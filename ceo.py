# ceo.py - FIXED VERSION
"""
CEO Control Panel (feature-complete, cleaned + modular)

FIXES APPLIED:
1. Fixed CV preview functionality by correcting database column handling
2. Fixed interview display to show proper numbering and remove "Interview 1." prefix
3. Corrected the CV fetch function to properly handle database responses
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
from smtp_mailer import send_email
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
    get_conn
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


def _safe_get_candidate_cv_fixed(candidate_id: str, actor_id: int) -> Tuple[Optional[bytes], Optional[str], str]:
    """
    FIXED CV fetch function that properly handles database responses.
    Returns: (file_bytes_or_none, filename_or_none, reason_str)
    """
    try:
        # Check permissions first
        perms = get_user_permissions(actor_id) or {}
        role = (perms.get("role") or "").lower()
        if not (role in ("ceo", "admin") or perms.get("can_view_cvs")):
            return None, None, "no_permission"

        # Fetch CV directly from database
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                            SELECT cv_file, cv_filename, resume_link
                            FROM candidates
                            WHERE candidate_id = %s
                            """, (candidate_id,))
                result = cur.fetchone()

                if not result:
                    return None, None, "not_found"

                cv_file, cv_filename, resume_link = result

                # If we have file bytes stored in database
                if cv_file:
                    return bytes(cv_file), cv_filename or f"{candidate_id}.bin", "ok"

                # If we have a resume link but no file bytes
                if resume_link:
                    # For links, we can't return bytes, so indicate it's a link
                    return None, resume_link, "link_only"

                # No CV found
                return None, None, "not_found"

        finally:
            conn.close()

    except Exception as e:
        st.error(f"Error fetching CV: {e}")
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
# Interview helpers (formatting, filtering) - FIXED
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


def _render_interview_card_fixed(ev: Dict[str, Any]):
    """
    FIXED: Render a single interview/event as a clean card WITHOUT numbering.
    """
    # Extract common fields
    when = ev.get("created_at") or ev.get("at") or ev.get("scheduled_at") or ev.get("date") or ev.get("timestamp")
    interviewer = ev.get("actor") or ev.get("interviewer") or ev.get("actor_name") or ev.get("by") or "—"

    raw_details = ev.get("details") or ev.get("notes") or ev.get("action") or ""
    result = None
    notes = None
    if isinstance(raw_details, dict):
        result = raw_details.get("result") or raw_details.get("status")
        notes = raw_details.get("notes") or raw_details.get("details") or ""
    else:
        # string
        notes = str(raw_details or "")

    # Header WITHOUT numbering
    header = f"**{interviewer}**"
    if result:
        header += f" — {result}"
    if when:
        header += f" • {_format_datetime(when)}"
    st.markdown(header)

    # Format notes into Markdown-friendly bullets
    def _notes_to_markdown(n: str) -> str:
        if not n:
            return ""
        n = n.replace("\r\n", "\n").strip()
        lines = [ln.strip() for ln in n.split("\n") if ln.strip()]
        # If single paragraph, return as-is (short)
        if len(lines) == 1:
            return lines[0]
        # Otherwise render as bullets, preserving existing bullet markers
        out = []
        for ln in lines:
            if re.match(r"^[\-\•\*]\s+", ln):
                out.append(ln)
            else:
                out.append(f"- {ln}")
        return "\n".join(out)

    if notes and notes.strip():
        md = _notes_to_markdown(notes)
        st.markdown(
            f"""
            <div style="background-color:#f8f9fa; padding:10px; border-radius:10px; margin-bottom:10px; border:1px solid #ddd;">
                <strong>Details:</strong><br>{md}
            </div>
            """,
            unsafe_allow_html=True
        )

    # show event metadata
    ev_id = ev.get("id") or ev.get("event_id") or "—"
    actor_id = ev.get("actor_id") or ev.get("user_id") or "—"
    st.caption(f"Event ID: {ev_id} • Actor ID: {actor_id}")
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
            st.write(f"- Age / DOB: {form.get('dob', 'N/A')}")
            st.write(f"- Highest qualification: {form.get('highest_qualification', 'N/A')}")
            st.write(f"- Work experience: {form.get('work_experience', 'N/A')}")
            st.write(f"- Ready for holidays: {form.get('ready_festivals', 'N/A')}")
            st.write(f"- Ready for late nights: {form.get('ready_late_nights', 'N/A')}")
        else:
            _render_kv_block(form)


