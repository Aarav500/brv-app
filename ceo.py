# =============================================================================
# CV Preview Helpers & Fallbacks - SIMPLIFIED VERSION
# =============================================================================
# ceo.py - SIMPLIFIED VERSION with clean PDF display and complete form data
"""
CEO Control Panel (feature-complete, cleaned + modular)

SIMPLIFIED FIXES APPLIED:
1. Fixed PDF preview with simple iframe approach
2. Show complete candidate form data from candidate_view.py
3. Clean white text styling for interview notes
4. Auto-redirect for new tab functionality
5. Display all application questions and answers
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
                if resume_link and resume_link.strip():
                    # For links, we can't return bytes, so indicate it's a link
                    return None, resume_link.strip(), "link_only"

                # No CV found
                return None, None, "not_found"

        finally:
            conn.close()

    except Exception as e:
        st.error(f"Error fetching CV: {e}")
        return None, None, "error"


# =============================================================================
# SIMPLE PDF Preview
# =============================================================================

def _simple_pdf_preview(bytes_data: bytes, height: int = 600, unique_key: str = "") -> bool:
    """Simple PDF preview using streamlit native display."""
    if not bytes_data:
        return False

    try:
        # Try Streamlit's native PDF display first
        st.subheader("📄 CV Preview")

        # Create download button
        st.download_button(
            "📥 Download PDF",
            data=bytes_data,
            file_name="cv.pdf",
            mime="application/pdf",
            key=f"pdf_download_{unique_key}"
        )

        # Simple iframe approach
        b64 = base64.b64encode(bytes_data).decode()

        # Simple HTML iframe
        iframe_html = f"""
        <iframe 
            src="data:application/pdf;base64,{b64}" 
            width="100%" 
            height="{height}px" 
            style="border: 1px solid #ccc;">
            <p>Your browser does not support PDFs. Please download the PDF to view it.</p>
        </iframe>
        """

        st.markdown(iframe_html, unsafe_allow_html=True)
        return True

    except Exception as e:
        st.error(f"PDF preview failed: {e}")
        return False


def _open_file_auto_redirect(bytes_data: bytes, mimetype: str, unique_key: str = "") -> bool:
    """
    Auto-redirect to new tab with file content - reloads automatically.
    """
    try:
        src = _b64_data_uri(bytes_data, mimetype)

        # Auto-redirect script that opens new tab and reloads
        redirect_html = f"""
        <script>
        (function() {{
            var newWindow = window.open('{src}', '_blank');
            if (newWindow) {{
                // Force reload after a short delay
                setTimeout(function() {{
                    newWindow.location.reload();
                }}, 1000);
            }}
        }})();
        </script>
        <div style="padding: 10px; background: #d4edda; border: 1px solid #c3e6cb; border-radius: 4px; color: #155724;">
            ✅ Opening CV in new tab and reloading...
        </div>
        """

        components.html(redirect_html, height=60)
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
# Performance optimization helpers
# =============================================================================

@st.cache_data(ttl=300)  # Cache for 5 minutes
def _get_candidates_cached():
    """Cached candidate loading with 5 minute TTL."""
    try:
        return get_all_candidates() or []
    except Exception as e:
        st.error(f"Failed to load candidates: {e}")
        return []


@st.cache_data(ttl=300)  # Cache for 5 minutes
def _get_candidate_history_cached(candidate_id: str):
    """Cached history loading with 5 minute TTL."""
    try:
        return get_candidate_history(candidate_id)
    except Exception:
        return []


@st.cache_data(ttl=600)  # Cache for 10 minutes
def _get_stats_cached():
    """Cached statistics with 10 minute TTL."""
    try:
        return get_candidate_statistics() or {}
    except Exception:
        return {}


def _clear_caches():
    """Clear all caches for refresh."""
    _get_candidates_cached.clear()
    _get_candidate_history_cached.clear()
    _get_stats_cached.clear()


# =============================================================================
# Interview helpers (formatting, filtering) - CLEAN VERSION
# =============================================================================

SYSTEM_HINT_WORDS = ("candidate record created", "record created", "created", "system", "import",
                     "candidate record updated", "record updated", "updated")


def _is_system_event(ev: Dict[str, Any]) -> bool:
    """Enhanced system event detection."""
    title = str(ev.get("title") or ev.get("event") or ev.get("details") or "").lower()
    actor = str(ev.get("actor") or ev.get("source") or ev.get("actor_type") or "").lower()
    etype = str(ev.get("type") or ev.get("event") or "").lower()

    # Check if it's a system event
    if any(w in title for w in SYSTEM_HINT_WORDS):
        return True
    if actor and ("portal" in actor or "candidate_portal" in actor or "system" in actor):
        return True
    if etype in ("system", "created", "import", "candidate_created", "candidate_updated"):
        return True

    # Additional check for system-like events
    if "candidate record" in title or "record updated" in title:
        return True

    return False


def _render_kv_block_clean(d: Dict[str, Any]):
    """Clean white text key-value block renderer."""
    html_content = ""
    for k, v in d.items():
        if v is None or v == "":
            continue
        if isinstance(v, (dict, list)):
            try:
                v = json.dumps(v, ensure_ascii=False)
            except Exception:
                v = str(v)

        field_name = _titleize_key(k)
        html_content += f"""
            <div style="margin-bottom: 8px;">
                <span style="color: #ffffff; font-weight: bold;">• {field_name}:</span>
                <span style="color: #ffffff; margin-left: 8px;">{v}</span>
            </div>
        """

    if html_content:
        st.markdown(
            f"""
            <div style="background-color: #000000; padding: 15px; border-radius: 8px; margin: 10px 0; border: 1px solid #333;">
                {html_content}
            </div>
            """,
            unsafe_allow_html=True
        )


def _format_interview_details(raw_details: str) -> str:
    """Format raw interview details into clean readable text."""
    if not raw_details or raw_details.strip() == "":
        return "No details provided"

    # If it's already formatted text, return as is
    if not (raw_details.strip().startswith("{") or raw_details.strip().startswith('"')):
        return raw_details

    try:
        # Try to parse as JSON
        if raw_details.strip().startswith("{"):
            import json
            data = json.loads(raw_details)
            formatted_lines = []

            # Format common interview fields
            field_mapping = {
                "age": "Age",
                "education": "Education",
                "family_background": "Family Background",
                "english": "English Skills",
                "experience_salary": "Experience & Salary",
                "attitude": "Attitude",
                "commitment": "Commitment Level",
                "no_festival_leave": "Available for Festivals",
                "own_pc": "Has Own PC",
                "continuous_night": "Continuous Night Shifts",
                "rotational_night": "Rotational Night Shifts",
                "profile_fit": "Profile Fit",
                "project_fit": "Project Fit",
                "grasping": "Learning Ability",
                "other_notes": "Additional Notes"
            }

            for key, value in data.items():
                if value and str(value).strip():
                    field_name = field_mapping.get(key, key.replace("_", " ").title())
                    formatted_lines.append(
                        f"<span style='color: #ffffff; font-weight: bold;'>{field_name}:</span> <span style='color: #ffffff;'>{value}</span>")

            return "<br>".join(formatted_lines) if formatted_lines else "No interview details recorded"

        # If starts with quotes, it might be a quoted string
        elif raw_details.strip().startswith('"') and raw_details.strip().endswith('"'):
            clean_text = raw_details.strip()[1:-1]  # Remove quotes
            return clean_text if clean_text else "No details provided"

    except (json.JSONDecodeError, Exception):
        pass

    # Fallback: return as is but clean it up
    cleaned_text = raw_details.replace("\\n", "\n").replace('\\"', '"')
    return cleaned_text


def _render_interview_card_clean(ev: Dict[str, Any]):
    """
    CLEAN: Render a single interview/event with simple black background and white text.
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
        # Handle string details that might contain result info
        raw_str = str(raw_details or "")
        if raw_str.startswith("Result: "):
            parts = raw_str.split("Result: ", 1)
            if len(parts) > 1 and ", Notes: " in parts[1]:
                result_and_notes = parts[1].split(", Notes: ", 1)
                result = result_and_notes[0]
                notes = result_and_notes[1] if len(result_and_notes) > 1 else ""
            else:
                result = parts[1] if len(parts) > 1 else None
                notes = ""
        else:
            notes = raw_str

    # Format header info
    header_info = []
    if result and result != "unspecified":
        header_info.append(f"<span style='color: #ffffff; font-weight: bold;'>{result}</span>")
    if when:
        header_info.append(f"<span style='color: #cccccc;'>{_format_datetime(when)}</span>")

    # Create clean interview card
    header_extra = f" • {' • '.join(header_info)}" if header_info else ""

    st.markdown(
        f"""
        <div style="background-color: #000000; padding: 20px; border-radius: 8px; margin-bottom: 15px; border: 1px solid #333;">
            <div style="margin-bottom: 15px;">
                <span style="color: #ffffff; font-size: 18px; font-weight: bold;">👤 {interviewer}</span>
                {header_extra}
            </div>
        """,
        unsafe_allow_html=True
    )

    # Format and display notes
    if notes and notes.strip():
        formatted_notes = _format_interview_details(notes)

        st.markdown(
            f"""
            <div style="background-color: #000000; padding: 15px; border-radius: 8px; margin: 10px 0;">
                <div style="color: #ffffff; line-height: 1.6; font-size: 14px;">
                    {formatted_notes}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    # Show event metadata
    ev_id = ev.get("id") or ev.get("event_id") or "—"
    actor_id = ev.get("actor_id") or ev.get("user_id") or "—"

    st.markdown(
        f"""
            <div style="color: #cccccc; font-size: 12px; margin-top: 10px;">
                Event ID: {ev_id} • Actor ID: {actor_id}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("---")


# =============================================================================
# Candidate summary - COMPLETE FORM DATA VERSION
# =============================================================================

def _render_candidate_summary_complete(c: Dict[str, Any]):
    """Display complete candidate information including all form questions."""

    # Basic candidate info
    candidate_name = c.get('name') or '—'
    candidate_id = c.get('candidate_id') or c.get('id')

    st.markdown(
        f"""
        <div style="background-color: #000000; padding: 20px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #333;">
            <h2 style="color: #ffffff; margin: 0 0 15px 0;">👤 {candidate_name}</h2>
            <div style="color: #ffffff; font-size: 14px; line-height: 1.6;">
                <div><strong>Candidate ID:</strong> {candidate_id}</div>
                <div><strong>Email:</strong> {c.get('email') or '—'}</div>
                <div><strong>Phone:</strong> {c.get('phone') or '—'}</div>
                <div><strong>Created At:</strong> {_format_datetime(c.get('created_at'))}</div>
                <div><strong>Updated At:</strong> {_format_datetime(c.get('updated_at'))}</div>
                <div><strong>Can Edit (candidate):</strong> {bool(c.get('can_edit', False))}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Complete form data from candidate_view.py
    form = c.get("form_data") or {}
    if isinstance(form, dict) and form:
        st.markdown(
            """
            <div style="background-color: #000000; padding: 15px; border-radius: 8px; margin: 10px 0; border: 1px solid #333;">
                <h4 style="color: #ffffff; margin: 0 0 15px 0;">📋 Complete Application Details</h4>
            """,
            unsafe_allow_html=True
        )

        # Map all form fields from candidate_view.py
        form_fields = {
            # Personal Information
            "name": "Full Name",
            "email": "Email Address",
            "phone": "Phone Number",
            "dob": "Date of Birth",
            "current_address": "Current Address",
            "permanent_address": "Permanent Address",
            "caste": "Caste",
            "sub_caste": "Sub-caste",
            "marital_status": "Marital Status",

            # Education & Experience
            "highest_qualification": "Highest Qualification",
            "work_experience": "Work Experience",
            "referral": "How did you hear about us?",

            # Availability Questions
            "ready_festivals": "Ready to work on festivals and national holidays?",
            "ready_late_nights": "Ready to work late nights if needed?",

            # Timestamps
            "updated_at": "Last Updated"
        }

        form_html = ""
        for field_key, field_label in form_fields.items():
            value = form.get(field_key)
            if value is not None and str(value).strip():
                # Format the value
                if field_key in ["ready_festivals", "ready_late_nights"]:
                    display_value = "✅ Yes" if value == "Yes" else "❌ No"
                elif field_key == "dob":
                    try:
                        # Try to format date nicely
                        if isinstance(value, str):
                            from datetime import datetime
                            dt = datetime.fromisoformat(value)
                            display_value = dt.strftime("%B %d, %Y")
                        else:
                            display_value = str(value)
                    except:
                        display_value = str(value)
                elif field_key in ["current_address", "permanent_address", "work_experience"]:
                    # Multi-line fields
                    display_value = str(value).replace('\n', '<br>')
                else:
                    display_value = str(value)

                form_html += f"""
                    <div style="margin-bottom: 12px; border-bottom: 1px solid #333; padding-bottom: 8px;">
                        <div style="color: #ffffff; font-weight: bold; margin-bottom: 4px;">{field_label}:</div>
                        <div style="color: #ffffff; margin-left: 15px; line-height: 1.5;">{display_value}</div>
                    </div>
                """

        if form_html:
            st.markdown(
                f"""
                <div style="color: #ffffff; line-height: 1.6;">
                    {form_html}
                </div>
                </div>
                """,
                unsafe_allow_html=True
            )
        else:
            st.markdown("</div>", unsafe_allow_html=True)
            st.info("No detailed form data available.")


# =============================================================================
# CEO Dashboard (main) - SIMPLIFIED
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
            with st.spinner("Loading candidates..."):
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
                # Complete candidate summary with all form data
                try:
                    _render_candidate_summary_complete(c)
                except Exception:
                    st.error("Error rendering candidate summary.")
                    st.write(json.dumps(c, default=str))

                # ===================== SIMPLE CV Access & Preview Section =====================
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
                        # Fetch CV securely from database
                        cv_bytes, cv_name, reason = _safe_get_candidate_cv_fixed(cid, actor_id)

                        # Handle CV fetch results
                        if reason == "no_permission":
                            st.warning("❌ You don't have permission to view CVs for this candidate.")

                        elif reason == "not_found":
                            st.info("📂 No CV uploaded yet.")

                        elif reason == "link_only":
                            st.info(f"📎 CV available as link")
                            col1, col2 = st.columns([1, 1])
                            with col1:
                                if st.button("🔗 Open CV Link", key=f"link_{cid}"):
                                    components.html(f"""
                                        <script>
                                        window.open('{cv_name}', '_blank');
                                        </script>
                                        <p>Opening CV in new tab...</p>
                                    """, height=50)
                            with col2:
                                st.markdown(f"[📄 Direct Link]({cv_name})", unsafe_allow_html=True)

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

                            # 3️⃣ Open in New Tab Button (Auto-redirect)
                            with col3:
                                if st.button("↗️ Open in New Tab", key=f"newtab_{cid}"):
                                    ok = _open_file_auto_redirect(cv_bytes, mimetype, cid)
                                    if not ok:
                                        st.info("⚠️ Failed to open in new tab. Please use **Download** instead.")

                            # 4️⃣ Simple Inline Preview (if requested)
                            if st.session_state.get(f"preview_{cid}", False):
                                if mimetype == "application/pdf":
                                    # Simple PDF preview
                                    ok = _simple_pdf_preview(cv_bytes, unique_key=cid)
                                    if not ok:
                                        st.info("PDF preview not available. Please download the file.")

                                elif mimetype.startswith("text/"):
                                    _preview_text(cv_bytes)

                                elif mimetype.startswith("image/"):
                                    _preview_image(cv_bytes, caption=cv_name or cid)

                                elif mimetype in (
                                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                        "application/msword",
                                ):
                                    st.info(
                                        "📄 Word document preview is not supported. Please download to view the full document.")

                                else:
                                    st.info("Preview isn't available for this file type. Please download to view.")

                        elif reason == "error":
                            st.error("❌ Error occurred while fetching CV.")

                except Exception as e:
                    st.error(f"Unexpected error while handling CV: {e}")

                # Clean Interview history (skip system events)
                try:
                    with st.spinner("Loading interview history..."):
                        history = get_candidate_history(c.get("candidate_id"))
                    if history is None:
                        st.info("No interview history available.")
                    else:
                        real_history = [ev for ev in history if not _is_system_event(ev)]
                        if not real_history:
                            st.info("No interviews recorded yet.")
                        else:
                            st.markdown("#### 📋 Interview History")
                            # Only show actual interviews, not system events
                            for ev in real_history:
                                _render_interview_card_clean(ev)
                except Exception as e:
                    st.error(f"Interview history error: {str(e)}")
                    # Don't show full traceback in production
                    if st.session_state.get("debug_mode", False):
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
                except Exception as e:
                    st.error(f"Failed to render toggle: {e}")

    # Footer tip
    st.markdown("---")
    st.caption(
        "💡 Simplified PDF preview and clean interview display. Auto-redirect opens files in new tab automatically.")


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