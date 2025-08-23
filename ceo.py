# ceo.py
"""
CEO Control Panel (refactor + small enhancements)

What’s new vs. your last version:
- CV Previews:
  * PDF: base64 iframe embed; if blocked => "Open in new tab" or download.
  * DOCX: tries to extract & preview text (via python-docx if installed); else fallback to download/tab.
  * TXT: inline preview.
  * Images (jpg/png/webp/gif): inline preview.
- Interview Notes:
  * Skips system/creation/import events.
  * Preserves structured JSON details as readable fields (key: value).
- Candidate Management:
  * Search, pagination, delete, toggle edit, CV controls intact.
- User Management:
  * Only user permissions (completely stripped of candidate ops).

Assumptions about helper functions (adapt if your project differs):
- get_all_users_with_permissions() -> List[Dict]
- update_user_permissions(user_id, perms_dict) -> True/False
- get_candidate_cv_secure(candidate_id, actor_id) -> (bytes_or_none, filename_or_none, reason_str) where reason in ("ok","no_permission","not_found")
- get_user_permissions(user_id) -> Dict[str, bool]
- get_candidate_statistics() -> Dict with keys: total_candidates, candidates_today, total_interviews, total_assessments
- get_all_candidates() -> List[Dict] with candidate fields (id, candidate_id, name, email, phone, cv_file/resume_link, form_data, created_at, updated_at, can_edit)
- delete_candidate(candidate_id, actor_id) -> (ok_bool, reason_str)
- set_candidate_permission(candidate_id, bool_val) -> True/False
- get_candidate_history(candidate_id) -> List[Dict] representing events/interviews
- require_login() ; get_current_user(refresh=True) -> Dict
"""

import base64
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import io
import uuid
import mimetypes
import traceback

import streamlit as st
import streamlit.components.v1 as components

# --- Import your project's DB/auth helpers here ---
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

from auth import require_login, get_current_user


# -------------------------
# Utility helpers
# -------------------------
def _format_datetime(v) -> str:
    """Normalize various datetime formats to a display string."""
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


def _detect_mimetype_from_name(name: Optional[str]) -> str:
    if not name:
        return "application/octet-stream"
    mt, _ = mimetypes.guess_type(name)
    if mt:
        return mt
    lname = name.lower()
    if lname.endswith(".pdf"):
        return "application/pdf"
    if lname.endswith(".txt") or lname.endswith(".log") or lname.endswith(".md"):
        return "text/plain"
    if lname.endswith(".docx"):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if lname.endswith(".doc"):
        return "application/msword"
    if lname.endswith(".jpg") or lname.endswith(".jpeg"):
        return "image/jpeg"
    if lname.endswith(".png"):
        return "image/png"
    if lname.endswith(".gif"):
        return "image/gif"
    if lname.endswith(".webp"):
        return "image/webp"
    return "application/octet-stream"


def _b64_data_uri(bytes_data: bytes, mimetype: str) -> str:
    b64 = base64.b64encode(bytes_data).decode("utf-8")
    return f"data:{mimetype};base64,{b64}"


def _safe_get_candidate_cv(candidate_id: str, actor_id: int) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
    """
    Adapter: calls get_candidate_cv_secure and normalizes returned values.
    Expected return: (bytes_or_none, filename_or_none, reason_str)
    """
    try:
        res = get_candidate_cv_secure(candidate_id, actor_id)
        if isinstance(res, tuple) and len(res) >= 3:
            return res[0], res[1], res[2]
        if isinstance(res, (bytes, bytearray)):
            return bytes(res), f"{candidate_id}.bin", "ok"
        return None, None, "not_found"
    except Exception as e:
        st.error(f"Error while fetching CV: {e}")
        return None, None, "error"


# -------------------------
# CV Preview Helpers & Fallbacks
# -------------------------
def _embed_pdf_iframe(bytes_data: bytes, height: int = 700):
    """
    Primary method: embed a base64 data URI inside an iframe.
    Some browsers (Brave/Firefox with strict settings) may block this — we provide fallbacks.
    """
    if not bytes_data:
        st.info("No data to preview.")
        return False
    try:
        src = _b64_data_uri(bytes_data, "application/pdf")
        html = f'<iframe src="{src}" width="100%" height="{height}" style="border:none;"></iframe>'
        components.html(html, height=height + 20)
        return True
    except Exception:
        st.write("Inline preview failed (browser may block embedded PDFs).")
        return False


