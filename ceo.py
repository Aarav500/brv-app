# ceo.py
"""
CEO Control Panel (feature-complete, cleaned + modular)

What’s included (and preserved):
- CEO Dashboard: candidate search, pagination, CV preview/download with fallbacks,
  formatted interview history (skips system/creation events),
  toggle candidate edit permission, delete (single + NEW: multi-select batch delete),
  refresh.
- User Management: permissions ONLY (no candidate UI here). Cleaner display.
- CV Preview: base64 <iframe> for PDFs, automatic fallback to "Open in new tab" or download.
  Graceful handling for .txt (render as text), .jpg/.jpeg/.png (render as image),
  .docx/.doc (no inline viewer -> provide new tab + download).
- Robust UI state via session_state. Helpful messages, safe exception handling.

Assumptions about helper functions (unchanged):
- get_all_users_with_permissions() -> List[Dict]
- update_user_permissions(user_id, perms_dict) -> True/False
- get_candidate_cv_secure(candidate_id, actor_id) ->
      (bytes_or_none, filename_or_none, reason_str) where reason in ("ok","no_permission","not_found")
- get_user_permissions(user_id) -> Dict[str, bool]
- get_candidate_statistics() -> Dict with keys: total_candidates, candidates_today, total_interviews, total_assessments
- get_all_candidates() -> List[Dict] with fields (id, candidate_id, name, email, phone, cv_file/resume_link,
      form_data, created_at, updated_at, can_edit)
- delete_candidate(candidate_id, actor_id) -> (ok_bool, reason_str)
- set_candidate_permission(candidate_id, bool_val) -> True/False
- get_candidate_history(candidate_id) -> List[Dict] representing events/interviews
- require_login() ; get_current_user(refresh=True) -> Dict
"""

from __future__ import annotations

import base64
import json
from typing import Dict, Any, List, Optional, Tuple, Iterable
from datetime import datetime
import uuid
import mimetypes
import traceback
import re

import streamlit as st
import streamlit.components.v1 as components

# ---- IMPORTANT: set page config once (safe even if main() routes later)
try:
    st.set_page_config(page_title="CEO Control Panel", layout="wide")
except Exception:
    # Streamlit may raise if called twice in same runtime; ignore
    pass

# --- Project helpers (unchanged imports expected in your repo)
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


# =============================================================================
# Utility helpers
# =============================================================================

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


def _titleize_key(k: str) -> str:
    # turn snake_case / lower / underscored keys into Title Case phrases
    k = (k or "").strip()
    k = k.replace("_", " ").replace("-", " ")
    k = re.sub(r"\s+", " ", k)
    if not k:
        return "Field"
    return k[:1].upper() + k[1:]


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
    return "application/octet-stream"


def _b64_data_uri(bytes_data: bytes, mimetype: str) -> str:
    b64 = base64.b64encode(bytes_data).decode("utf-8")
    return f"data:{mimetype};base64,{b64}"


def _safe_get_candidate_cv(candidate_id: str, actor_id: int) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
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


# =============================================================================
# CV Preview Helpers & Fallbacks
# =============================================================================

def _embed_pdf_iframe(bytes_data: bytes, height: int = 720) -> bool:
    """Primary inline preview for PDFs using base64 data URI in <iframe>."""
    if not bytes_data:
        return False
    try:
        src = _b64_data_uri(bytes_data, "application/pdf")
        html = f'<iframe src="{src}" width="100%" height="{height}" style="border:none;"></iframe>'
        components.html(html, height=height + 20)
        return True
    except Exception:
        return False


def _open_file_new_tab(bytes_data: bytes, mimetype: str, label: str = "Open in new tab") -> bool:
    """
    Generic open-in-new-tab fallback using a data URI anchor injected via components.html.
    Works immediately without rerun; if a strict browser blocks it, user can Download.
    """
    try:
        src = _b64_data_uri(bytes_data, mimetype)
        aid = f"open_{uuid.uuid4().hex}"
        html = f'''
            <a id="{aid}" href="{src}" target="_blank" rel="noopener noreferrer">{label}</a>
            <script>
              (function() {{
                var a = document.getElementById("{aid}");
                if (a) {{
                  // auto click to avoid extra step; comment this if undesired.
                  a.click();
                }}
              }})();
            </script>
        '''
        components.html(html, height=0)
        st.caption("If a new tab didn't open (strict browser), use Download below.")
        return True
    except Exception:
        return False


