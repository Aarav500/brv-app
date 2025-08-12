import streamlit as st
import json
import uuid
from datetime import datetime

from mysql_db import get_db_connection
from cloud_storage import upload_cv, download_cv
from resume_linker import save_temp_cv
from security import hash_password  # might be needed for candidate registration

# ---------- DB helpers ----------
def _fetchone(query, params=()):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
    finally:
        conn.close()

def _fetchall(query, params=()):
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall()
            return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()

def _execute(query, params=()):
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            conn.commit()
            return True
    except Exception as e:
        st.error(f"DB error: {e}")
        return False
    finally:
        conn.close()

# ---------- Candidate DB ops ----------
def create_candidate_record(data):
    """
    data: dict with keys: name, email, phone, skills, experience, education, created_by, resume_link(optional)
    Returns candidate_id (UUID string) or None
    """
    candidate_id = str(uuid.uuid4())
    query = """
        INSERT INTO candidates (
            candidate_id, full_name, email, phone, qualification, work_experience,
            resume_link, timestamp, interview_status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s)
    """
    ok = _execute(query, (
        candidate_id,
        data.get("name"),
        data.get("email"),
        data.get("phone"),
        data.get("education"),
        data.get("experience"),
        data.get("cv_url"),
        data.get("interview_status", "Not Scheduled")
    ))
    if ok:
        return candidate_id
    return None

def get_candidate_by_id(candidate_id):
    query = "SELECT * FROM candidates WHERE candidate_id = %s"
    return _fetchone(query, (candidate_id,))

def get_candidate_by_email(email):
    query = "SELECT * FROM candidates WHERE email = %s"
    return _fetchone(query, (email,))

def update_candidate_record(candidate_id, update_fields: dict):
    if not update_fields:
        return False
    set_clauses = []
    params = []
    for k, v in update_fields.items():
        set_clauses.append(f"{k} = %s")
        params.append(v)
    params.append(candidate_id)
    query = f"UPDATE candidates SET {', '.join(set_clauses)}, timestamp = NOW() WHERE candidate_id = %s"
    return _execute(query, tuple(params))

# ---------- Streamlit UI ----------
def candidate_form_view():
    st.title("BRV Application")

    # If user logged in as candidate -> show authenticated view
    if st.session_state.get("authenticated") and st.session_state.get("user_role") == "candidate":
        candidate_id = st.session_state.get("candidate_id")
        if not candidate_id:
            # try to find by user id/email
            email = st.session_state.get("email")
            if email:
                cand = get_candidate_by_email(email)
                if cand:
                    st.session_state.candidate_id = cand["candidate_id"]
                    candidate_id = cand["candidate_id"]
        if not candidate_id:
            st.error("Candidate profile not found. Contact support.")
            return
        show_authenticated_candidate(candidate_id)
    else:
        show_public_application()

def show_authenticated_candidate(candidate_id):
    candidate = get_candidate_by_id(candidate_id)
    if not candidate:
        st.error("Candidate not found")
        return

    st.subheader("Your Information")
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Name:** {candidate.get('full_name')}")
        st.write(f"**Email:** {candidate.get('email')}")
        st.write(f"**Phone:** {candidate.get('phone')}")
    with col2:
        st.write(f"**Application ID:** {candidate.get('candidate_id')}")
        st.write(f"**Interview Status:** {candidate.get('interview_status') or 'Not Scheduled'}")

    if candidate.get("resume_link"):
        st.markdown(f"Resume: {candidate.get('resume_link')}")

    if st.button("Edit Application"):
        st.session_state.editing_own_application = True
        st.experimental_rerun()

    if st.session_state.get("editing_own_application"):
        success = edit_candidate_form(candidate)
        if success:
            st.session_state.editing_own_application = False
            st.experimental_rerun()

    if st.button("Logout"):
        for k in ["authenticated","user_id","email","user_role","candidate_id"]:
            st.session_state.pop(k, None)
        st.experimental_rerun()

def show_public_application():
    st.title("Apply (No Account Required)")
    if "candidate_form_data" not in st.session_state:
        st.session_state.candidate_form_data = {}
    with st.form("candidate_application_form"):
        name = st.text_input("Full Name*", value=st.session_state.candidate_form_data.get("name",""))
        email = st.text_input("Email*", value=st.session_state.candidate_form_data.get("email",""))
        phone = st.text_input("Phone", value=st.session_state.candidate_form_data.get("phone",""))
        skills = st.text_area("Skills", value=st.session_state.candidate_form_data.get("skills",""))
        experience = st.text_area("Experience", value=st.session_state.candidate_form_data.get("experience",""))
        education = st.text_area("Education", value=st.session_state.candidate_form_data.get("education",""))
        uploaded_file = st.file_uploader("Upload CV", type=["pdf","doc","docx"])

        submit = st.form_submit_button("Submit")
        if submit:
            if not name or not email:
                st.error("Name and email required")
                return
            cv_url = None
            if uploaded_file:
                try:
                    # upload to google drive (cloud_storage.upload_cv returns link)
                    temp_bytes = uploaded_file.read()
                    cv_url = upload_cv(str(uuid.uuid4()), temp_bytes, uploaded_file.name)
                except Exception as e:
                    st.error(f"CV upload failed: {e}")
                    return
            data = {
                "name": name,
                "email": email,
                "phone": phone,
                "skills": skills,
                "experience": experience,
                "education": education,
                "cv_url": cv_url,
                "interview_status": "Not Scheduled"
            }
            candidate_id = create_candidate_record(data)
            if candidate_id:
                st.success(f"Application submitted successfully. Your ID: {candidate_id}")
                # reset form state
                st.session_state.candidate_form_data = {}
            else:
                st.error("Failed to submit application. Try again later.")

def edit_candidate_form(candidate):
    st.title("Edit Application")
    with st.form("edit_candidate_form"):
        name = st.text_input("Full Name*", value=candidate.get("full_name",""))
        email = st.text_input("Email*", value=candidate.get("email",""))
        phone = st.text_input("Phone", value=candidate.get("phone",""))
        experience = st.text_area("Experience", value=candidate.get("work_experience",""))
        education = st.text_area("Education", value=candidate.get("qualification",""))
        uploaded_file = st.file_uploader("Upload new CV", type=["pdf","doc","docx"])
        submit = st.form_submit_button("Update")
        if submit:
            update = {
                "full_name": name,
                "email": email,
                "phone": phone,
                "work_experience": experience,
                "qualification": education
            }
            if uploaded_file:
                try:
                    uploaded_file.seek(0)
                    cv_url = upload_cv(candidate["candidate_id"], uploaded_file.read(), uploaded_file.name)
                    update["resume_link"] = cv_url
                except Exception as e:
                    st.error(f"CV upload failed: {e}")
                    return False
            ok = update_candidate_record(candidate["candidate_id"], update)
            if ok:
                st.success("Application updated")
                return True
            else:
                st.error("Update failed")
                return False
    return False