# =============================================================================
# CEO Dashboard (main) - FIXED
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
    st.caption(f"Showing {start + 1}–{min(end, total)} of {total} candidates")

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

                # ===================== CV Access & Preview Section - FIXED =====================
                try:
                    # Get the currently logged-in user
                    current_user = get_current_user(refresh=True)
                    actor_id = current_user.get("id") if current_user else 0

                    # Get the user's permissions
                    current_perms = get_user_permissions(actor_id) or {}
                    can_view_cvs = bool(current_perms.get("can_view_cvs", False))
                    role = (current_perms.get("role") or "").lower()

                    # CEO and admin always have CV access
                    if role in ("ceo", "admin"):
                        can_view_cvs = True

                    if not can_view_cvs:
                        st.warning("🔒 You do not have permission to view or download CVs.")
                    else:
                        # Fetch CV securely from database using FIXED function
                        cv_bytes, cv_name, reason = _safe_get_candidate_cv_fixed(cid, actor_id)

                        # Handle CV fetch results
                        if reason == "no_permission":
                            st.warning("❌ You don't have permission to view CVs for this candidate.")

                        elif reason == "not_found":
                            st.info("📂 No CV uploaded yet.")

                        elif reason == "link_only":
                            st.info(f"📎 CV available as link: {cv_name}")
                            if st.button("🔗 Open CV Link", key=f"link_{cid}"):
                                st.markdown(f"[Open CV]({cv_name})")

                        elif reason == "ok" and cv_bytes:
                            # Detect file type for proper preview
                            mimetype = _detect_mimetype_from_name(cv_name)

                            # Create three columns: Preview | Download | Open in New Tab
                            col1, col2, col3 = st.columns([1, 1, 1])

                            # 1️⃣ Preview Button
                            with col1:
                                if st.button("🔍 Preview", key=f"prev_{cid}"):
                                    st.session_state[f"preview_{cid}"] = True

                            # 2️⃣ Download Button
                            with col2:
                                st.download_button(
                                    "📄 Download",
                                    data=cv_bytes,
                                    file_name=cv_name or f"{cid}_cv.bin",
                                    key=f"dl_{cid}"
                                )

                            # 3️⃣ Open in New Tab Button
                            with col3:
                                if st.button("↗️ Open in New Tab", key=f"newtab_{cid}"):
                                    ok = _open_file_new_tab(cv_bytes, mimetype)
                                    if not ok:
                                        st.info("⚠️ Your browser blocked the new tab. Please use **Download** instead.")

                            # 4️⃣ Inline Preview (if requested)
                            if st.session_state.get(f"preview_{cid}", False):
                                st.subheader("📄 CV Preview")

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
                                    st.info(
                                        "Inline preview for Word docs is not supported. Use Open in New Tab or Download.")

                                else:
                                    st.info("Preview isn't available for this file type. Please download to view.")

                        elif reason == "error":
                            st.error("❌ Error occurred while fetching CV.")

                except Exception as e:
                    st.error(f"Unexpected error while handling CV: {e}")

                # Interview history (skip system events) - FIXED
                try:
                    history = get_candidate_history(c.get("candidate_id"))
                    if history is None:
                        st.info("No interview history available.")
                    else:
                        real_history = [ev for ev in history if not _is_system_event(ev)]
                        if not real_history:
                            st.info("No interviews recorded (only system events present).")
                        else:
                            st.markdown("#### Interview History")
                            # FIXED: Don't show numbering, just render each interview
                            for ev in real_history:
                                _render_interview_card_fixed(ev)
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

                # Single delete
                if not can_delete_records:
                    st.info("🚫 You can't delete this record.")
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
                                st.error("❌ You don't have permission to delete this record.")
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
                                            st.session_state["last_candidates_loaded"][i][
                                                "can_edit"] = not current_can_edit
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
    """Delete multiple candidates in one DB query (batch delete)."""
    current_user = get_current_user(refresh=True) or {}
    actor_id = current_user.get("id")
    ids = list(candidate_ids) if candidate_ids else []
    if not ids:
        st.info("No candidates selected.")
        return
    try:
        ok, reason = delete_candidate(ids, actor_id)
        if ok:
            st.success(f"Deleted {len(ids)} candidate(s).")
        else:
            if reason == "no_permission":
                st.error("❌ You don't have permission to delete these records.")
            elif reason == "not_found":
                st.warning("No matching candidates found to delete.")
            else:
                st.error("Delete failed (DB error).")
    except Exception as e:
        st.error(f"Failed to delete candidates: {e}")


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
    st.markdown(f"**{user_row.get('email', '(no email)')}**")
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