def _preview_text(bytes_data: bytes, max_chars: int = 30_000):
    try:
        text = bytes_data.decode("utf-8", errors="replace")
    except Exception:
        text = str(bytes_data)[:max_chars]
    if len(text) > max_chars:
        st.code(text[:max_chars] + "\n\n... (truncated)")
    else:
        st.code(text)


def _preview_image(bytes_data: bytes, caption: Optional[str] = None):
    try:
        st.image(bytes_data, caption=caption, use_column_width=True)
    except Exception:
        st.info("Unable to render image inline. Please use Download.")


# =============================================================================
# Interview helpers (formatting, filtering)
# =============================================================================

SYSTEM_HINT_WORDS = ("candidate record created", "record created", "created", "system", "import")


def _is_system_event(ev: Dict[str, Any]) -> bool:
    title = str(ev.get("title") or ev.get("event") or "").lower()
    actor = str(ev.get("actor") or ev.get("source") or ev.get("actor_type") or "").lower()
    etype = str(ev.get("type") or "").lower()
    if any(w in title for w in SYSTEM_HINT_WORDS):
        return True
    if actor and ("portal" in actor or "candidate_portal" in actor or "system" in actor):
        return True
    if etype in ("system", "created", "import"):
        return True
    return False


def _render_kv_block(d: Dict[str, Any]):
    for k, v in d.items():
        if v is None or v == "":
            continue
        if isinstance(v, (dict, list)):
            try:
                v = json.dumps(v, ensure_ascii=False)
            except Exception:
                v = str(v)
        st.write(f"- **{_titleize_key(k)}:** {v}")


def _render_interview_card(idx: int, ev: Dict[str, Any]):
    when = ev.get("created_at") or ev.get("at") or ev.get("scheduled_at") or ev.get("date") or ev.get("timestamp")
    interviewer = ev.get("actor") or ev.get("interviewer") or ev.get("actor_name") or ev.get("by") or "—"

    # Normalize details/result/notes whether dict or JSON string
    raw_details = ev.get("details") or ev.get("notes") or ev.get("action") or ""
    result = None
    notes: Any = None

    if isinstance(raw_details, dict):
        result = raw_details.get("result") or raw_details.get("status")
        notes = raw_details.get("notes") or raw_details.get("comment") or raw_details
    elif isinstance(raw_details, str) and raw_details.strip():
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

    # Card layout
    left, right = st.columns([3, 1])
    with left:
        st.markdown(f"### {title}")
        st.write(f"- **When:** {_format_datetime(when)}")
        st.write(f"- **By:** {interviewer}")
        if result:
            badge = "✅ Pass" if str(result).lower() in ("pass", "passed", "yes", "true", "selected") else f"🛈 {result}"
            st.write(f"- **Result:** {badge}")
        # Render notes
        if isinstance(notes, dict):
            st.markdown("**Details:**")
            _render_kv_block(notes)
        elif isinstance(notes, str) and notes.strip():
            md = notes.replace("\r\n", "\n").replace("\n", "  \n")
            st.markdown(f"**Details:**  \n{md}")
    with right:
        ev_id = ev.get("id") or ev.get("event_id") or "—"
        actor_id = ev.get("actor_id") or ev.get("user_id") or "—"
        st.caption(f"Event ID: {ev_id}")
        st.caption(f"Actor ID: {actor_id}")
    st.markdown("---")


# =============================================================================
# Candidate summary
# =============================================================================

def _render_candidate_summary(c: Dict[str, Any]):
    st.markdown(f"### {c.get('name') or '—'}")
    st.write(f"**Candidate ID:** {c.get('candidate_id') or c.get('id')}")
    st.write(f"**Email:** {c.get('email') or '—'}")
    st.write(f"**Phone:** {c.get('phone') or '—'}")
    st.write(f"**Created At:** {_format_datetime(c.get('created_at'))}")
    st.write(f"**Updated At:** {_format_datetime(c.get('updated_at'))}")
    st.write(f"**Can Edit (candidate):** {bool(c.get('can_edit', False))}")

    form = c.get("form_data") or {}
    if isinstance(form, dict) and form:
        st.markdown("**Application Summary**")
        # Display common fields if present, else a compact kv listing
        displayed = False
        for label_key in (
            "dob", "highest_qualification", "work_experience",
            "ready_festivals", "ready_late_nights"
        ):
            if form.get(label_key) is not None:
                displayed = True
        if displayed:
            st.write(f"- Age / DOB: {form.get('dob','N/A')}")
            st.write(f"- Highest qualification: {form.get('highest_qualification','N/A')}")
            st.write(f"- Work experience: {form.get('work_experience','N/A')}")
            st.write(f"- Ready for holidays: {form.get('ready_festivals','N/A')}")
            st.write(f"- Ready for late nights: {form.get('ready_late_nights','N/A')}")
        else:
            _render_kv_block(form)


