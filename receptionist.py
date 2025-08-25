import os
import re
import smtplib
import base64
from email.message import EmailMessage
from typing import List, Dict, Any, Tuple

import streamlit as st

from auth import get_current_user
from db_postgres import (
    get_conn,
    find_candidates_by_name,
    get_all_candidates,
    delete_candidate,
    set_candidate_permission,
    get_user_permissions,
    save_receptionist_assessment,
    get_candidate_cv_secure,
)

EMAIL_RE = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.I)


# -------------------- Performance Optimizations --------------------

@st.cache_data(ttl=30, show_spinner=False)
def _get_candidates_cached(search_query=""):
    """Cached candidate loading to avoid database reload after each action."""
    try:
        if search_query and search_query.strip():
            return _search_candidates_all_fields(search_query.strip())
        else:
            return get_all_candidates()
    except Exception as e:
        st.error(f"Error loading candidates: {e}")
        return []


def _clear_candidates_cache():
    """Clear candidates cache for refresh."""
    _get_candidates_cached.clear()


# -------------------- Access Control Functions --------------------

def _check_user_permissions(user_id: int) -> Dict[str, Any]:
    """Check user permissions with strict enforcement."""
    try:
        perms = get_user_permissions(user_id)
        if not perms:
            return {"role": "user", "can_view_cvs": False, "can_delete_records": False, "can_manage_users": False}

        role = (perms.get("role") or "user").lower()

        return {
            "role": role,
            "can_view_cvs": bool(perms.get("can_view_cvs", False)),
            "can_delete_records": bool(perms.get("can_delete_records", False)),
            "can_manage_users": role in ("ceo", "admin")
        }
    except Exception as e:
        st.error(f"Permission check failed: {e}")
        return {"role": "user", "can_view_cvs": False, "can_delete_records": False, "can_manage_users": False}


def _get_cv_with_proper_access(candidate_id: str, user_id: int) -> tuple:
    """Get CV with proper access control like in CEO panel."""
    try:
        perms = _check_user_permissions(user_id)
        if not perms.get("can_view_cvs", False):
            return None, None, "no_permission"

        cv_bytes, cv_name, reason = get_candidate_cv_secure(candidate_id, user_id)
        return cv_bytes, cv_name, reason
    except Exception as e:
        st.error(f"CV fetch error: {e}")
        return None, None, "error"


# -------------------- CV Display Functions (Same as CEO) --------------------

def _detect_mimetype(filename: str) -> str:
    """Detect mimetype from filename."""
    if not filename:
        return "application/octet-stream"

    ext = filename.lower().split('.')[-1]
    mime_map = {
        'pdf': 'application/pdf',
        'txt': 'text/plain',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'doc': 'application/msword',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png'
    }
    return mime_map.get(ext, 'application/octet-stream')


def _render_cv_section_with_access(candidate_id: str, user_id: int, candidate_data: Dict[str, Any]):
    """Render CV section with proper access control (same as CEO panel)."""
    st.markdown("### 📄 CV & Documents")

    perms = _check_user_permissions(user_id)
    can_view = perms.get("can_view_cvs", False)

    if not can_view:
        st.warning("🔒 Access Denied: You need 'View CVs' permission to access candidate documents")
        return

    cv_bytes, cv_name, status = _get_cv_with_proper_access(candidate_id, user_id)

    if status == "ok" and cv_bytes:
        st.download_button(
            "📥 Download CV",
            data=cv_bytes,
            file_name=cv_name or f"{candidate_id}_cv.pdf",
            mime=_detect_mimetype(cv_name or ""),
            key=f"cv_dl_{candidate_id}"
        )

        if cv_name and cv_name.lower().endswith('.pdf'):
            try:
                b64 = base64.b64encode(cv_bytes).decode()
                st.markdown(f"""
                    <iframe 
                        src="data:application/pdf;base64,{b64}" 
                        width="100%" 
                        height="500px" 
                        style="border: 1px solid #ddd; border-radius: 5px;">
                    </iframe>
                """, unsafe_allow_html=True)
            except Exception:
                st.info("📄 PDF preview not available, but file can be downloaded")

    elif status == "link_only" and cv_name:
        st.markdown(f"🔗 **Resume Link:** [Open CV]({cv_name})")

        if "drive.google.com" in cv_name:
            try:
                if "file/d/" in cv_name:
                    file_id = cv_name.split("file/d/")[1].split("/")[0]
                    embed_url = f"https://drive.google.com/file/d/{file_id}/preview"
                elif "id=" in cv_name:
                    file_id = cv_name.split("id=")[1].split("&")[0]
                    embed_url = f"https://drive.google.com/file/d/{file_id}/preview"
                else:
                    embed_url = cv_name

                st.markdown(f"""
                    <iframe 
                        src="{embed_url}" 
                        width="100%" 
                        height="500px" 
                        style="border: 1px solid #ddd; border-radius: 5px;">
                    </iframe>
                """, unsafe_allow_html=True)
            except Exception:
                st.info("📄 CV link preview not available")

    elif status == "no_permission":
        st.warning("🔒 Access Denied: CV viewing permission required")
    elif status == "not_found":
        resume_link = candidate_data.get("resume_link")
        if resume_link:
            st.markdown(f"🔗 **Resume Link:** [Open CV]({resume_link})")
        else:
            st.info("📂 No CV uploaded")
    else:
        st.error("❌ Error accessing CV")


