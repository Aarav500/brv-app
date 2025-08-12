"""
drive_and_cv_views.py
Single-file Google Drive + CV Streamlit views + Postgres candidate helpers.

Requirements:
  pip install streamlit psycopg2-binary google-api-python-client oauth2client python-dotenv

Env vars:
  DATABASE_URL - Postgres full URL, e.g. postgres://user:pass@host:5432/dbname
  GOOGLE_SERVICE_ACCOUNT_FILE - path to service account json
  GOOGLE_DRIVE_FOLDER_ID - (optional) existing folder id to use for CVs
"""

import os
import io
import json
import uuid
import traceback
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

# DB
import psycopg2
from psycopg2.extras import RealDictCursor, Json

# Google
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

load_dotenv()

# ---------- Configuration ----------
DATABASE_URL = os.getenv("DATABASE_URL")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")  # optional

# Safe checks
if not DATABASE_URL:
    st.warning("DATABASE_URL not set — DB functions will fail until set.")
if not GOOGLE_SERVICE_ACCOUNT_FILE:
    st.warning("GOOGLE_SERVICE_ACCOUNT_FILE not set — Drive functions will fail until set.")

# ---------- Postgres helpers (candidates table uses form_data JSON to hold 'allowed_edit') ----------

def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable not set")
    return psycopg2.connect(DATABASE_URL, sslmode=os.getenv("PGSSLMODE", "require"))

def init_candidates_table():
    """Create candidates table if it doesn't exist. form_data is JSONB and will store 'allowed_edit'."""
    sql = """
    CREATE TABLE IF NOT EXISTS candidates (
        id SERIAL PRIMARY KEY,
        candidate_id TEXT UNIQUE NOT NULL,
        name TEXT,
        email TEXT,
        phone TEXT,
        form_data JSONB DEFAULT '{}'::jsonb,
        resume_link TEXT,
        created_by TEXT,
        created_at TIMESTAMP DEFAULT now(),
        updated_at TIMESTAMP DEFAULT now()
    );
    """
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql)
    finally:
        conn.close()

