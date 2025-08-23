# ceo.py
"""
CEO Control Panel (refactored)

- Candidate statistics and candidate management are ONLY here.
- User Management (below) only edits user permissions (no candidate ops).
- CV preview works (PDF inline preview when permitted).
- Toggling candidate edit permission updates immediately and reflects in the UI.
- Interview history displayed in a friendly, consistent card-like layout.
"""

import base64
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import io

import streamlit as st
import streamlit.components.v1 as components

# Import DB helpers -- keep your existing function names/signatures
from db_postgres import (
    get_all_users_with_permissions,
    update_user_permissions,
    get_candidate_cv_secure,
    get_user_permissions,
    get_candidate_statistics,
    get_all_candidates,
    delete_candidate,
    set_candidate_permission,
    get_candidate_history,
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
            dt = datetime.fromisoformat(v)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return v
    try:
        return v.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(v)


def _safe_lower(s: Optional[str]) -> str:
    return (s or "").lower()


def _embed_pdf(bytes_data: bytes, width: str = "100%", height: int = 700) -> None:
    """Embed a PDF in the page using an iframe (base64)."""
    if not bytes_data:
        st.info("No PDF data to preview.")
        return
    b64 = base64.b64encode(bytes_data).decode("utf-8")
    src = f"data:application/pdf;base64,{b64}"
    html = f"""
    <iframe src="{src}" width="{width}" height="{height}" style="border: none;"></iframe>
    """
    components.html(html, height=height + 20)


def _preview_text_file(bytes_data: bytes, max_chars: int = 40_000) -> None:
    """Show a plain-text preview (trimmed)"""
    try:
        text = bytes_data.decode("utf-8", errors="replace")
    except Exception:
        text = str(bytes_data)[:max_chars]
    if len(text) > max_chars:
        st.code(text[:max_chars] + "\n\n... (truncated)", language=None)
    else:
        st.code(text, language=None)


def _render_user_permissions_block(user_row: Dict[str, Any], index_key: str):
    """
    Render the permission checkboxes for a single user (returns new permission values as dict).
    This does not persist automatically — caller persists via update_user_permissions.
    """
    base = index_key
    st.markdown(f"**{user_row.get('email','(no email)')}**")
    role = (user_row.get("role") or "").strip()
    if role and role.lower() != "ceo":
        st.caption(f"Role: {role}")

    st.write(f"ID: {user_row.get('id')}  |  Created: {_format_datetime(user_row.get('created_at'))}")
    st.write(f"Force Password Reset: {bool(user_row.get('force_password_reset', False))}")

    c1 = st.checkbox("Can View CVs", value=bool(user_row.get("can_view_cvs", False)), key=f"{base}_cv")
    c2 = st.checkbox("Can Delete Candidate Records", value=bool(user_row.get("can_delete_records", False)),
                     key=f"{base}_del")

    return {
        "can_view_cvs": bool(c1),
        "can_delete_records": bool(c2),
    }


def _render_candidate_summary(c: Dict[str, Any]):
    """Render candidate summary fields in a friendly way (no raw JSON dumps)."""
    st.markdown(f"### {c.get('name') or '—'}")
    st.write(f"**Candidate ID:** {c.get('candidate_id') or c.get('id')}")
    st.write(f"**Email:** {c.get('email') or '—'}")
    st.write(f"**Phone:** {c.get('phone') or '—'}")
    st.write(f"**Created At:** {_format_datetime(c.get('created_at'))}")
    st.write(f"**Updated At:** {_format_datetime(c.get('updated_at'))}")
    st.write(f"**Can Edit (candidate):** {bool(c.get('can_edit', False))}")

    form = c.get("form_data") or {}
    if isinstance(form, dict) and form:
        st.markdown("**Application summary**")
        st.write(f"- Age / DOB: {form.get('dob','N/A')}")
        st.write(f"- Highest qualification: {form.get('highest_qualification','N/A')}")
        st.write(f"- Work experience: {form.get('work_experience','N/A')}")
        st.write(f"- Ready for holidays: {form.get('ready_festivals','N/A')}")
        st.write(f"- Ready for late nights: {form.get('ready_late_nights','N/A')}")


def _render_interview_history(history: List[Dict[str, Any]]):
    """Show interviews as clean 'cards' with preserved line breaks."""
    if not history:
        st.info("No interview history available.")
        return

    for idx, ev in enumerate(history):
        with st.container():
            st.markdown(f"**Interview #{idx + 1}**")
            # Use two-column visual layout
            left, right = st.columns([3, 1])
            when = ev.get("created_at") or ev.get("at") or ev.get("scheduled_at")
            interviewer = ev.get("actor") or ev.get("interviewer") or "—"
            raw_details = ev.get("details") or ev.get("notes") or ev.get("action") or ""
            result = None
            notes = None

            if isinstance(raw_details, dict):
                result = raw_details.get("result") or raw_details.get("status")
                notes = raw_details.get("notes") or raw_details.get("comment") or raw_details
            elif isinstance(raw_details, str):
                notes = raw_details

            with left:
                st.write(f"- **When:** {_format_datetime(when)}")
                st.write(f"- **By:** {interviewer}")
                if result:
                    st.write(f"- **Result:** {result}")

                if notes:
                    # preserve newlines by replacing single newline with markdown line break
                    if isinstance(notes, dict):
                        st.markdown("**Details:**")
                        for k, v in notes.items():
                            st.write(f"- {k}: {v}")
                    else:
                        md = str(notes).replace("\r\n", "\n").replace("\n", "  \n")
                        st.markdown(f"**Details:**  \n{md}")

            with right:
                # small metadata panel
                ev_actor_id = ev.get("actor_id") or ev.get("user_id") or "—"
                st.caption(f"Event ID: {ev.get('id', '—')}")
                st.caption(f"Actor ID: {ev_actor_id}")

            st.markdown("---")


def _detect_mimetype_from_name(name: Optional[str]) -> str:
    if not name:
        return "application/octet-stream"
    lname = name.lower()
    if lname.endswith(".pdf"):
        return "application/pdf"
    if lname.endswith(".txt") or lname.endswith(".log") or lname.endswith(".md"):
        return "text/plain"
    if lname.endswith(".docx"):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if lname.endswith(".doc"):
        return "application/msword"
    # fallback
    return "application/octet-stream"


# -------------------------
# Main CEO panel
# -------------------------
def show_ceo_panel():
    require_login()
    user = get_current_user(refresh=True)
    role = _safe_lower(user.get("role"))

    if role not in ("ceo", "admin"):
        st.error("You do not have permission to view this page.")
        st.stop()

    st.title("CEO Dashboard")
    st.caption("Candidate statistics and candidate management.")

    # -- Top-level stats --
    try:
        stats = get_candidate_statistics() or {}
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        with col_s1:
            st.metric("Total Candidates", stats.get("total_candidates", 0))
        with col_s2:
            st.metric("Candidates Today", stats.get("candidates_today", 0))
        with col_s3:
            st.metric("Interviews", stats.get("total_interviews", 0))
        with col_s4:
            st.metric("Assessments", stats.get("total_assessments", 0))
    except Exception as e:
        st.warning("Unable to load statistics.")
        st.write(e)

    st.markdown("---")

    # --- Candidate Management ---
    st.header("Candidate Management")
    q_col1, q_col2, q_col3 = st.columns([3, 1, 1])
    with q_col1:
        search_q = st.text_input("Search candidates by name / email / candidate_id (partial matches allowed)", key="ceo_search")
    with q_col2:
        if st.button("Refresh List"):
            st.rerun()
    with q_col3:
        show_only_no_cv = st.checkbox("Only without CV", value=False, key="ceo_filter_no_cv")

    try:
        candidates = get_all_candidates() or []
    except Exception as e:
        st.error(f"Failed to load candidates: {e}")
        candidates = []

    # apply filter
    filtered = []
    sq = (search_q or "").strip().lower()
    for c in candidates:
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

    # Ensure session_state keys exist for preview toggles
    for c in filtered:
        cid = c.get("candidate_id") or str(c.get("id"))
        preview_key = f"preview_{cid}"
        if preview_key not in st.session_state:
            st.session_state[preview_key] = False

    for c in filtered:
        cid = c.get("candidate_id") or str(c.get("id"))
        candidate_label = f"{c.get('name') or 'Unnamed'} — {cid}"
        with st.expander(candidate_label, expanded=False):
            left, right = st.columns([3, 1])
            with left:
                # summary
                try:
                    _render_candidate_summary(c)
                except Exception as e:
                    st.error("Error rendering candidate details.")
                    st.write(f"Name: {c.get('name', '—')}")
                    st.write(f"Candidate ID: {cid}")
                    st.write(f"Created At: {_format_datetime(c.get('created_at'))}")

                # Candidate CV (secure + permission aware)
                try:
                    user = get_current_user(refresh=True)
                    actor_id = user.get("id") if user else 0

                    cv_bytes, cv_name, reason = get_candidate_cv_secure(cid, actor_id)

                    if reason == "no_permission":
                        st.warning("❌ You don’t have permission to view CVs for this candidate.")
                    elif reason == "not_found":
                        st.info("No CV uploaded yet.")
                    elif reason == "ok" and cv_bytes:
                        # action buttons: preview + download
                        col_a, col_b = st.columns([1, 1])
                        with col_a:
                            preview_key = f"preview_{cid}"
                            if st.button("🔍 Preview CV", key=f"preview_btn_{cid}"):
                                # toggle preview; using explicit True makes it show
                                st.session_state[preview_key] = True
                                # we don't rerun here; preview will appear because we continue rendering below
                        with col_b:
                            st.download_button(
                                "📄 Download CV",
                                data=cv_bytes,
                                file_name=cv_name or f"{cid}_cv.bin",
                                key=f"download_{cid}"
                            )

                        # Render preview if requested
                        if st.session_state.get(f"preview_{cid}", False):
                            mimetype = _detect_mimetype_from_name(cv_name)
                            st.markdown("**Preview**")
                            if mimetype == "application/pdf":
                                try:
                                    _embed_pdf(cv_bytes, height=700)
                                except Exception as e:
                                    st.error("Failed to render PDF preview. You can still download the file.")
                                    st.write(e)
                            elif mimetype.startswith("text/") or mimetype == "text/plain":
                                _preview_text_file(cv_bytes)
                            else:
                                st.info("Preview isn't available for this file type. Please download to view.")
                    else:
                        st.info("No CV available.")
                except Exception as e:
                    st.error(f"Error fetching CV: {e}")

                # Interview history
                try:
                    history = get_candidate_history(c.get("candidate_id"))
                    _render_interview_history(history)
                except Exception as e:
                    st.error("Interview history: (error fetching)")
                    st.write(e)

            with right:
                st.markdown("### Actions")
                user = get_current_user(refresh=True)
                _perms = get_user_permissions(user.get("id")) or {}
                can_delete_records = bool(_perms.get("can_delete_records", False))

                # Delete candidate (permission-aware)
                if not can_delete_records:
                    st.info("🚫 You don’t have permission to delete this record.")
                else:
                    if st.button("🗑️ Delete Candidate", key=f"del_btn_{cid}"):
                        try:
                            ok, reason = delete_candidate(cid, user["id"])
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

                # Toggle candidate edit permission (immediate UI update)
                try:
                    current_can_edit = bool(c.get("can_edit", False))
                    if st.button(
                        ("🔓 Grant Edit" if not current_can_edit else "🔒 Revoke Edit"),
                        key=f"toggle_edit_{cid}"
                    ):
                        new_val = not current_can_edit
                        # persist to DB
                        ok = set_candidate_permission(cid, new_val)
                        if ok:
                            # update local representation so UI reflects change immediately
                            c['can_edit'] = new_val
                            st.success(f"Set candidate can_edit = {new_val}")
                        else:
                            st.error("Failed to update candidate permission in DB.")
                except Exception as e:
                    st.error(f"Failed to toggle edit permission: {e}")


# -------------------------
# User management panel (permissions only)
# -------------------------
def show_user_management_panel():
    """User management only (CEO/Admin). Candidate operations removed by design."""
    require_login()
    current_user = get_current_user(refresh=True)
    role = _safe_lower(current_user.get("role"))
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
                try:
                    ok = update_user_permissions(u.get("id"), new_perms)
                    if ok:
                        st.success("Permissions updated.")
                        st.rerun()
                    else:
                        st.info("No changes were detected or update failed.")
                except Exception as e:
                    st.error(f"Failed to update permissions: {e}")


# -------------------------
# Entrypoint dispatcher (optional)
# -------------------------
def main():
    """
    Basic navigation: CEO Dashboard and User Management.
    You can call show_ceo_panel() directly from your router if you have one.
    """
    require_login()
    user = get_current_user(refresh=True)
    role = _safe_lower(user.get("role"))

    pages = {
        "CEO Dashboard": show_ceo_panel,
        "User Management": show_user_management_panel,
    }

    # restrict menu if not admin/ceo
    if role not in ("ceo", "admin"):
        st.error("You do not have permission to access this app.")
        st.stop()

    choice = st.sidebar.selectbox("Page", list(pages.keys()))
    pages[choice]()


if __name__ == "__main__":
    main()