def _open_file_new_tab_button(bytes_data: bytes, mimetype: str, label: str = "Open in new tab"):
    """Generic new-tab opener using data URI (some browsers still force download)."""
    try:
        src = _b64_data_uri(bytes_data, mimetype)
        aid = f"openfile_{uuid.uuid4().hex}"
        html = f'''
            <a id="{aid}" href="{src}" target="_blank" rel="noopener noreferrer">
                {label}
            </a>
        '''
        st.markdown(html, unsafe_allow_html=True)
        return True
    except Exception:
        return False


def _preview_text(bytes_data: bytes, max_chars: int = 30_000):
    """Preview plain-text files safely."""
    try:
        text = bytes_data.decode("utf-8", errors="replace")
    except Exception:
        text = str(bytes_data)[:max_chars]
    if len(text) > max_chars:
        st.code(text[:max_chars] + "\n\n... (truncated)", language=None)
    else:
        st.code(text, language=None)


def _preview_image(bytes_data: bytes, caption: Optional[str] = None):
    """Preview an image (jpg/png/gif/webp)."""
    try:
        st.image(bytes_data, caption=caption, use_column_width=True)
        return True
    except Exception:
        return False


def _preview_docx(bytes_data: bytes, max_chars: int = 40_000) -> bool:
    """
    Try to preview DOCX by extracting text using python-docx if available.
    Falls back to False when library is missing or parsing fails.
    """
    try:
        from docx import Document  # optional dependency
    except Exception:
        return False

    try:
        buf = io.BytesIO(bytes_data)
        doc = Document(buf)
        parts = []
        for p in doc.paragraphs:
            parts.append(p.text)
        text = "\n".join(parts).strip()
        if not text:
            # Try table text (some CVs are tables)
            for t in doc.tables:
                for row in t.rows:
                    parts.append(" | ".join(cell.text.strip() for cell in row.cells))
            text = "\n".join(parts).strip()

        if not text:
            return False

        if len(text) > max_chars:
            st.code(text[:max_chars] + "\n\n... (truncated)", language=None)
        else:
            st.code(text, language=None)
        return True
    except Exception:
        return False


# -------------------------
# Interview formatting helpers
# -------------------------
def _is_system_event(ev: Dict[str, Any]) -> bool:
    """
    Skip system/creation/import events in the interview list.
    """
    title = str(ev.get("title") or ev.get("event") or "").lower()
    actor = str(ev.get("actor") or ev.get("source") or ev.get("actor_type") or "").lower()
    if "created" in title and ("candidate" in title or "record" in title):
        return True
    if actor and ("portal" in actor or "candidate_portal" in actor or "system" in actor):
        return True
    if str(ev.get("type") or "").lower() in ("system", "created", "import"):
        return True
    return False


def _render_interview_card(idx: int, ev: Dict[str, Any]):
    """
    Render a single interview/event as a clean card.
    """
    when = ev.get("created_at") or ev.get("at") or ev.get("scheduled_at") or ev.get("date") or ev.get("timestamp")
    interviewer = ev.get("actor") or ev.get("interviewer") or ev.get("actor_name") or ev.get("by") or "—"

    raw_details = ev.get("details") or ev.get("notes") or ev.get("action") or ""
    result = None
    notes = None
    if isinstance(raw_details, dict):
        result = raw_details.get("result") or raw_details.get("status")
        notes = raw_details.get("notes") or raw_details.get("comment") or raw_details
    elif isinstance(raw_details, str):
        try:
            parsed = json.loads(raw_details)
            if isinstance(parsed, dict):
                result = parsed.get("result") or parsed.get("status")
                notes = parsed.get("notes") or parsed
            else:
                notes = raw_details
        except Exception:
            notes = raw_details

    title = ev.get("title") or ev.get("summary") or f"Interview #{idx}"

    left, right = st.columns([3, 1])
    with left:
        st.markdown(f"**{title}**")
        st.write(f"- **When:** {_format_datetime(when)}")
        st.write(f"- **By:** {interviewer}")
        if result:
            st.write(f"- **Result:** {result}")

        if isinstance(notes, dict):
            st.markdown("**Details:**")
            for k, v in notes.items():
                if isinstance(v, (dict, list)):
                    v = json.dumps(v, ensure_ascii=False)
                st.write(f"- {k}: {v}")
        elif isinstance(notes, str) and notes.strip():
            md = notes.replace("\r\n", "\n").replace("\n", "  \n")
            st.markdown(f"**Details:**  \n{md}")
    with right:
        ev_id = ev.get("id") or ev.get("event_id") or "—"
        actor_id = ev.get("actor_id") or ev.get("user_id") or "—"
        st.caption(f"Event ID: {ev_id}")
        st.caption(f"Actor ID: {actor_id}")
    st.markdown("---")