# =============================================================================
# CEO Dashboard (main)
# =============================================================================

def show_ceo_panel():
    require_login()
    user = get_current_user(refresh=True)
    role = _safe_lower(user.get("role"))
    if role not in ("ceo", "admin"):
        st.error("You do not have permission to view this page.")
        st.stop()

    st.title("CEO Dashboard")
    st.caption("Candidate statistics and candidate management.")

    # Top stats
    try:
        stats = get_candidate_statistics() or {}
    except Exception:
        st.warning("Failed to fetch statistics.")
        stats = {}

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Candidates", stats.get("total_candidates", 0))
    with c2:
        st.metric("Candidates Today", stats.get("candidates_today", 0))
    with c3:
        st.metric("Interviews", stats.get("total_interviews", 0))
    with c4:
        st.metric("Assessments", stats.get("total_assessments", 0))

    st.markdown("---")

    # Candidate management header
    st.header("Candidate Management")

    q1, q2, q3, q4 = st.columns([3, 1, 1, 1])
    with q1:
        search_q = st.text_input(
            "Search by name / email / candidate_id (partial allowed)",
            key="ceo_search"
        )
    with q2:
        show_only_no_cv = st.checkbox("Only without CV", value=False, key="ceo_filter_no_cv")
    with q3:
        select_all_toggle = st.checkbox("Select all on page", value=False, key="ceo_select_all_toggle")
    with q4:
        if st.button("Refresh List", help="Reload candidates and stats"):
            st.session_state.pop("last_candidates_loaded", None)
            st.rerun()

    # Load candidates (cached per session run)
    try:
        if "last_candidates_loaded" not in st.session_state:
            st.session_state["last_candidates_loaded"] = get_all_candidates() or []
        candidates: List[Dict[str, Any]] = st.session_state["last_candidates_loaded"]
    except Exception as e:
        st.error(f"Failed to load candidates: {e}")
        candidates = []

    # Search/filter
    sq = (search_q or "").strip().lower()
    filtered: List[Dict[str, Any]] = []
    for c in (candidates or []):
        if sq:
            if (
                (c.get("name") or "").lower().find(sq) != -1
                or (c.get("email") or "").lower().find(sq) != -1
                or (c.get("candidate_id") or "").lower().find(sq) != -1
            ):
                pass
            else:
                continue
        if show_only_no_cv and (c.get("cv_file") or c.get("resume_link")):
            continue
        filtered.append(c)

    if not filtered:
        st.info("No candidates match your criteria.")
        return

    # Selection state
    selected_set: set[str] = st.session_state.setdefault("selected_candidates", set())

    # Ensure preview flags exist per candidate
    for c in filtered:
        cid = c.get("candidate_id") or str(c.get("id"))
        st.session_state.setdefault(f"preview_{cid}", False)

    # Pagination
    per_page = 12
    total = len(filtered)
    pages = (total + per_page - 1) // per_page
    page_idx = st.number_input("Page", min_value=1, max_value=max(1, pages), value=1, step=1, key="ceo_page")
    start = (page_idx - 1) * per_page
    end = start + per_page
    page_items = filtered[start:end]
    st.caption(f"Showing {start+1}–{min(end, total)} of {total} candidates")

    # Batch delete UI (top)
    can_delete_records = False
    try:
        _perms = get_user_permissions(user.get("id")) or {}
        can_delete_records = bool(_perms.get("can_delete_records", False))
    except Exception:
        pass

    bb1, bb2 = st.columns([1, 6])
    with bb1:
        if can_delete_records:
            if st.button(f"🗑️ Delete Selected ({len(selected_set)})", disabled=len(selected_set) == 0):
                _batch_delete_candidates(sorted(selected_set))
                # after deletion, refresh once
                st.session_state.pop("last_candidates_loaded", None)
                st.session_state["selected_candidates"] = set()
                st.rerun()
        else:
            st.caption("No permission to delete.")

    # Render candidate expanders
    for c in page_items:
        cid = c.get("candidate_id") or str(c.get("id"))
        label = f"{c.get('name') or 'Unnamed'} — {cid}"

        # selection checkbox row header
        sel_cols = st.columns([0.06, 0.94])
        with sel_cols[0]:
            checked = select_all_toggle or (cid in selected_set)
            new_checked = st.checkbox("", value=checked, key=f"sel_{cid}")
            if new_checked:
                selected_set.add(cid)
            else:
                selected_set.discard(cid)
        with sel_cols[1]:
            pass  # space for the expander

        with st.expander(label, expanded=False):
            main_left, main_right = st.columns([3, 1])
            with main_left:
                # Summary
                try:
                    _render_candidate_summary(c)
                except Exception:
                    st.error("Error rendering candidate summary.")
                    st.write(json.dumps(c, default=str))

                # CV access & preview
                try:
                    current_user = get_current_user(refresh=True)
                    actor_id = current_user.get("id") if current_user else 0
                    cv_bytes, cv_name, reason = _safe_get_candidate_cv(cid, actor_id)
                    current_perms = get_user_permissions(current_user.get("id")) or {}
                    can_view_cvs = bool(current_perms.get("can_view_cvs", False))

                    if reason == "no_permission":
                        st.warning("❌ You don’t have permission to view CVs for this candidate.")
                    elif reason == "not_found" or not cv_bytes:
                        st.info("No CV uploaded yet.")
                    elif reason == "ok" and cv_bytes:
                        if not can_view_cvs:
                            st.warning("🔒 You do not have permission to view or download CVs.")
                        else:
                            mimetype = _detect_mimetype_from_name(cv_name)
                            a, b, ccol = st.columns([1, 1, 1])
                            with a:
                                if st.button("🔍 Preview", key=f"prev_{cid}"):
                                    st.session_state[f"preview_{cid}"] = True
                            with b:
                                st.download_button(
                                    "📄 Download",
                                    data=cv_bytes,
                                    file_name=cv_name or f"{cid}_cv.bin",
                                    key=f"dl_{cid}",
                                )
                            with ccol:
                                if st.button("↗️ Open in new tab", key=f"newtab_{cid}"):
                                    ok = _open_file_new_tab(cv_bytes, mimetype)
                                    if not ok:
                                        st.info("Your browser blocked new tab. Please use Download.")

                            # Render preview area
                            if st.session_state.get(f"preview_{cid}", False):
                                st.markdown("**Preview**")
                                if mimetype == "application/pdf":
                                    ok = _embed_pdf_iframe(cv_bytes)
                                    if not ok:
                                        if not _open_file_new_tab(cv_bytes, mimetype):
                                            st.info("Preview blocked. Please use Download.")
                                elif mimetype.startswith("text/"):
                                    _preview_text(cv_bytes)
                                elif mimetype.startswith("image/"):
                                    _preview_image(cv_bytes, caption=cv_name or cid)
                                elif mimetype in (
                                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    "application/msword",
                                ):
                                    st.info("Inline preview for Word docs is not supported. Use Open in New Tab or Download.")
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

            with main_right:
                st.markdown("### Actions")
                current_user = get_current_user(refresh=True)
                _perms = get_user_permissions(current_user.get("id")) or {}
                can_delete_records = bool(_perms.get("can_delete_records", False))

                st.caption(f"ID: {c.get('id')}")
                st.caption(f"Candidate ID: {cid}")
                st.caption(f"Created: {_format_datetime(c.get('created_at'))}")

                # Single delete (optimized: no extra round trips after success; cache edited then rerun once)
                if not can_delete_records:
                    st.info("🚫 You can’t delete this record.")
                else:
                    if st.button("🗑️ Delete Candidate", key=f"del_one_{cid}"):
                        ok, reason = False, "error"
                        try:
                            ok, reason = delete_candidate(cid, current_user["id"])
                        except Exception as e:
                            st.error(f"Delete failed: {e}")

                        if ok:
                            st.success("Candidate deleted.")
                            # Update cached list locally to avoid extra fetch
                            if "last_candidates_loaded" in st.session_state:
                                st.session_state["last_candidates_loaded"] = [
                                    x for x in st.session_state["last_candidates_loaded"]
                                    if (x.get("candidate_id") or str(x.get("id"))) != cid
                                ]
                            # remove from selections if present
                            st.session_state["selected_candidates"].discard(cid)
                            st.rerun()
                        else:
                            if reason == "no_permission":
                                st.error("❌ You don’t have permission to delete this record.")
                            elif reason == "not_found":
                                st.warning("Candidate already deleted.")
                            else:
                                st.error("Delete failed (DB error).")

                # Toggle candidate edit permission
                try:
                    current_can_edit = bool(c.get("can_edit", False))
                    toggle_label = "🔓 Grant Edit" if not current_can_edit else "🔒 Revoke Edit"
                    if st.button(toggle_label, key=f"toggle_edit_{cid}"):
                        try:
                            ok = set_candidate_permission(cid, not current_can_edit)
                            if ok:
                                c["can_edit"] = not current_can_edit
                                # Update cache entry in-place
                                if "last_candidates_loaded" in st.session_state:
                                    for i, cand in enumerate(st.session_state["last_candidates_loaded"]):
                                        if (cand.get("candidate_id") or str(cand.get("id"))) == cid:
                                            st.session_state["last_candidates_loaded"][i]["can_edit"] = not current_can_edit
                                            break
                                st.success(f"Set candidate can_edit = {not current_can_edit}")
                            else:
                                st.error("Failed to update candidate permission in DB.")
                        except Exception as e:
                            st.error(f"Failed to toggle permission: {e}")
                            st.write(traceback.format_exc())
                except Exception as e:
                    st.error(f"Failed to render toggle: {e}")

    # Footer tip
    st.markdown("---")
    st.caption("Tip: If inline PDF preview is blocked by your browser, use 'Open in new tab' or 'Download'.")


