# receptionist.py
import os
import re
import json
import logging
import smtplib
from email.message import EmailMessage
from typing import List, Dict, Any, Optional, Tuple

import streamlit as st

from db_postgres import (
    get_conn,
    find_candidates_by_name,
    update_candidate_form_data,
    create_candidate_in_db,
    get_all_candidates,
    get_user_permissions,
    get_candidate_cv,
    delete_candidate_by_actor,
    save_receptionist_assessment,
)
from drive_and_cv_views import (
    preview_cv_ui,
    download_cv_ui,
    upload_cv_ui,
    delete_cv_ui,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

EMAIL_RE = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.I)


# ---------------------- Helper utilities ----------------------

def _valid_email(addr: str) -> bool:
    """Return True if email is valid format."""
    return bool(EMAIL_RE.match((addr or "").strip()))


def _search_candidates_all_fields(q: str) -> List[Dict[str, Any]]:
    """
    Try a broader search across candidate_id, name, email, phone, and JSON form_data.
    If anything fails, fallback to the simpler name-based helper.
    """
    q = (q or "").strip()
    if not q:
        return []

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
                LIMIT 500
                """,
                (like, like, like, like, like),
            )
            rows = cur.fetchall()
        conn.close()

        results = []
        for r in rows:
            results.append(
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
        return results
    except Exception as exc:
        logger.exception("Full-field search failed, falling back to name search.")
        return find_candidates_by_name(q)


def _send_candidate_code(email: str, candidate_id: str) -> Tuple[bool, str]:
    """
    Send candidate code by SMTP if configured; otherwise print to console.
    Returns (success, message)
    """
    email = (email or "").strip()
    if not _valid_email(email):
        return False, "Invalid email address."

    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    from_email = os.getenv("FROM_EMAIL", "no-reply@brv.local")

    subject = "Your BRV Candidate Code"
    body = (
        f"Hello,\n\nYour candidate code is: {candidate_id}\n\n"
        "Use this code to view/update your application if permitted.\n\nThanks,\nBRV Recruitment\n"
    )

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
            logger.exception("SMTP send failed")
            return False, f"SMTP error: {e}"
    else:
        # fallback: console print
        logger.info("SMTP not configured — printing candidate code to console")
        print("---- Candidate Code Email (console fallback) ----")
        print("To:", email)
        print(body)
        print("-----------------------------------------------")
        return True, "Printed to console (SMTP not configured)."


def _parse_form_data(field: Optional[Any]) -> Dict[str, Any]:
    """
    Safely parse form_data values which might be stored as JSON string or dict.
    """
    if field is None:
        return {}
    if isinstance(field, dict):
        return field
    if isinstance(field, str):
        try:
            return json.loads(field)
        except Exception:
            # try simple key=value lines
            res = {}
            for line in field.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    res[k.strip()] = v.strip()
            return res
    return {}


# ---------------------- Receptionist UI ----------------------

def receptionist_view():
    st.header("Receptionist Panel")

    # fetch logged-in user from session
    current_user = st.session_state.get("user")
    if not current_user:
        st.error("No active user session. Please log in.")
        return

    user_id = current_user.get("id")
    if not user_id:
        st.error("Invalid user session (missing id).")
        return

    # fetch permissions (single call)
    try:
        user_perms = get_user_permissions(user_id) or {}
    except Exception as e:
        logger.exception("Failed to read user permissions")
        st.error("Failed to read permissions. Contact admin.")
        return

    # Search / list candidates
    st.subheader("Search Candidates")
    q = st.text_input("Search by candidate code, name, email, phone, or any form value", placeholder="Type to search…")
    if q.strip():
        rows = _search_candidates_all_fields(q.strip())
    else:
        try:
            rows = get_all_candidates()
        except Exception as e:
            logger.exception("Unable to fetch candidates")
            rows = []

    st.caption(f"{len(rows)} result(s).")

    # Present each candidate
    for c in rows:
        # defensive keys
        cid = c.get("candidate_id") or c.get("candidate_code") or c.get("id")
        display_name = c.get("name") or "(no name)"
        with st.expander(f"{display_name} — {cid}", expanded=False):
            st.write(f"**Email:** {c.get('email','—')}")
            st.write(f"**Phone:** {c.get('phone','—')}")
            st.write(f"**Created:** {c.get('created_at','—')}")

            # Show parsed application data if present
            if c.get("form_data"):
                parsed = _parse_form_data(c["form_data"])
                if parsed:
                    with st.expander("Application Data", expanded=False):
                        for k, v in parsed.items():
                            st.write(f"- **{k}**: {v}")

            # ---------- CV section ----------
            st.markdown("#### Resume / CV")
            if user_perms.get("can_view_cv", False):
                try:
                    cv_file, cv_filename = get_candidate_cv(cid)
                    if cv_file:
                        st.success(f"✅ CV found ({cv_filename or 'unnamed'})")
                        # preview is allowed for viewers
                        try:
                            preview_cv_ui(cid)
                        except Exception as e:
                            logger.exception("preview_cv_ui failed")
                            st.warning("Preview unavailable.")
                        # download/edit controls for those with rights
                        if user_perms.get("can_edit_cv", False) or user_perms.get("can_download_cv", False):
                            try:
                                download_cv_ui(cid)
                            except Exception:
                                # older code may not have download function gracefully
                                pass
                        # delete CV option if allowed to edit
                        if user_perms.get("can_edit_cv", False):
                            if st.button(f"Delete CV for {cid}", key=f"delcv_{cid}"):
                                try:
                                    delete_cv_ui(cid)
                                    st.success("Requested CV deletion (check drive).")
                                except Exception as e:
                                    st.error(f"Failed to delete CV: {e}")
                    else:
                        st.info("No CV uploaded yet.")
                        if user_perms.get("can_upload_cv", False):
                            try:
                                upload_cv_ui(cid)
                            except Exception as e:
                                logger.exception("upload_cv_ui failed")
                                st.warning("Upload UI not available.")
                        else:
                            st.caption("You don't have upload permission.")
                except Exception:
                    logger.exception("Error fetching CV for candidate")
                    st.error("Error fetching CV.")
            else:
                st.warning("🚫 You don't have permission to view CVs.")

            # ---------- Receptionist Assessment ----------
            st.markdown("#### Receptionist Assessment")
            # We gate saving assessments behind candidate-edit permission to keep control
            if user_perms.get("can_edit_candidates", False) or current_user.get("role") in ("ceo", "admin"):
                with st.form(f"receptionist_assessment_{cid}"):
                    speed = st.number_input("Speed Test (WPM)", min_value=0, key=f"speed_{cid}")
                    accuracy = st.number_input("Accuracy Test (%)", min_value=0, max_value=100, key=f"accuracy_{cid}")
                    work_commitment = st.text_area("Work Commitment", key=f"work_{cid}")
                    english = st.text_area("English Understanding", key=f"english_{cid}")
                    comments = st.text_area("Comments", key=f"comments_{cid}")
                    submitted = st.form_submit_button("💾 Save Assessment")
                    if submitted:
                        try:
                            ok = save_receptionist_assessment(cid, int(speed), int(accuracy), work_commitment, english, comments)
                            if ok:
                                st.success("Assessment saved successfully.")
                            else:
                                st.error("Failed to save assessment.")
                        except Exception:
                            logger.exception("Failed saving receptionist assessment")
                            st.error("Failed to save assessment.")
            else:
                st.info("You do not have permission to record receptionist assessments.")

            # ---------- Quick Permission / Edit Actions ----------
            st.markdown("---")
            st.caption("Quick Actions")

            col1, col2, col3, col4 = st.columns(4)

            # Allow edit by code (sets can_edit flag on candidate)
            with col1:
                if st.button("Allow Edit (by code only)", key=f"allow_{cid}"):
                    try:
                        ok = _set_candidate_edit_flag(cid, True)
                        (st.success if ok else st.error)("Permission updated." if ok else "Failed to update.")
                    except Exception:
                        st.exception("Error setting candidate permission")
                        st.error("Failed to update permission.")

            # Revoke edit
            with col2:
                if st.button("Revoke Edit", key=f"revoke_{cid}"):
                    try:
                        ok = _set_candidate_edit_flag(cid, False)
                        (st.success if ok else st.error)("Permission updated." if ok else "Failed to update.")
                    except Exception:
                        logger.exception("Error revoking edit permission")
                        st.error("Failed to update permission.")

            # Email candidate code
            with col3:
                if st.button("Email Candidate Code", key=f"code_{cid}"):
                    ok, msg = _send_candidate_code(c.get("email", ""), cid)
                    (st.success if ok else st.error)(msg)

            # Delete candidate
            with col4:
                if user_perms.get("can_delete_candidate", False) or current_user.get("role") in ("ceo", "admin"):
                    confirm_key = f"confirm_delete_{cid}"
                    confirm_delete = st.checkbox(f"Confirm Delete {cid}", key=confirm_key)
                    if confirm_delete and st.button("🗑️ Delete Candidate", key=f"delete_{cid}"):
                        try:
                            if delete_candidate_by_actor(cid, user_id):
                                st.success("Candidate deleted.")
                                st.experimental_rerun()
                            else:
                                st.error("Delete failed or insufficient permission.")
                        except Exception:
                            logger.exception("delete_candidate_by_actor failed")
                            st.error("Failed to delete candidate.")
                else:
                    st.caption("No permission to delete candidate.")

    # -------------- Divider / Create / Edit --------------
    st.markdown("---")
    st.subheader("Create / Update Candidate (Front Desk Tools)")

    # Create candidate UI - requires add permission
    if user_perms.get("can_add_candidates", False) or current_user.get("role") in ("ceo", "admin"):
        st.write("Create a new candidate record and optionally email their code.")
        c1, c2 = st.columns(2)
        with c1:
            new_name = st.text_input("Full Name", key="new_name")
            new_phone = st.text_input("Phone", key="new_phone")
        with c2:
            new_email = st.text_input("Email", key="new_email")
            created_by = current_user.get("email", "receptionist")

        if st.button("Create Candidate"):
            if not new_name.strip():
                st.error("Name is required.")
            elif new_email and not _valid_email(new_email):
                st.error("Invalid email.")
            else:
                try:
                    # create_candidate_in_db signature in your code may differ; adapt as needed
                    created = create_candidate_in_db(
                        candidate_id=None,  # allow DB helper to generate if it does, else pass a unique code
                        name=new_name.strip(),
                        address="",
                        dob=None,
                        caste="",
                        email=new_email.strip(),
                        phone=new_phone.strip(),
                        form_data={},
                        created_by=created_by,
                    )
                    if created:
                        assigned_code = created.get("candidate_id") if isinstance(created, dict) else str(created)
                        st.success(f"Candidate created. Code: {assigned_code}")
                        if new_email:
                            ok, msg = _send_candidate_code(new_email, assigned_code)
                            (st.success if ok else st.error)(msg)
                    else:
                        st.error("Failed to create candidate (DB returned nothing).")
                except Exception:
                    logger.exception("Error creating candidate")
                    st.error("An error occurred when creating the candidate.")
    else:
        st.warning("You do not have permission to create candidates.")

    # Edit by code - basic patch tool for front desk
    st.markdown("---")
    st.write("Quick Edit by Candidate Code (for small fixes)")
    edit_code = st.text_input("Candidate Code", key="edit_code")
    edit_field = st.text_input("Field to set (e.g. name, email, phone)", key="edit_field")
    edit_value = st.text_input("New value", key="edit_value")

    if st.button("Apply Quick Edit"):
        if not edit_code.strip() or not edit_field.strip():
            st.error("Code and field are required.")
        else:
            # Build a patch: form_data or top-level field supported
            updates = {}
            if edit_field in ("name", "email", "phone"):
                updates[edit_field] = edit_value
            else:
                # treat as form_data patch
                updates["form_patch"] = {edit_field: edit_value}
            try:
                ok = update_candidate_form_data(edit_code, updates)
                if ok:
                    st.success("Update applied.")
                else:
                    st.error("Update failed (check code & permissions).")
            except Exception:
                logger.exception("Quick edit failed")
                st.error("Error applying update.")

    st.caption("Note: Candidate edits may require explicit permission. Front desk should only use quick edits for small fixes.")


# ---------------------- Internal small helpers ----------------------

def _set_candidate_edit_flag(candidate_id: str, allow: bool) -> bool:
    """
    Helper that updates the 'can_edit' column on candidates.
    This mirrors earlier inline logic — kept small and local for receptionist usage.
    """
    try:
        conn = get_conn()
        with conn, conn.cursor() as cur:
            cur.execute("UPDATE candidates SET can_edit=%s, updated_at = CURRENT_TIMESTAMP WHERE candidate_id=%s",
                        (allow, candidate_id))
            ok = cur.rowcount > 0
        conn.close()
        return ok
    except Exception:
        logger.exception("Failed to set candidate edit flag")
        return False