def create_candidate(candidate_id: str, name: str, email: str, phone: str, form_data: dict, created_by: str):
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO candidates (candidate_id, name, email, phone, form_data, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING *;
                    """,
                    (candidate_id, name, email, phone, Json(form_data), created_by)
                )
                return cur.fetchone()
    except psycopg2.errors.UniqueViolation:
        # candidate_id exists
        conn.rollback()
        return None
    finally:
        conn.close()

def find_candidates_by_name(name: str):
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM candidates WHERE LOWER(name) LIKE %s ORDER BY updated_at DESC",
                    (f"%{name.lower()}%",)
                )
                return cur.fetchall()
    finally:
        conn.close()

def get_candidate_by_id(candidate_id: str):
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM candidates WHERE candidate_id = %s", (candidate_id,))
                return cur.fetchone()
    finally:
        conn.close()

def update_candidate_form_data(candidate_id: str, new_form_data: dict):
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE candidates SET form_data = %s, updated_at = now() WHERE candidate_id = %s",
                    (Json(new_form_data), candidate_id)
                )
                return cur.rowcount > 0
    finally:
        conn.close()

def update_candidate_resume_link(candidate_id: str, resume_link: str):
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE candidates SET resume_link = %s, updated_at = now() WHERE candidate_id = %s",
                    (resume_link, candidate_id)
                )
                return cur.rowcount > 0
    finally:
        conn.close()

# ---------- Google Drive helpers ----------

def get_drive_service():
    """Return an authenticated Drive v3 service for the service account JSON path."""
    if not GOOGLE_SERVICE_ACCOUNT_FILE:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_FILE not configured")

    scopes = ['https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SERVICE_ACCOUNT_FILE, scopes)
    service = build('drive', 'v3', credentials=creds, cache_discovery=False)
    return service

def ensure_drive_folder(folder_name="BRV_CVs"):
    """
    Ensure a folder exists in Drive. If GOOGLE_DRIVE_FOLDER_ID is set in env, use it.
    Otherwise search for a folder with the name under the service account drive and create it if missing.
    Returns folder_id.
    """
    global GOOGLE_DRIVE_FOLDER_ID
    if GOOGLE_DRIVE_FOLDER_ID:
        return GOOGLE_DRIVE_FOLDER_ID

    svc = get_drive_service()
    # try to find an existing folder
    q = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    try:
        resp = svc.files().list(q=q, spaces='drive', fields='files(id,name)', pageSize=10).execute()
        files = resp.get('files', [])
        if files:
            GOOGLE_DRIVE_FOLDER_ID = files[0]['id']
            print("Using existing Drive folder id:", GOOGLE_DRIVE_FOLDER_ID)
            return GOOGLE_DRIVE_FOLDER_ID
        # create folder
        metadata = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
        newf = svc.files().create(body=metadata, fields='id').execute()
        GOOGLE_DRIVE_FOLDER_ID = newf.get('id')
        print("Created Drive folder id:", GOOGLE_DRIVE_FOLDER_ID)
        return GOOGLE_DRIVE_FOLDER_ID
    except Exception as e:
        print("Error ensuring Drive folder:", e)
        traceback.print_exc()
        raise

def upload_resume_to_drive(candidate_id: str, file_bytes: bytes, filename: str):
    """
    Upload file bytes to Drive into the configured folder.
    Returns (True, webViewLink, message) or (False, None, error_message)
    """
    try:
        svc = get_drive_service()
        folder_id = ensure_drive_folder()
        # build a unique name to avoid collisions
        safe_name = f"{candidate_id}_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}_{filename}"
        fh = io.BytesIO(file_bytes)
        media = MediaIoBaseUpload(fh, mimetype="application/pdf", resumable=False)
        metadata = {
            'name': safe_name,
            'parents': [folder_id],
        }
        file = svc.files().create(body=metadata, media_body=media, fields='id,webViewLink,webContentLink').execute()
        file_id = file.get('id')
        # make file readable by anyone with the link (optional — if you prefer more restricted access, change below)
        svc.permissions().create(fileId=file_id, body={"role": "reader", "type": "anyone"}).execute()
        webview = file.get('webViewLink') or f"https://drive.google.com/file/d/{file_id}/view"
        return True, webview, "Uploaded"
    except Exception as e:
        print("Drive upload error:", e)
        traceback.print_exc()
        return False, None, str(e)

def download_resume_bytes_from_drive(file_id: str):
    svc = get_drive_service()
    request = svc.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = None
    try:
        from googleapiclient.http import MediaIoBaseDownload
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.seek(0)
        return fh.read()
    except Exception as e:
        print("Download error:", e)
        traceback.print_exc()
        return None

def extract_drive_file_id_from_link(link: str):
    """
    Accept typical Drive link forms and extract fileId if possible.
    """
    if not link:
        return None
    # patterns:
    # https://drive.google.com/file/d/<id>/view?usp=sharing
    # https://drive.google.com/open?id=<id>
    try:
        if "drive.google.com" in link:
            # simple heuristics
            if "/d/" in link:
                parts = link.split("/d/")
                after = parts[1]
                file_id = after.split("/")[0]
                return file_id
            if "id=" in link:
                parts = link.split("id=")
                return parts[1].split("&")[0]
    except Exception:
        pass
    return None

# ---------- Streamlit UI: Candidate view & Receptionist view ----------

st.set_page_config(page_title="CV Upload (Drive) — Candidate / Receptionist", layout="wide")

# Initialize DB table (idempotent)
try:
    init_candidates_table()
except Exception as e:
    st.error(f"Failed to init DB table: {e}")

# small helper UI utils
def show_candidate_card(candidate):
    st.write("**Candidate ID:**", candidate['candidate_id'])
    st.write("**Name:**", candidate.get('name'))
    st.write("**Email:**", candidate.get('email'))
    st.write("**Phone:**", candidate.get('phone'))
    st.write("**Created By:**", candidate.get('created_by'))
    st.write("**Updated At:**", candidate.get('updated_at'))
    st.write("**Allowed to Edit (by receptionist)?**", candidate.get('form_data', {}).get('allowed_edit', False))
    if candidate.get('resume_link'):
        st.markdown(f"[Open Resume]({candidate['resume_link']})")
    st.markdown("---")

# Candidate flow
def candidate_form_view():
    st.header("Candidate — Submit / Edit Application")

    # Candidate either provides candidate_id (to edit) or leaves blank to create
    candidate_id = st.text_input("Candidate ID (leave blank to create new)")
    name = st.text_input("Full name")
    email = st.text_input("Email")
    phone = st.text_input("Phone")
    st.markdown("Upload your CV (PDF preferred). If editing, receptionist must have allowed edit for your name.")
    uploaded_file = st.file_uploader("Upload CV", type=["pdf"], help="PDF recommended")

    # If editing existing
    if candidate_id:
        existing = get_candidate_by_id(candidate_id)
        if not existing:
            st.warning("Candidate ID not found. Leave Candidate ID blank to create a new record.")
        else:
            st.info("Found record — you may edit if receptionist granted permission to your name.")
            show_candidate_card(existing)

    if st.button("Submit"):
        # Validation
        if not name or not email:
            st.warning("Please provide name & email.")
            return

        if not candidate_id:
            # create
            candidate_id = str(uuid.uuid4())[:8]
            form_data = {"allowed_edit": False, "history": [{"action": "created", "at": datetime.utcnow().isoformat()}]}
            created = create_candidate(candidate_id, name, email, phone, form_data, "candidate_portal")
            if not created:
                st.error("Failed to create candidate. Candidate ID collision (rare); please try again.")
                return
            st.success(f"Application created. Candidate ID: {candidate_id}")
        else:
            # editing attempt
            existing = get_candidate_by_id(candidate_id)
            if not existing:
                st.error("Candidate ID not found.")
                return
            # Check permission by comparing names (case-insensitive) and allowed_edit flag in form_data
            allowed = False
            fd = existing.get('form_data') or {}
            if fd.get('allowed_edit') and existing.get('name') and existing.get('name').strip().lower() == name.strip().lower():
                allowed = True
            if not allowed:
                st.error("You don't have permission to edit this application. Please ask the receptionist to grant edit permission for your name.")
                return
            # update form_data history
            fd.setdefault('history', []).append({"action": "edited_by_candidate", "at": datetime.utcnow().isoformat()})
            # write updates
            ok = update_candidate_form_data(candidate_id, fd)
            if ok:
                # also update basic fields (name/email/phone)
                # read-modify-write via create/update functions; to keep simple, update resume and form only
                conn = get_conn()
                try:
                    with conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                "UPDATE candidates SET name=%s, email=%s, phone=%s, updated_at=now() WHERE candidate_id=%s",
                                (name, email, phone, candidate_id)
                            )
                    st.success("Application updated.")
                finally:
                    conn.close()
            else:
                st.error("Failed to update application.")

        # handle file upload if provided
        if uploaded_file:
            # read bytes and call drive upload
            file_bytes = uploaded_file.read()
            filename = uploaded_file.name
            st.info("Uploading resume to Google Drive...")
            success, webview, msg = upload_resume_to_drive(candidate_id, file_bytes, filename)
            if success:
                update_candidate_resume_link(candidate_id, webview)
                st.success("Resume uploaded and linked.")
                st.markdown(f"[Open Resume]({webview})")
            else:
                st.error(f"Resume upload failed: {msg}")

# Receptionist flow
def receptionist_view():
    st.header("Receptionist — Manage Candidates & Grant Edit Permission (by name)")

    st.markdown("**Search candidates by name (partial match).** You can grant permission to edit to a candidate by matching their name.")

    search_name = st.text_input("Search name (partial)")
    if st.button("Search"):
        if not search_name:
            st.warning("Type a name to search.")
        else:
            results = find_candidates_by_name(search_name)
            if not results:
                st.info("No candidates found with that name.")
            else:
                st.success(f"{len(results)} candidate(s) found")
                for c in results:
                    with st.expander(f"{c['candidate_id']} — {c.get('name')}"):
                        show_candidate_card(c)
                        st.write("Set permission for this candidate:")
                        allow = st.checkbox("Allow this candidate to edit their application", value=c.get('form_data', {}).get('allowed_edit', False), key=f"allow_{c['candidate_id']}")
                        if st.button("Apply permission", key=f"applyperm_{c['candidate_id']}"):
                            fd = c.get('form_data') or {}
                            fd['allowed_edit'] = bool(allow)
                            fd.setdefault('history', []).append({"action": ("granted" if allow else "revoked"), "by": "receptionist", "at": datetime.utcnow().isoformat()})
                            ok = update_candidate_form_data(c['candidate_id'], fd)
                            if ok:
                                st.success(f"Permission {'granted' if allow else 'revoked'} for {c['candidate_id']}")
                            else:
                                st.error("Failed to update permission.")

                        st.markdown("**Upload / replace resume for this candidate**")
                        up = st.file_uploader(f"Upload resume for {c['candidate_id']}", key=f"up_{c['candidate_id']}", type=["pdf"])
                        if up:
                            bytes_ = up.read()
                            st.info("Uploading resume to Drive...")
                            success, webview, msg = upload_resume_to_drive(c['candidate_id'], bytes_, up.name)
                            if success:
                                update_candidate_resume_link(c['candidate_id'], webview)
                                st.success("Resume uploaded and linked.")
                                st.markdown(f"[Open Resume]({webview})")
                            else:
                                st.error("Upload failed: " + str(msg))

    st.markdown("---")
    st.subheader("Quick create candidate (walk-in)")
    name = st.text_input("Name (new)", key="walkin_name")
    email = st.text_input("Email (new)", key="walkin_email")
    phone = st.text_input("Phone (new)", key="walkin_phone")
    walkin_file = st.file_uploader("Optional CV for walk-in", key="walkin_cv", type=["pdf"])
    if st.button("Create walk-in"):
        if not name:
            st.warning("Name required")
        else:
            new_id = str(uuid.uuid4())[:8]
            form_data = {"allowed_edit": True, "history": [{"action": "created_by_receptionist", "at": datetime.utcnow().isoformat()}]}
            rec = create_candidate(new_id, name, email, phone, form_data, "receptionist")
            if rec:
                st.success(f"Created candidate {new_id}")
                if walkin_file:
                    b = walkin_file.read()
                    ok, link, m = upload_resume_to_drive(new_id, b, walkin_file.name)
                    if ok:
                        update_candidate_resume_link(new_id, link)
                        st.success("Resume uploaded for walk-in candidate.")
                        st.markdown(f"[Open Resume]({link})")
                    else:
                        st.error("Resume upload failed: " + str(m))
            else:
                st.error("Failed to create candidate (duplicate id?), try again.")

# ---------- Main routing in Streamlit ----------
st.sidebar.title("Role")
role = st.sidebar.selectbox("Open as", ["Candidate", "Receptionist", "Debug"])
if role == "Candidate":
    candidate_form_view()
elif role == "Receptionist":
    receptionist_view()
else:
    st.header("Debug / Tools")
    st.write("Use this panel to inspect DB and Drive connection status.")
    st.subheader("Drive")
    try:
        svc = get_drive_service()
        st.success("Drive service initialized")
        fid = ensure_drive_folder()
        st.write("Drive folder id:", fid)
    except Exception as e:
        st.error(f"Drive init error: {e}")
    st.subheader("DB")
    try:
        conn = get_conn()
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM candidates;")
                cnt = cur.fetchone()[0]
        st.success("DB reachable. Candidates count: " + str(cnt))
    except Exception as e:
        st.error("DB error: " + str(e))
    finally:
        try:
            conn.close()
        except:
            pass