# -------------------- Interview Assessment Functions --------------------

def _get_receptionist_assessments_for_candidate(candidate_id: str) -> List[Dict[str, Any]]:
    """Get all assessments for this candidate."""
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            # Check if table exists
            cur.execute("""
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                          AND table_name = 'receptionist_assessments'
                        """)
            if not cur.fetchone():
                return []

            cur.execute("""
                        SELECT id,
                               created_at,
                               speed_test,
                               accuracy_test,
                               work_commitment,
                               english_understanding,
                               comments
                        FROM receptionist_assessments
                        WHERE candidate_id = %s
                        ORDER BY created_at DESC
                        """, (candidate_id,))

            assessments = []
            for row in cur.fetchall():
                assessments.append({
                    'id': row[0],
                    'created_at': row[1],
                    'speed_test': row[2],
                    'accuracy_test': row[3],
                    'work_commitment': row[4],
                    'english_understanding': row[5],
                    'comments': row[6]
                })

        conn.close()
        return assessments
    except Exception as e:
        st.warning(f"Could not load assessments: {e}")
        return []


def _render_assessment_history(candidate_id: str):
    """Show assessment history for the candidate."""
    assessments = _get_receptionist_assessments_for_candidate(candidate_id)

    if not assessments:
        st.info("📋 No previous assessments found")
        return

    st.markdown("#### 📊 Previous Assessments")
    for i, assessment in enumerate(assessments):
        with st.expander(f"Assessment #{i + 1} - {assessment['created_at']}", expanded=i == 0):
            col1, col2 = st.columns(2)

            with col1:
                st.metric("Speed Test", f"{assessment['speed_test']}/100")
                st.write(f"**Work Commitment:** {assessment['work_commitment']}")

            with col2:
                st.metric("Accuracy Test", f"{assessment['accuracy_test']}/100")
                st.write(f"**English:** {assessment['english_understanding']}")

            if assessment['comments']:
                st.write(f"**Comments:** {assessment['comments']}")


# ----------------------------
# Utilities
# ----------------------------

def _valid_email(addr: str) -> bool:
    return bool(EMAIL_RE.match(addr or ""))


def _search_candidates_all_fields(q: str) -> List[Dict[str, Any]]:
    """
    Search widely in the candidates table. Falls back to legacy name search if anything fails.
    """
    try:
        conn = get_conn()
        with conn, conn.cursor() as cur:
            like = f"%{q}%"
            cur.execute(
                """
                SELECT id, candidate_id, name, email, phone, created_at, form_data
                FROM candidates
                WHERE candidate_id ILIKE %s
                   OR
                    name ILIKE %s
                   OR
                    email ILIKE %s
                   OR
                    phone ILIKE %s
                   OR
                    COALESCE (CAST (form_data AS TEXT)
                    , '') ILIKE %s
                ORDER BY created_at DESC
                    LIMIT 200
                """,
                (like, like, like, like, like),
            )
            rows = cur.fetchall()
        conn.close()
        return [
            {
                "id": r[0],
                "candidate_id": r[1],
                "name": r[2],
                "email": r[3],
                "phone": r[4],
                "created_at": r[5],
                "form_data": r[6],
            }
            for r in rows
        ]
    except Exception:
        # legacy fallback
        return find_candidates_by_name(q)


