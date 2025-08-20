# receptionist.py
import os
import re
import smtplib
from email.message import EmailMessage
from typing import List, Dict, Any

import streamlit as st
from db_postgres import (
    get_conn,
    find_candidates_by_name,
    update_candidate_form_data,
    create_candidate_in_db,
    get_all_candidates,
    get_user_permissions
    get_candidate_cv,
    delete_candidate_by_actor,
    save_receptionist_assessment,   # ✅ add this
)
from drive_and_cv_views import preview_cv_ui, download_cv_ui # ✅ reuse CV UI

EMAIL_RE = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.I)


# --------- helpers

def _valid_email(addr: str) -> bool:
    return bool(EMAIL_RE.match(addr or ""))


def _search_candidates_all_fields(q: str) -> List[Dict[str, Any]]:
    """Search across many columns. Falls back to name search if anything fails."""
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
        results = []
        for r in rows:
            results.append({
                "id": r[0],
                "candidate_id": r[1],
                "name": r[2],
                "email": r[3],
                "phone": r[4],
                "created_at": r[5],
                "form_data": r[6],
            })
        return results
    except Exception:
        return find_candidates_by_name(q)


def _set_candidate_permission(candidate_id: str, can_edit: bool) -> bool:
    """Minimal local implementation if the DB helper is missing."""
    conn = get_conn()
    with conn, conn.cursor() as cur:
        cur.execute("UPDATE candidates SET can_edit=%s WHERE candidate_id=%s", (can_edit, candidate_id))
        ok = cur.rowcount > 0
    conn.close()
    return ok


def _send_candidate_code(email: str, candidate_id: str) -> tuple[bool, str]:
    """Email candidate code using SMTP env (same pattern as you used in auth)."""
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
        # fallback to console
        print("---- Candidate Code Email (console fallback) ----")
        print("To:", email)
        print(body)
        print("-----------------------------------------------")
        return True, "Printed to console (SMTP not configured)."


# --------- main view

