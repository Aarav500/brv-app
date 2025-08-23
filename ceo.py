# ceo.py
"""
CEO Control Panel
- Manage user permissions (can_view_cvs, can_delete_records, can_grant_delete)
- Force password reset (UI only to set flag)
- Manage candidates (view details, download CV, delete candidate)
- Displays candidate stats
"""

import streamlit as st
from typing import Optional, Dict, Any, List
from datetime import datetime

# Import DB helpers -- ensure these exist in your db_postgres.py
from db_postgres import (
    get_all_users_with_permissions,
    update_user_permissions,
    get_candidate_cv_secure,
    save_candidate_cv,
    clear_candidate_cv,
    get_user_permissions,
    get_candidate_statistics,
    get_all_candidates,
    delete_candidate,
    set_candidate_permission,
    get_candidate_history,
    set_user_permission,
)

# Import auth helpers
from auth import require_login, get_current_user

# -------------------------
# Helpers
# -------------------------
def _format_datetime(v) -> str:
    if not v:
        return "N/A"
    if isinstance(v, str):
        try:
            # try parsing isoformat
            dt = datetime.fromisoformat(v)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return v
    try:
        return v.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(v)


def _render_user_permissions_block(user_row: Dict[str, Any], index_key: str):
    """
    Render the permission checkboxes for a single user (returns new permission values as dict).
    This does not persist - caller should call update_user_permissions.
    """
    # We will use unique keys so streamlit doesn't share state between users
    base = index_key
    # Show minimal info (hide the "(ceo)" token)
    st.markdown(f"**{user_row.get('email','(no email)')}**")
    # optionally show role but hide the literal "(ceo)" suffix if you prefer:
    role = (user_row.get("role") or "").strip()
    if role and role.lower() != "ceo":
        st.caption(f"Role: {role}")

    st.write(f"ID: {user_row.get('id')}  |  Created: {_format_datetime(user_row.get('created_at'))}")
    st.write(f"Force Password Reset: {user_row.get('force_password_reset', False)}")

    c1 = st.checkbox("Can View CVs", value=bool(user_row.get("can_view_cvs", False)), key=f"{base}_cv")
    c2 = st.checkbox("Can Delete Candidate Records", value=bool(user_row.get("can_delete_records", False)),
                     key=f"{base}_del")

    return {
        "can_view_cvs": bool(c1),
        "can_delete_records": bool(c2),
        # no grant-delete control in UI anymore
    }

def _render_candidate_summary(c: Dict[str, Any]):
    """Render candidate summary fields in a friendly way (no raw JSON dumps)."""
    st.write(f"**Name:** {c.get('name') or '—'}")
    st.write(f"**Candidate ID:** {c.get('candidate_id') or c.get('id')}")
    st.write(f"**Email:** {c.get('email') or '—'}")
    st.write(f"**Phone:** {c.get('phone') or '—'}")
    st.write(f"**Created At:** {_format_datetime(c.get('created_at'))}")
    st.write(f"**Updated At:** {_format_datetime(c.get('updated_at'))}")
    st.write(f"**Can Edit (candidate):** {bool(c.get('can_edit', False))}")
    # If there's an embedded form_data, show selected friendly fields
    form = c.get("form_data") or {}
    if isinstance(form, dict) and form:
        st.markdown("**Application summary**")
        # present selected fields only for readability
        st.write(f"- Age / DOB: {form.get('dob','N/A')}")
        st.write(f"- Highest qualification: {form.get('highest_qualification','N/A')}")
        st.write(f"- Work experience: {form.get('work_experience','N/A')}")
        st.write(f"- Ready for holidays: {form.get('ready_festivals','N/A')}")
        st.write(f"- Ready for late nights: {form.get('ready_late_nights','N/A')}")