def _batch_delete_candidates(candidate_ids: Iterable[str]):
    """Delete multiple candidates in one action; suppress repeated reruns."""
    current_user = get_current_user(refresh=True) or {}
    actor_id = current_user.get("id")
    successes, failures = 0, []

    for cid in candidate_ids:
        try:
            ok, reason = delete_candidate(cid, actor_id)
            if ok:
                successes += 1
            else:
                failures.append((cid, reason or "unknown"))
        except Exception as e:
            failures.append((cid, str(e)))

    if successes:
        st.success(f"Deleted {successes} candidate(s).")
    if failures:
        msgs = ", ".join([f"{cid} ({why})" for cid, why in failures])
        st.error(f"Failed to delete: {msgs}")


# =============================================================================
# User management (permissions ONLY — NO candidate UI here)
# =============================================================================

def show_user_management_panel():
    require_login()
    current_user = get_current_user(refresh=True)
    role = _safe_lower(current_user.get("role"))
    if role not in ("ceo", "admin"):
        st.error("You do not have permission to view this page.")
        st.stop()

    st.title("User Management")
    st.caption("Manage user permissions. (No candidate operations here.)")

    try:
        users = get_all_users_with_permissions() or []
    except Exception as e:
        st.error(f"Failed to load users: {e}")
        users = []

    if not users:
        st.info("No users found.")
        return

    # Removed any "Candidate Records" section — ONLY permission controls remain
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
                    st.write(traceback.format_exc())