# -------------------------
# Render candidate summary (keeps old fields)
# -------------------------
def _render_candidate_summary(c: Dict[str, Any]):
    """Render a readable candidate summary similar to old implementation."""
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


# -------------------------
# CEO Dashboard (main)
# -------------------------
def show_ceo_panel():
    require_login()
    user = get_current_user(refresh=True)
    role = _safe_lower(user.get("role"))
    if role not in ("ceo", "admin"):
        st.error("You do not have permission to view this page.")
        st.stop()

    st.set_page_config(page_title="CEO Dashboard", layout="wide")
    st.title("CEO Dashboard")
    st.caption("Candidate statistics and candidate management (all candidate operations live here).")

    # Top stats area
    try:
        stats = get_candidate_statistics() or {}
    except Exception:
        st.warning("Failed to fetch statistics.")
        stats = {}

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Candidates", stats.get("total_candidates", 0))
    with col2:
        st.metric("Candidates Today", stats.get("candidates_today", 0))
    with col3:
        st.metric("Interviews", stats.get("total_interviews", 0))
    with col4:
        st.metric("Assessments", stats.get("total_assessments", 0))

    st.markdown("---")

    # Candidate management block (search/filter/refresh)
    st.header("Candidate Management")
    q_col1, q_col2, q_col3 = st.columns([3, 1, 1])
    with q_col1:
        search_q = st.text_input(
            "Search candidates by name / email / candidate_id (partial matches allowed)",
            key="ceo_search",
        )
    with q_col2:
        if st.button("Refresh List"):
            st.session_state.pop("last_candidates_loaded", None)
            st.rerun()
    with q_col3:
        show_only_no_cv = st.checkbox("Only without CV", value=False, key="ceo_filter_no_cv")

    # Load candidates (cache in session during the interaction)
    try:
        if "last_candidates_loaded" not in st.session_state:
            st.session_state["last_candidates_loaded"] = get_all_candidates() or []
        candidates = st.session_state["last_candidates_loaded"]
    except Exception as e:
        st.error(f"Failed to load candidates: {e}")
        candidates = []

    # Apply search filter
    filtered: List[Dict[str, Any]] = []
    sq = (search_q or "").strip().lower()
    for c in (candidates or []):
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

    # Ensure session_state keys for previews
    for c in filtered:
        cid = c.get("candidate_id") or str(c.get("id"))
        preview_key = f"preview_{cid}"
        if preview_key not in st.session_state:
            st.session_state[preview_key] = False

    # Pagination helper (simple)
    per_page = 15
    total = len(filtered)
    pages = (total + per_page - 1) // per_page
    page_idx = st.number_input(
        "Page", min_value=1, max_value=max(1, pages), value=1, step=1, key="ceo_page"
    )
    start = (page_idx - 1) * per_page
    end = start + per_page
    page_items = filtered[start:end]

    st.caption(f"Showing {start+1} - {min(end, total)} of {total} candidates")

    # show candidate expanders
    for c in page_items:
        cid = c.get("candidate_id") or str(c.get("id"))
        candidate_label = f"{c.get('name') or 'Unnamed'} — {cid}"
        with st.expander(candidate_label, expanded=False):
            left, right = st.columns([3, 1])
            with left:
                # Candidate summary
                try:
                    _render_candidate_summary(c)
                except Exception:
                    st.error("Error rendering candidate summary.")
                    st.write(json.dumps(c, default=str))

                # CV access & preview logic
                try:
                    current_user = get_current_user(refresh=True)
                    actor_id = current_user.get("id") if current_user else 0
                    cv_bytes, cv_name, reason = _safe_get_candidate_cv(cid, actor_id)

                    # check permissions explicitly via get_user_permissions
                    current_perms = get_user_permissions(current_user.get("id")) or {}
                    can_view_cvs = bool(current_perms.get("can_view_cvs", False))

                    if reason == "no_permission":
                        st.warning("❌ You don’t have permission to view CVs for this candidate.")
                    elif reason == "not_found":
                        st.info("No CV uploaded yet.")
                    elif reason == "ok" and cv_bytes:
                        if not can_view_cvs:
                            st.warning("🔒 You do not have permission to view or download CVs.")
                        else:
                            # action buttons
                            col_a, col_b, col_c = st.columns([1, 1, 1])
                            with col_a:
                                if st.button("🔍 Preview CV", key=f"preview_btn_{cid}"):
                                    st.session_state[f"preview_{cid}"] = True
                            with col_b:
                                st.download_button(
                                    "📄 Download CV",
                                    data=cv_bytes,
                                    file_name=cv_name or f"{cid}_cv.bin",
                                    key=f"download_{cid}",
                                )
                            with col_c:
                                # 'Open in new tab' anchor (for browsers that block iframe)
                                mimetype = _detect_mimetype_from_name(cv_name)
                                if st.button("↗️ Open in new tab", key=f"open_newtab_{cid}"):
                                    _open_file_new_tab_button(cv_bytes, mimetype, label="Open CV in new tab")

                            # Render preview block if requested
                            if st.session_state.get(f"preview_{cid}", False):
                                mimetype = _detect_mimetype_from_name(cv_name)
                                st.markdown("**Preview**")

                                if mimetype == "application/pdf":
                                    ok = _embed_pdf_iframe(cv_bytes, height=700)
                                    if not ok:
                                        opened = _open_file_new_tab_button(
                                            cv_bytes, "application/pdf", label="Open PDF in new tab"
                                        )
                                        if not opened:
                                            st.info(
                                                "Your browser blocked inline preview. Please download the CV to view it."
                                            )

                                elif mimetype.startswith("text/") or mimetype == "text/plain":
                                    _preview_text(cv_bytes)

                                elif mimetype in (
                                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    "application/msword",
                                ):
                                    # .docx => try textual extraction; .doc => likely download only
                                    parsed = False
                                    if mimetype.endswith("wordprocessingml.document"):
                                        parsed = _preview_docx(cv_bytes)
                                    if not parsed:
                                        st.info(
                                            "Preview for Word documents isn’t available in this browser. "
                                            "Use 'Open in new tab' (will download) or 'Download CV'."
                                        )

                                elif mimetype.startswith("image/"):
                                    shown = _preview_image(cv_bytes, caption=cv_name or "Image preview")
                                    if not shown:
                                        st.info("Unable to preview this image. Please download to view.")

                                else:
                                    st.info("Preview isn't available for this file type. Please download to view.")
                    else:
                        st.info("No CV available or unable to fetch CV. You can upload or check permissions.")
                except Exception as e:
                    st.error("Error processing CV preview/download.")
                    st.write(traceback.format_exc())

                # Interview history (skip system events)
                try:
                    history = get_candidate_history(c.get("candidate_id"))
                    if history is None:
                        st.info("No interview history available.")
                    else:
                        real_history = [ev for ev in history if not _is_system_event(ev)]
                        if not real_history:
                            st.info("No interviews recorded (only system events present).")
                        else:
                            st.markdown("#### Interview history")
                            for idx, ev in enumerate(real_history, start=1):
                                _render_interview_card(idx, ev)
                except Exception:
                    st.error("Interview history: (error fetching)")
                    st.write(traceback.format_exc())

            # Right column: actions (delete, toggle edit permission, quick metadata)
            with right:
                st.markdown("### Actions")
                current_user = get_current_user(refresh=True)
                _perms = get_user_permissions(current_user.get("id")) or {}
                can_delete_records = bool(_perms.get("can_delete_records", False))

                # Quick metadata
                st.caption(f"ID: {c.get('id')}")
                st.caption(f"Candidate ID: {c.get('candidate_id')}")
                st.caption(f"Created: {_format_datetime(c.get('created_at'))}")

                # Delete candidate (permission-aware)
                if not can_delete_records:
                    st.info("🚫 You don’t have permission to delete this record.")
                else:
                    if st.button("🗑️ Delete Candidate", key=f"del_btn_{cid}"):
                        try:
                            ok, reason = delete_candidate(cid, current_user["id"])
                            if ok:
                                st.success("Candidate deleted.")
                                st.session_state.pop("last_candidates_loaded", None)
                                st.rerun()
                            else:
                                if reason == "no_permission":
                                    st.error("❌ You don’t have permission to delete this record.")
                                elif reason == "not_found":
                                    st.warning("Candidate already deleted.")
                                else:
                                    st.error("Delete failed (DB error).")
                        except Exception as e:
                            st.error(f"Delete failed: {e}")
                            st.write(traceback.format_exc())

                # Toggle candidate edit permission (instant)
                try:
                    current_can_edit = bool(c.get("can_edit", False))
                    toggle_label = ("🔓 Grant Edit" if not current_can_edit else "🔒 Revoke Edit")
                    if st.button(toggle_label, key=f"toggle_edit_{cid}"):
                        new_val = not current_can_edit
                        try:
                            ok = set_candidate_permission(cid, new_val)
                            if ok:
                                c["can_edit"] = new_val
                                st.success(f"Set candidate can_edit = {new_val}")
                                if "last_candidates_loaded" in st.session_state:
                                    for i, cand in enumerate(st.session_state["last_candidates_loaded"]):
                                        if (cand.get("candidate_id") or str(cand.get("id"))) == cid:
                                            st.session_state["last_candidates_loaded"][i]["can_edit"] = new_val
                                            break
                            else:
                                st.error("Failed to update candidate permission in DB.")
                        except Exception as e:
                            st.error(f"Failed to toggle edit permission: {e}")
                            st.write(traceback.format_exc())
                except Exception as e:
                    st.error(f"Failed to render toggle: {e}")

    st.markdown("---")
    st.caption(
        "Tip: If inline PDF preview is blocked by your browser, use 'Open in new tab' or 'Download CV'. "
        "DOCX previews need python-docx; otherwise they’ll download."
    )