def _render_interview_history(history: List[Dict[str, Any]]):
    if not history:
        st.info("No interview history available.")
        return

    for idx, ev in enumerate(history):
        with st.container():
            st.markdown(f"**{idx + 1}. Interview**")
            when = ev.get("created_at") or ev.get("at") or ev.get("scheduled_at")
            interviewer = ev.get("actor") or ev.get("interviewer")
            result = None
            notes = None

            raw_details = ev.get("details") or ev.get("notes") or ev.get("action") or ""
            if isinstance(raw_details, dict):
                result = raw_details.get("result") or raw_details.get("status")
                notes = raw_details.get("notes") or raw_details.get("comment")
            elif isinstance(raw_details, str):
                notes = raw_details

            st.write(f"- **When:** {_format_datetime(when)}")
            if interviewer:
                st.write(f"- **By:** {interviewer}")
            if result:
                st.write(f"- **Result:** {result}")
            if notes:
                md = str(notes).replace("\r\n", "\n").replace("\n", "  \n")
                st.markdown(f"- **Details:**  \n{md}")
            st.markdown("---")


# -------------------------
# Main CEO panel
# -------------------------
def show_ceo_panel():
    require_login()
    user = get_current_user(refresh=True)
    role = (user.get("role") or "").lower()

    st.title("CEO Dashboard")
    st.caption("Candidate statistics and candidate management (no user operations here).")
    # -- Top-level stats --
    try:
        stats = get_candidate_statistics()
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        with col_s1:
            st.metric("Total Candidates", stats.get("total_candidates", 0))
        with col_s2:
            st.metric("Candidates Today", stats.get("candidates_today", 0))
        with col_s3:
            st.metric("Interviews", stats.get("total_interviews", 0))
        with col_s4:
            st.metric("Assessments", stats.get("total_assessments", 0))
    except Exception:
        # non-fatal - continue
        pass

    st.markdown("---")



        # Focused panel to grant/revoke Interview Access for Interviewers
            with st.expander("Interviewer Access Management", expanded=True):
            st.caption("Grant or revoke interview access (CV viewing) for interviewer accounts.")
            interviewers = [u for u in (users or []) if (u.get("role") or "").lower() == "interviewer"]
            if not interviewers:
                st.info("No interviewer accounts found.")
            else:
                for iu in interviewers:
                    colA, colB, colC = st.columns([3, 1, 1])
                    with colA:
                        st.write(iu.get("email"))
                        st.caption(f"User ID: {iu.get('id')}")
                    with colB:
                        current = bool(iu.get("can_view_cvs", False))
                        new_val = st.toggle("Interview Access", value=current, key=f"ivacc_{iu.get('id')}")
                    with colC:
                        if st.button("Save", key=f"save_ivacc_{iu.get('id')}"):
                            try:
                                ok = set_user_permission(iu.get("id"), can_view=bool(new_val))
                                if ok:
                                    st.success("Updated.")
                                    st.rerun()
                                else:
                                    st.error("No change or failed to update.")
                            except Exception as e:
                                st.error(f"Error updating: {e}")

        st.markdown("---")
    else:
        st.info("User management panel is limited to admins and CEOs.")

    # --- Candidate Management (visible to any logged-in user, but delete gated) ---
    st.header("Candidate Management")
    # filters & search
    q_col1, q_col2, q_col3 = st.columns([3, 1, 1])
    with q_col1:
        search_q = st.text_input("Search candidates by name / email / candidate_id (partial matches allowed)")
    with q_col2:
        refresh_btn = st.button("Refresh List")
        if refresh_btn:
            st.rerun()
    with q_col3:
        # show only those without CV or other quick filters if needed
        show_only_no_cv = st.checkbox("Only without CV", value=False, key="filter_no_cv")

    # Load candidates
    try:
        candidates = get_all_candidates() or []
    except Exception as e:
        st.error(f"Failed to load candidates: {e}")
        candidates = []

    # apply filter
    filtered = []
    sq = (search_q or "").strip().lower()
    for c in candidates:
        # search in name/email/candidate_id
        if sq:
            if (
                (c.get("name") or "").lower().find(sq) != -1
                or (c.get("email") or "").lower().find(sq) != -1
                or (c.get("candidate_id") or "").lower().find(sq) != -1
            ):
                filtered.append(c)
        else:
            filtered.append(c)

    if show_only_no_cv:
        filtered = [x for x in filtered if not x.get("cv_file") and not x.get("resume_link")]

    if not filtered:
        st.info("No candidates match your criteria.")
        return

    # For each candidate, present an expander with summary and actions
    for c in filtered:
        candidate_label = f"{c.get('name') or 'Unnamed'} — {c.get('candidate_id') or c.get('id')}"
        with st.expander(candidate_label, expanded=False):
            # split into left (details) and right (actions)
            left, right = st.columns([3, 1])
            with left:
                # Candidate details
                try:
                    _render_candidate_summary(c)
                except Exception as e:
                    st.error("Error rendering candidate details (truncated).")
                    st.write(f"Name: {c.get('name', '—')}")
                    st.write(f"Candidate ID: {c.get('candidate_id', '—')}")
                    st.write(f"Created At: {_format_datetime(c.get('created_at'))}")
                    st.caption("Full record available in logs if needed.")
                    import logging
                    logging.exception("ceo: render candidate error: %s", e)

                # Candidate CV (secure + permission aware)
                try:
                    cid = c.get("candidate_id")
                    # force permission refresh so revokes apply instantly
                    user = get_current_user(refresh=True)
                    actor_id = user.get("id") if user else 0

                    cv_bytes, cv_name, reason = get_candidate_cv_secure(cid, actor_id)

                    if reason == "no_permission":
                        st.warning("❌ You don’t have permission to view CVs for this candidate.")
                    elif reason == "not_found":
                        st.info("No CV uploaded yet.")
                    elif cv_bytes:
                        st.download_button(
                            "📄 Download CV",
                            data=cv_bytes,
                            file_name=cv_name or f"{cid}_cv.bin",
                        )

                # Interview history
                try:
                    history = get_candidate_history(c.get("candidate_id"))
                    _render_interview_history(history)
                except Exception as e:
                    st.write("Interview history: (error fetching)", e)

            with right:
                st.markdown("### Actions")
                user = get_current_user(refresh=True)
                role_lower = (user.get("role") or "").lower()
                _perms = get_user_permissions(user.get("id")) or {}
                can_delete_records = role_lower in ("admin", "ceo") or bool(_perms.get("can_delete_records"))
                if not can_delete_records:
                    st.info("🚫 You don’t have permission to delete this record.")
                else:
                    if st.button("🗑️ Delete Candidate", key=f"del_btn_{c.get('candidate_id')}"):
                        try:
                            ok, reason = delete_candidate(c.get("candidate_id"), user["id"])
                            if ok:
                                st.success("Candidate deleted.")
                                st.rerun()
                            elif reason == "no_permission":
                                st.error("❌ You don’t have permission to delete this record.")
                            elif reason == "not_found":
                                st.warning("Candidate already deleted.")
                            else:
                                st.error("Delete failed (DB error).")
                        except Exception as e:
                            st.error(f"Delete failed: {e}")

                # Toggle can_edit for candidate from CEO, optional
                if st.button("Toggle Candidate Edit Permission", key=f"toggle_edit_{c.get('candidate_id')}"):
                    try:
                        current_can_edit = bool(c.get("can_edit", False))
                        # flip
                        new_val = not current_can_edit
                        set_candidate_permission(c.get("candidate_id"), new_val)
                        st.success(f"Set candidate can_edit = {new_val}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to toggle edit permission: {e}")

                # Small hint area
                st.caption("Delete requires permission. Toggle candidate edit to allow candidate to update their record.")

def show_user_management_panel():
    """User management only (CEO/Admin). Route to this from a separate menu item."""
    require_login()
    current_user = get_current_user(refresh=True)
    role = (current_user.get("role") or "").lower()
    if role not in ("ceo", "admin"):
        st.error("You do not have permission to view this page.")
        st.stop()

    st.title("User Management")
    st.caption("Manage user permissions. (No candidate operations here.)")

    users = get_all_users_with_permissions() or []
    if not users:
        st.info("No users found.")
        return

    for u in users:
        with st.expander(u.get("email") or "(no email)"):
            idx_key = f"user_{u.get('id')}"
            new_perms = _render_user_permissions_block(u, idx_key)
            if st.button("Update Permissions", key=f"saveperm_{u.get('id')}"):
                ok = update_user_permissions(u.get("id"), new_perms)
                if ok:
                    st.success("Permissions updated.")
                    st.rerun()
                else:
                    st.error("No change.")

    # End of show_ceo_panel