def _render_user_permissions_block(user_row: Dict[str, Any], index_key: str):
    st.markdown(f"**{user_row.get('email','(no email)')}**")
    role = (user_row.get("role") or "").strip()
    if role and role.lower() != "ceo":
        st.caption(f"Role: {role}")

    st.write(f"ID: {user_row.get('id')}  |  Created: {_format_datetime(user_row.get('created_at'))}")
    st.write(f"Force Password Reset: {bool(user_row.get('force_password_reset', False))}")

    c1 = st.checkbox("Can View CVs", value=bool(user_row.get("can_view_cvs", False)), key=f"{index_key}_cv")
    c2 = st.checkbox("Can Delete Candidate Records", value=bool(user_row.get("can_delete_records", False)),
                     key=f"{index_key}_del")

    return {
        "can_view_cvs": bool(c1),
        "can_delete_records": bool(c2),
    }


# =============================================================================
# Entrypoint / Router
# =============================================================================

def main():
    require_login()
    user = get_current_user(refresh=True)
    role = _safe_lower(user.get("role"))

    pages = {
        "CEO Dashboard": show_ceo_panel,
        "Manage Users": show_user_management_panel,  # wording matches your sidebar screenshot
    }

    if role not in ("ceo", "admin"):
        st.error("You do not have permission to access this app.")
        st.stop()

    # Sidebar
    st.sidebar.title("Navigation")
    st.sidebar.caption(f"Logged in as:\n{user.get('email') or '—'}")
    st.sidebar.markdown("---")
    choice = st.sidebar.radio("Go to", list(pages.keys()), index=0)
    st.sidebar.markdown("---")
    st.sidebar.caption("Admin panel actions depend on CEO-granted rights. CEO always has full access.")
    pages[choice]()


if __name__ == "__main__":
    main()