def receptionist_view():
    st.header("Receptionist — Candidate Management")

    # Search section
    st.subheader("Search Candidates (all fields)")
    q = st.text_input("Search by candidate code, name, email, phone, or any form value", placeholder="Type to search…")
    if q.strip():
        rows = _search_candidates_all_fields(q.strip())
    else:
        rows = get_all_candidates()

    st.caption(f"{len(rows)} result(s).")
    for c in rows:
        with st.expander(f"{c.get('name','(no name)')} — {c.get('candidate_id')}", expanded=False):
            st.write(f"**Email:** {c.get('email','—')}")
            st.write(f"**Phone:** {c.get('phone','—')}")
            st.write(f"**Created:** {c.get('created_at','—')}")

            # --- CV section ---
            # check permission
            perms = get_user_permissions(current_user["id"])
            if not perms.get("can_view_cvs", False):
                st.warning("You do not have permission to view CVs.")
                return
            st.markdown("### Resume / CV")
            try:
                cv_file, cv_filename = get_candidate_cv(c["candidate_id"])
                if cv_file:
                    st.success(f"✅ CV found ({cv_filename or 'unnamed'})")
                    preview_cv_ui(c["candidate_id"])   # ✅ preview + download
                    delete_cv_ui(c["candidate_id"])
                else:
                    st.info("No CV uploaded yet.")
                    upload_cv_ui(c["candidate_id"])
            except Exception as e:
                st.error(f"Error fetching CV: {e}")

            # --- Application data ---
            if c.get("form_data"):
                try:
                    data = c["form_data"]
                    if isinstance(data, str):
                        import json
                        data = json.loads(data)
                    with st.expander("Application Data", expanded=False):
                        for k, v in (data or {}).items():
                            st.write(f"- **{k}**: {v}")
                except Exception:
                    pass
            # --- Receptionist Assessment ---
            st.markdown("### Receptionist Assessment")
            with st.form(f"receptionist_assessment_{c['candidate_id']}"):
                speed = st.number_input("Speed Test (WPM)", min_value=0, key=f"speed_{c['candidate_id']}")
                accuracy = st.number_input("Accuracy Test (%)", min_value=0, max_value=100, key=f"accuracy_{c['candidate_id']}")
                work_commitment = st.text_area("Work Commitment", key=f"work_{c['candidate_id']}")
                english = st.text_area("English Understanding", key=f"english_{c['candidate_id']}")
                comments = st.text_area("Comments", key=f"comments_{c['candidate_id']}")
                submitted = st.form_submit_button("💾 Save Assessment")

            if submitted:
                ok = save_receptionist_assessment(
                    c["candidate_id"], speed, accuracy, work_commitment, english, comments
                )
                if ok:
                    st.success("Assessment saved successfully.")
                else:
                    st.error("Failed to save assessment.")

            # --- Permissions & Quick Actions ---
            st.markdown("---")
            st.caption("Quick Actions")

            col1, col2, col3, col4 = st.columns(4)  # add col4 for delete
            with col1:
                if st.button("Allow Edit (by code only)", key=f"allow_{c['candidate_id']}"):
                    if _set_candidate_permission(c["candidate_id"], True):
                        st.success("Permission granted.")
                    else:
                        st.error("Failed to update permission.")
            with col2:
                if st.button("Revoke Edit", key=f"revoke_{c['candidate_id']}"):
                    if _set_candidate_permission(c["candidate_id"], False):
                        st.success("Permission revoked.")
                    else:
                        st.error("Failed to update permission.")
            with col3:
                if st.button("Email Candidate Code", key=f"code_{c['candidate_id']}"):
                    ok, msg = _send_candidate_code(c.get("email",""), c["candidate_id"])
                    (st.success if ok else st.error)(msg)
            with col4:
                # 🔴 Delete Candidate (requires permission)
                current_user = st.session_state.get("user")
                if current_user and current_user.get("can_delete_records", False):
                    if st.button("🗑️ Delete Candidate", key=f"delcand_{c['candidate_id']}"):
                        user_id = current_user.get("id")
                        if user_id and delete_candidate_by_actor(c["candidate_id"], user_id):
                            st.success("Candidate deleted successfully.")
                            st.rerun()
                        else:
                            st.error("Failed to delete candidate.")

    st.divider()

    # Minimal create/edit tools (optional quick fixes)
    st.subheader("Create/Update Application (front-desk help)")
    cc, ce = st.columns(2)
    with cc:
        name = st.text_input("Full Name", key="new_name")
        email = st.text_input("Email", key="new_email")
        phone = st.text_input("Phone", key="new_phone")
        if st.button("Create Candidate"):
            if not _valid_email(email):
                st.error("Please enter a valid email.")
            else:
                try:
                    cid = create_candidate_in_db(name=name, email=email, phone=phone)
                    if cid:
                        st.success(f"Candidate created. Code: {cid}")
                        ok, msg = _send_candidate_code(email, cid)
                        (st.success if ok else st.warning)(msg)
                    else:
                        st.error("Failed to create candidate.")
                except Exception as e:
                    st.error(f"Error: {e}")

    with ce:
        st.caption("Edit by Candidate Code (name can be changed; permission required)")
        code = st.text_input("Candidate Code", key="edit_code")
        new_name = st.text_input("New Name (optional)", key="edit_name")
        form_json = st.text_area("Form JSON patch (optional)", placeholder='{"skills":"Excel, Email"}')
        if st.button("Apply Update"):
            try:
                updates = {}
                if new_name.strip():
                    updates["name"] = new_name.strip()
                if form_json.strip():
                    import json
                    updates["form_patch"] = json.loads(form_json)
                if not updates:
                    st.info("Nothing to update.")
                else:
                    ok = update_candidate_form_data(code, updates)
                    if ok:
                        st.success("Update applied.")
                    else:
                        st.error("Failed to update (check permission or code).")
            except Exception as e:
                st.error(f"Error: {e}")

    st.caption("Note: Editing only requires the candidate code if permission is granted.")