def _send_candidate_code(email: str, candidate_id: str) -> Tuple[bool, str]:
    """
    Email candidate code using SMTP env (same pattern you used in auth).
    Falls back to console print if SMTP not configured.
    """
    if not _valid_email(email):
        return False, "Invalid email address."

    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    from_email = os.getenv("FROM_EMAIL", "no-reply@brv.local")

    subject = "Your BRV Candidate Code"
    body = f"""Hello,

Your candidate code is: {candidate_id}

Use this code to view/update your application if permitted.

Thanks,
BRV Recruitment
"""

    if smtp_host and smtp_port and smtp_user and smtp_pass:
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = from_email
            msg["To"] = email
            msg.set_content(body)

            with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            return True, "Email sent."
        except Exception as e:
            return False, f"SMTP error: {e}"
    else:
        # fallback: console
        print("---- Candidate Code Email (console fallback) ----")
        print("To:", email)
        print(body)
        print("-----------------------------------------------")
        return True, "Printed to console (SMTP not configured)."


# ----------------------------
# Main Receptionist view
# ----------------------------
def receptionist_view():
    st.header("🏢 Receptionist — Candidate Assessment & Management")

    # Current user & permissions
    current_user = get_current_user()
    if not current_user:
        st.error("No active user session. Please log in.")
        return

    user_id = current_user.get("id")
    perms = _check_user_permissions(user_id)
    role = perms.get("role", "user")

    # Show permissions in sidebar
    st.sidebar.markdown("### 🔑 Your Permissions")
    st.sidebar.markdown(f"- **Role:** {role.title()}")
    st.sidebar.markdown(f"- **View CVs:** {'✅ Enabled' if perms.get('can_view_cvs') else '❌ Disabled'}")
    st.sidebar.markdown(f"- **Delete Records:** {'✅ Enabled' if perms.get('can_delete_records') else '❌ Disabled'}")

    # Search section
    st.subheader("🔍 Search & Manage Candidates")

    # Search with refresh button
    col1, col2 = st.columns([4, 1])
    with col1:
        q = st.text_input(
            "Search by candidate code, name, email, phone, or any form value",
            placeholder="Type to search…",
            key="recept_search",
        )
    with col2:
        if st.button("🔄 Refresh", key="refresh_candidates"):
            _clear_candidates_cache()
            st.rerun()

    # Load candidates (cached for performance)
    candidates = _get_candidates_cached(q)
    st.caption(f"📊 Found {len(candidates)} candidate(s).")

    if not candidates:
        st.info("No candidates found. Try adjusting your search or refresh the data.")
        return

    for c in candidates:
        candidate_id = c.get('candidate_id', '')
        candidate_name = c.get('name', '(no name)')

        header = f"👤 {candidate_name} — {candidate_id}"
        with st.expander(header, expanded=False):
            # Basic info section
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### 📋 Basic Information")
                st.write(f"**Name:** {candidate_name}")
                st.write(f"**Email:** {c.get('email', '—')}")
                st.write(f"**Phone:** {c.get('phone', '—')}")

            with col2:
                st.markdown("#### 🕐 Timeline")
                st.write(f"**Created:** {c.get('created_at', '—')}")
                st.write(f"**ID:** {candidate_id}")

            # CV section with proper access control
            st.markdown("---")
            _render_cv_section_with_access(candidate_id, user_id, c)

            # Assessment history
            st.markdown("---")
            _render_assessment_history(candidate_id)

            # New assessment form
            st.markdown("---")
            st.markdown("### ➕ New Receptionist Assessment")
            st.info("💡 Complete this assessment to make candidate eligible for interviews")

            with st.form(key=f"recept_assess_{candidate_id}"):
                st.markdown("#### 📊 Test Scores")
                col1, col2 = st.columns(2)
                with col1:
                    speed_test = st.number_input(
                        "Speed Test Score (0-100)",
                        min_value=0, max_value=100, value=0,
                        help="Typing speed test result"
                    )
                    accuracy_test = st.number_input(
                        "Accuracy Test Score (0-100)",
                        min_value=0, max_value=100, value=0,
                        help="Typing accuracy test result"
                    )
                with col2:
                    work_commitment = st.selectbox(
                        "Work Commitment Level",
                        ["Low", "Medium", "High"],
                        index=1,
                        help="Assessment of candidate's commitment to work"
                    )
                    english_understanding = st.selectbox(
                        "English Understanding",
                        ["Poor", "Average", "Good", "Excellent"],
                        index=1,
                        help="Assessment of candidate's English language skills"
                    )

                st.markdown("#### 📝 Comments")
                comments = st.text_area(
                    "Assessment Comments",
                    placeholder="Any observations about the candidate's performance, attitude, communication skills, etc...",
                    height=120
                )

                submitted = st.form_submit_button("💾 Save Assessment", type="primary")

            if submitted:
                try:
                    ok = save_receptionist_assessment(
                        candidate_id,
                        int(speed_test),
                        int(accuracy_test),
                        work_commitment,
                        english_understanding,
                        comments.strip(),
                    )
                    if ok:
                        st.success("✅ Assessment saved successfully! Candidate is now eligible for interviews.")
                        _clear_candidates_cache()
                        st.rerun()
                    else:
                        st.error("❌ Failed to save assessment.")
                except Exception as e:
                    st.error(f"Error saving assessment: {e}")

            # Quick actions section
            st.markdown("---")
            st.markdown("### ⚙️ Quick Actions")

            action_col1, action_col2, action_col3, action_col4 = st.columns(4)

            with action_col1:
                if st.button("🔓 Allow Edit (by code)", key=f"allow_{candidate_id}"):
                    if set_candidate_permission(candidate_id, True):
                        st.success("✅ Edit permission granted.")
                        _clear_candidates_cache()
                        st.rerun()
                    else:
                        st.error("❌ Failed to update permission.")

            with action_col2:
                if st.button("🔒 Revoke Edit", key=f"revoke_{candidate_id}"):
                    if set_candidate_permission(candidate_id, False):
                        st.success("✅ Edit permission revoked.")
                        _clear_candidates_cache()
                        st.rerun()
                    else:
                        st.error("❌ Failed to update permission.")

            with action_col3:
                if st.button("📧 Email Code", key=f"emailcode_{candidate_id}"):
                    ok, msg = _send_candidate_code(c.get("email", ""), candidate_id)
                    if ok:
                        st.success(f"✅ {msg}")
                    else:
                        st.error(f"❌ {msg}")

            with action_col4:
                # Delete with proper permission check
                if perms.get("can_delete_records"):
                    if st.button("🗑️ Delete", key=f"del_{candidate_id}"):
                        try:
                            success, reason = delete_candidate(candidate_id, user_id)
                            if success:
                                st.success("✅ Candidate deleted successfully.")
                                _clear_candidates_cache()
                                st.rerun()
                            else:
                                if reason == "no_permission":
                                    st.error("🔒 Access Denied: Insufficient permissions")
                                else:
                                    st.error(f"❌ Delete failed: {reason}")
                        except Exception as e:
                            st.error(f"❌ Delete error: {e}")
                else:
                    st.info("🚫 No delete permission")

            # Show current permissions for this candidate
            st.markdown("---")
            st.caption("**Current Status:**")
            assessments = _get_receptionist_assessments_for_candidate(candidate_id)
            if assessments:
                st.caption("✅ Has receptionist assessment - Eligible for interviews")
            else:
                st.caption("❌ No assessment - Not eligible for interviews")

    # Footer with summary and refresh
    st.markdown("---")
    st.markdown("### 📊 Dashboard Summary")

    summary_col1, summary_col2, summary_col3 = st.columns(3)

    with summary_col1:
        if st.button("🔄 Refresh All Data"):
            _clear_candidates_cache()
            st.rerun()

    with summary_col2:
        total_candidates = len(candidates)
        st.metric("Total Candidates", total_candidates)

    with summary_col3:
        # Count assessed candidates
        assessed_count = 0
        for c in candidates:
            assessments = _get_receptionist_assessments_for_candidate(c.get('candidate_id', ''))
            if assessments:
                assessed_count += 1
        st.metric("Assessed", f"{assessed_count}/{total_candidates}")

    st.info("""
    💡 **Receptionist Role:**
    - Assess candidates with speed/accuracy tests and evaluation questions
    - Manage candidate edit permissions  
    - Email candidate codes for self-service access
    - CV access requires permission from CEO/Admin
    - Only candidates with completed assessments are eligible for interviews
    """)