# receptionist.py
import os
import re
import smtplib
from email.message import EmailMessage
from typing import List, Dict, Any, Tuple

import streamlit as st

from db_postgres import (
    get_conn,
    find_candidates_by_name,
    get_all_candidates,
    get_candidate_cv,
    delete_candidate_by_actor,
    set_candidate_permission,            # present in your DB layer
    get_user_permissions,                # used for permission checks
    save_receptionist_assessment,        # save assessment block
)

EMAIL_RE = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.I)


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
                WHERE
                    candidate_id ILIKE %s OR
                    name ILIKE %s OR
                    email ILIKE %s OR
                    phone ILIKE %s OR
                    COALESCE(CAST(form_data AS TEXT),'') ILIKE %s
                ORDER BY created_at DESC
                LIMIT 200
                """,
                (like, like, like, like, like),
            )
            rows = cur.fetchall()
        conn.close()
        res: List[Dict[str, Any]] = []
        for r in rows:
            res.append(
                {
                    "id": r[0],
                    "candidate_id": r[1],
                    "name": r[2],
                    "email": r[3],
                    "phone": r[4],
                    "created_at": r[5],
                    "form_data": r[6],
                }
            )
        return res
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


def _cv_preview_and_download(candidate_id: str):
    """
    Local CV preview + download. Respects permission checks done by caller.
    """
    cv_file, cv_filename = get_candidate_cv(candidate_id)
    if not cv_file:
        st.info("No CV uploaded yet.")
        return

    st.success(f"✅ CV on file: {cv_filename or 'unnamed'}")
    st.download_button(
        label="Download CV",
        data=cv_file,
        file_name=cv_filename or f"{candidate_id}_cv.bin",
        mime="application/octet-stream",
        key=f"dlcv_{candidate_id}",
    )
    # Lightweight inline PDF preview if filename looks like PDF
    if (cv_filename or "").lower().endswith(".pdf"):
        try:
            st.caption("Inline preview (PDF):")
            st.pdf(cv_file)  # Streamlit 1.36+; if your version lacks st.pdf, ignore silently
        except Exception:
            pass


# ----------------------------
# Main Receptionist view
# ----------------------------

def receptionist_view():
    st.header("Receptionist — Candidate Management")

    # Current user & permissions
    current_user = st.session_state.get("user")
    if not current_user:
        st.error("No active user session. Please log in.")
        return

    # Search section
    st.subheader("Search Candidates (all fields)")
    q = st.text_input(
        "Search by candidate code, name, email, phone, or any form value",
        placeholder="Type to search…",
        key="recept_search",
    )

    if q.strip():
        rows = _search_candidates_all_fields(q.strip())
    else:
        rows = get_all_candidates()

    st.caption(f"{len(rows)} result(s).")

    for c in rows:
        header = f"{c.get('name','(no name)')} — {c.get('candidate_id')}"
        with st.expander(header, expanded=False):
            st.write(f"**Email:** {c.get('email','—')}")
            st.write(f"**Phone:** {c.get('phone','—')}")
            st.write(f"**Created:** {c.get('created_at','—')}")

            # ---------------- CV section (permission protected) ----------------
            st.markdown("### Resume / CV")
            perms = get_user_permissions(current_user["id"]) or {}
            if not perms.get("can_view_cvs", False):
                st.warning("You do not have permission to view CVs.")
            else:
                try:
                    _cv_preview_and_download(c["candidate_id"])
                except Exception as e:
                    st.error(f"Error fetching CV: {e}")

            st.markdown("---")

            # ---------------- Receptionist assessment block ----------------
            st.markdown("### Receptionist Assessment")
            with st.form(key=f"recept_assess_{c['candidate_id']}"):
                col1, col2 = st.columns(2)
                with col1:
                    speed_test = st.number_input("Speed Test (0-100)", min_value=0, max_value=100, value=0)
                    accuracy_test = st.number_input("Accuracy Test (0-100)", min_value=0, max_value=100, value=0)
                with col2:
                    work_commitment = st.selectbox(
                        "Work Commitment",
                        ["Low", "Medium", "High"],
                        index=1
                    )
                    english_understanding = st.selectbox(
                        "English Understanding",
                        ["Poor", "Average", "Good", "Excellent"],
                        index=1
                    )
                comments = st.text_area("Comments", placeholder="Any brief observations…")
                submitted = st.form_submit_button("Save Assessment")
            if submitted:
                ok = save_receptionist_assessment(
                    c["candidate_id"],
                    int(speed_test),
                    int(accuracy_test),
                    work_commitment,
                    english_understanding,
                    comments.strip(),
                )
                if ok:
                    st.success("Assessment saved.")
                else:
                    st.error("Failed to save assessment.")

            st.markdown("---")

            # ---------------- Quick actions ----------------
            st.caption("Quick Actions")
            colA, colB, colC, colD = st.columns(4)

            with colA:
                if st.button("Allow Edit (by code)", key=f"allow_{c['candidate_id']}"):
                    if set_candidate_permission(c["candidate_id"], True):
                        st.success("Edit permission granted.")
                    else:
                        st.error("Failed to update permission.")

            with colB:
                if st.button("Revoke Edit", key=f"revoke_{c['candidate_id']}"):
                    if set_candidate_permission(c["candidate_id"], False):
                        st.success("Edit permission revoked.")
                    else:
                        st.error("Failed to update permission.")

            with colC:
                if st.button("Email Candidate Code", key=f"emailcode_{c['candidate_id']}"):
                    ok, msg = _send_candidate_code(c.get("email", ""), c["candidate_id"])
                    (st.success if ok else st.error)(msg)

            with colD:
                # Permission-aware delete
                if st.button("🗑️ Delete Candidate", key=f"del_{c['candidate_id']}"):
                    if not perms.get("can_delete_records", False):
                        st.error("You do not have permission to delete candidate records.")
                    else:
                        if delete_candidate_by_actor(c["candidate_id"], current_user["id"]):
                            st.success("Candidate deleted.")
                            st.rerun()
                        else:
                            st.error("Failed to delete candidate (or not permitted).")

    st.caption("Note: Receptionist can assess candidates, manage edit permission, and email codes. Creation of candidates is not shown here.")