# -------------------------
# User management panel (permissions only — candidates fully stripped)
# -------------------------
def show_user_management_panel():
    require_login()
    current_user = get_current_user(refresh=True)
    role = _safe_lower(current_user.get("role"))
    if role not in ("ceo", "admin"):
        st.error("You do not have permission to view this page.")
        st.stop()

    st.title("User Management")
    st.caption("Manage user permissions only (no candidate data/actions on this page).")

    try:
        users = get_all_users_with_permissions() or []
    except Exception as e:
        st.error(f"Failed to load users: {e}")
        users = []

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
                        # (Optional) nothing else to refresh here.
                        st.rerun()
                    else:
                        st.info("No changes were detected or update failed.")
                except Exception as e:
                    st.error(f"Failed to update permissions: {e}")
                    st.write(traceback.format_exc())


# -------------------------
# Small helper: render user permission block (copied/adapted)
# -------------------------
def _render_user_permissions_block(user_row: Dict[str, Any], index_key: str):
    base = index_key
    st.markdown(f"**{user_row.get('email','(no email)')}**")
    role = (user_row.get("role") or "").strip()
    if role and role.lower() != "ceo":
        st.caption(f"Role: {role}")

    st.write(f"ID: {user_row.get('id')}  |  Created: {_format_datetime(user_row.get('created_at'))}")
    st.write(f"Force Password Reset: {bool(user_row.get('force_password_reset', False))}")

    c1 = st.checkbox("Can View CVs", value=bool(user_row.get("can_view_cvs", False)), key=f"{base}_cv")
    c2 = st.checkbox(
        "Can Delete Candidate Records",
        value=bool(user_row.get("can_delete_records", False)),
        key=f"{base}_del",
    )

    return {
        "can_view_cvs": bool(c1),
        "can_delete_records": bool(c2),
    }


# -------------------------
# Entrypoint / Router
# -------------------------
def main():
    require_login()
    user = get_current_user(refresh=True)
    role = _safe_lower(user.get("role"))

    pages = {
        "CEO Dashboard": show_ceo_panel,
        "User Management": show_user_management_panel,
    }

    if role not in ("ceo", "admin"):
        st.error("You do not have permission to access this app.")
        st.stop()

    st.sidebar.title("Admin")
    choice = st.sidebar.radio("Page", list(pages.keys()), index=0)
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "**Helpful:**\n- Use `Refresh List` after bulk import.\n"
        "- If PDF preview is blocked, try `Open in new tab` or `Download CV`.\n"
        "- DOCX preview needs python-docx; otherwise it will download."
    )
    pages[choice]()


if __name__ == "__main__":
    main()
