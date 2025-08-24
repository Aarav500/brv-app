# =============================================================================
# Fixed CEO Control Panel - Performance & Access Rights Optimized
# =============================================================================

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

# Set page config once
try:
    st.set_page_config(page_title="CEO Control Panel", layout="wide")
except Exception:
    pass

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
# Performance Optimizations
# =============================================================================

# Cache with shorter TTL and session-based invalidation
@st.cache_data(ttl=60, show_spinner=False)  # 1 minute cache
def _get_candidates_fast():
    """Fast candidate loading with minimal queries."""
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("""
                        SELECT candidate_id,
                               name,
                               email,
                               phone,
                               created_at,
                               updated_at,
                               can_edit,
                               cv_file IS NOT NULL     as has_cv_file,
                               resume_link IS NOT NULL as has_resume_link,
                               form_data
                        FROM candidates
                        ORDER BY created_at DESC LIMIT 1000
                        """)

            candidates = []
            for row in cur.fetchall():
                candidate = {
                    'candidate_id': row[0],
                    'name': row[1],
                    'email': row[2],
                    'phone': row[3],
                    'created_at': row[4],
                    'updated_at': row[5],
                    'can_edit': row[6],
                    'has_cv_file': row[7],
                    'has_resume_link': row[8],
                    'form_data': row[9] if row[9] else {}
                }
                candidates.append(candidate)

            conn.close()
            return candidates
    except Exception as e:
        st.error(f"Failed to load candidates: {e}")
        return []


@st.cache_data(ttl=300, show_spinner=False)  # 5 minute cache for stats
def _get_stats_fast():
    """Fast statistics loading."""
    try:
        return get_candidate_statistics() or {}
    except Exception:
        return {}


def _clear_candidate_cache():
    """Clear candidate cache for refresh."""
    _get_candidates_fast.clear()
    _get_stats_fast.clear()


# =============================================================================
# Fixed Access Rights Check
# =============================================================================

def _check_user_permissions(user_id: int) -> Dict[str, Any]:
    """Check user permissions with proper caching and error handling."""
    try:
        # Get fresh permissions from database
        perms = get_user_permissions(user_id)
        if not perms:
            return {"role": "user", "can_view_cvs": False, "can_delete_records": False}

        role = (perms.get("role") or "user").lower()

        # CEO and admin get all permissions automatically
        if role in ("ceo", "admin"):
            return {
                "role": role,
                "can_view_cvs": True,
                "can_delete_records": True,
                "can_manage_users": True
            }

        return {
            "role": role,
            "can_view_cvs": bool(perms.get("can_view_cvs", False)),
            "can_delete_records": bool(perms.get("can_delete_records", False)),
            "can_manage_users": False
        }
    except Exception as e:
        st.error(f"Permission check failed: {e}")
        return {"role": "user", "can_view_cvs": False, "can_delete_records": False}


# =============================================================================
# Fast CV Access
# =============================================================================

def _get_cv_fast(candidate_id: str, user_id: int) -> Tuple[Optional[bytes], Optional[str], str]:
    """Fast CV retrieval with proper access control."""
    try:
        # Check permissions first
        perms = _check_user_permissions(user_id)
        if not perms.get("can_view_cvs", False):
            return None, None, "no_permission"

        # Single query to get CV
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

                if cv_file:
                    return bytes(cv_file), cv_filename or f"{candidate_id}.pdf", "ok"
                elif resume_link and resume_link.strip():
                    return None, resume_link.strip(), "link_only"
                else:
                    return None, None, "not_found"

        finally:
            conn.close()

    except Exception as e:
        st.error(f"CV fetch error: {e}")
        return None, None, "error"


# =============================================================================
# Utility Functions
# =============================================================================

def _format_datetime(dt) -> str:
    """Fast datetime formatting."""
    if not dt:
        return "—"
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except:
            return dt
    try:
        return dt.strftime("%Y-%m-%d %H:%M")
    except:
        return str(dt)


def _detect_mimetype(filename: str) -> str:
    """Fast mimetype detection."""
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


# =============================================================================
# Fast Form Data Display
# =============================================================================

def _render_application_details_fast(form_data: Dict[str, Any]):
    """Fast rendering of complete application details."""
    if not form_data or not isinstance(form_data, dict):
        st.info("📋 No application details available")
        return

    # Field mapping for better display
    field_labels = {
        "name": "👤 Full Name",
        "email": "📧 Email Address",
        "phone": "📱 Phone Number",
        "dob": "🎂 Date of Birth",
        "current_address": "🏠 Current Address",
        "permanent_address": "🏡 Permanent Address",
        "caste": "📋 Caste",
        "sub_caste": "📋 Sub-caste",
        "marital_status": "💑 Marital Status",
        "highest_qualification": "🎓 Highest Qualification",
        "work_experience": "💼 Work Experience",
        "referral": "📢 How did you hear about us?",
        "ready_festivals": "🎊 Ready to work on festivals?",
        "ready_late_nights": "🌙 Ready to work late nights?",
        "updated_at": "🕐 Last Updated"
    }

    st.markdown("### 📋 Complete Application Details")

    # Create two columns for better layout
    col1, col2 = st.columns(2)

    form_items = list(form_data.items())
    mid_point = len(form_items) // 2

    with col1:
        for key, value in form_items[:mid_point]:
            if value and str(value).strip():
                label = field_labels.get(key, key.replace('_', ' ').title())

                if key in ["ready_festivals", "ready_late_nights"]:
                    display_value = "✅ Yes" if str(value).lower() == "yes" else "❌ No"
                elif key == "dob":
                    try:
                        if isinstance(value, str):
                            dt = datetime.fromisoformat(value)
                            display_value = dt.strftime("%B %d, %Y")
                        else:
                            display_value = str(value)
                    except:
                        display_value = str(value)
                else:
                    display_value = str(value)

                st.markdown(f"**{label}:** {display_value}")

    with col2:
        for key, value in form_items[mid_point:]:
            if value and str(value).strip():
                label = field_labels.get(key, key.replace('_', ' ').title())

                if key in ["ready_festivals", "ready_late_nights"]:
                    display_value = "✅ Yes" if str(value).lower() == "yes" else "❌ No"
                elif key == "dob":
                    try:
                        if isinstance(value, str):
                            dt = datetime.fromisoformat(value)
                            display_value = dt.strftime("%B %d, %Y")
                        else:
                            display_value = str(value)
                    except:
                        display_value = str(value)
                else:
                    display_value = str(value)

                st.markdown(f"**{label}:** {display_value}")


# =============================================================================
# Fast Interview History
# =============================================================================

def _get_interview_history_fast(candidate_id: str) -> List[Dict[str, Any]]:
    """Fast interview history loading."""
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("""
                        SELECT id, actor, created_at, details, actor_id
                        FROM candidate_history
                        WHERE candidate_id = %s
                          AND (details NOT ILIKE '%candidate record created%' 
                     AND details NOT ILIKE '%record created%'
                     AND details NOT ILIKE '%system%')
                        ORDER BY created_at DESC LIMIT 20
                        """, (candidate_id,))

            history = []
            for row in cur.fetchall():
                history.append({
                    'id': row[0],
                    'actor': row[1],
                    'created_at': row[2],
                    'details': row[3],
                    'actor_id': row[4]
                })

            conn.close()
            return history
    except Exception:
        return []


def _render_interview_fast(interview: Dict[str, Any]):
    """Fast interview rendering."""
    actor = interview.get('actor', '—')
    when = _format_datetime(interview.get('created_at'))
    details = interview.get('details', '')

    with st.container():
        st.markdown(f"**👤 {actor}** • {when}")

        if details:
            # Try to parse as JSON for structured display
            try:
                if details.startswith('{') and details.endswith('}'):
                    data = json.loads(details)
                    for key, value in data.items():
                        if value:
                            clean_key = key.replace('_', ' ').title()
                            st.markdown(f"• **{clean_key}:** {value}")
                else:
                    st.markdown(f"📝 {details}")
            except:
                st.markdown(f"📝 {details}")

        st.markdown("---")


# =============================================================================
# Simple PDF Preview
# =============================================================================

def _pdf_preview_fast(pdf_bytes: bytes, candidate_id: str):
    """Fast PDF preview with fallback options."""
    try:
        b64 = base64.b64encode(pdf_bytes).decode()

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "📥 Download PDF",
                data=pdf_bytes,
                file_name=f"{candidate_id}_cv.pdf",
                mime="application/pdf",
                key=f"pdf_dl_{candidate_id}"
            )

        with col2:
            if st.button("🔗 Open in New Tab", key=f"pdf_open_{candidate_id}"):
                components.html(f"""
                    <script>
                    window.open('data:application/pdf;base64,{b64}', '_blank');
                    </script>
                    <p>Opening in new tab...</p>
                """, height=50)

        # Simple iframe preview
        st.markdown(f"""
            <iframe 
                src="data:application/pdf;base64,{b64}" 
                width="100%" 
                height="500px" 
                style="border: 1px solid #ddd;">
            </iframe>
        """, unsafe_allow_html=True)

        return True
    except Exception:
        return False


# =============================================================================
# Main CEO Dashboard - Optimized
# =============================================================================

def show_ceo_panel():
    """Optimized CEO dashboard with fast loading."""
    require_login()

    # Get current user and check permissions
    user = get_current_user(refresh=True)
    if not user:
        st.error("Please log in again.")
        st.stop()

    user_id = user.get("id")
    perms = _check_user_permissions(user_id)

    if perms.get("role") not in ("ceo", "admin"):
        st.error("Access denied. CEO/Admin role required.")
        st.stop()

    st.title("🎯 CEO Dashboard")
    st.caption(f"Welcome {user.get('email', 'User')} | Role: {perms.get('role', 'Unknown').title()}")

    # Quick stats with caching
    with st.spinner("Loading dashboard..."):
        stats = _get_stats_fast()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📊 Total Candidates", stats.get("total_candidates", 0))
    with col2:
        st.metric("📅 Today", stats.get("candidates_today", 0))
    with col3:
        st.metric("🎤 Interviews", stats.get("total_interviews", 0))
    with col4:
        st.metric("📋 Assessments", stats.get("total_assessments", 0))

    st.markdown("---")

    # Fast candidate management
    st.header("👥 Candidate Management")

    # Controls row
    ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4 = st.columns([3, 1, 1, 1])

    with ctrl_col1:
        search_term = st.text_input("🔍 Search candidates", key="search",
                                    help="Search by name, email, or candidate ID")

    with ctrl_col2:
        show_no_cv = st.checkbox("📂 No CV only", key="filter_no_cv")

    with ctrl_col3:
        select_all = st.checkbox("☑️ Select all", key="select_all")

    with ctrl_col4:
        if st.button("🔄 Refresh", help="Reload data"):
            _clear_candidate_cache()
            st.rerun()

    # Load candidates with caching
    candidates = _get_candidates_fast()

    if not candidates:
        st.warning("No candidates found.")
        return

    # Fast filtering
    filtered_candidates = []
    search_lower = search_term.lower().strip() if search_term else ""

    for candidate in candidates:
        # Search filter
        if search_lower:
            searchable_text = f"{candidate.get('name', '')} {candidate.get('email', '')} {candidate.get('candidate_id', '')}".lower()
            if search_lower not in searchable_text:
                continue

        # CV filter
        if show_no_cv and (candidate.get('has_cv_file') or candidate.get('has_resume_link')):
            continue

        filtered_candidates.append(candidate)

    total_candidates = len(filtered_candidates)

    if total_candidates == 0:
        st.info("No candidates match your filters.")
        return

    # Pagination
    items_per_page = 10
    total_pages = (total_candidates + items_per_page - 1) // items_per_page

    if total_pages > 1:
        page = st.selectbox("📄 Page", range(1, total_pages + 1), key="page_select")
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_candidates = filtered_candidates[start_idx:end_idx]
        st.caption(f"Showing {start_idx + 1}-{min(end_idx, total_candidates)} of {total_candidates}")
    else:
        page_candidates = filtered_candidates

    # Selection management
    if 'selected_candidates' not in st.session_state:
        st.session_state.selected_candidates = set()

    selected = st.session_state.selected_candidates

    # Batch actions
    if perms.get("can_delete_records") and selected:
        if st.button(f"🗑️ Delete Selected ({len(selected)})", type="primary"):
            _batch_delete_fast(list(selected), user_id)
            st.session_state.selected_candidates.clear()
            _clear_candidate_cache()
            st.rerun()

    # Render candidates
    for candidate in page_candidates:
        candidate_id = candidate.get('candidate_id', '')
        candidate_name = candidate.get('name', 'Unnamed')

        # Selection checkbox
        is_selected = select_all or candidate_id in selected

        with st.container():
            sel_col, content_col = st.columns([0.05, 0.95])

            with sel_col:
                if st.checkbox("", value=is_selected, key=f"sel_{candidate_id}"):
                    selected.add(candidate_id)
                else:
                    selected.discard(candidate_id)

            with content_col:
                with st.expander(f"👤 {candidate_name} ({candidate_id})", expanded=False):
                    main_col, action_col = st.columns([3, 1])

                    with main_col:
                        # Basic info
                        st.markdown(f"""
                        **📧 Email:** {candidate.get('email', '—')}  
                        **📱 Phone:** {candidate.get('phone', '—')}  
                        **📅 Created:** {_format_datetime(candidate.get('created_at'))}  
                        **✏️ Can Edit:** {'Yes' if candidate.get('can_edit') else 'No'}
                        """)

                        # Application details
                        if candidate.get('form_data'):
                            with st.expander("📋 Application Details", expanded=True):
                                _render_application_details_fast(candidate.get('form_data', {}))

                        # CV Section
                        if perms.get("can_view_cvs"):
                            st.markdown("### 📄 CV & Documents")

                            if candidate.get('has_cv_file') or candidate.get('has_resume_link'):
                                cv_bytes, cv_name, status = _get_cv_fast(candidate_id, user_id)

                                if status == "ok" and cv_bytes:
                                    mimetype = _detect_mimetype(cv_name or "")

                                    if mimetype == "application/pdf":
                                        _pdf_preview_fast(cv_bytes, candidate_id)
                                    else:
                                        st.download_button(
                                            f"📥 Download {cv_name or 'CV'}",
                                            data=cv_bytes,
                                            file_name=cv_name or f"{candidate_id}_cv",
                                            key=f"cv_dl_{candidate_id}"
                                        )

                                elif status == "link_only":
                                    st.markdown(f"🔗 [Open CV Link]({cv_name})")

                                elif status == "no_permission":
                                    st.warning("🔒 No permission to view CV")

                                else:
                                    st.info("❌ CV access error")
                            else:
                                st.info("📂 No CV uploaded")

                        # Interview History
                        st.markdown("### 🎤 Interview History")
                        history = _get_interview_history_fast(candidate_id)

                        if history:
                            for interview in history[:5]:  # Show last 5
                                _render_interview_fast(interview)
                        else:
                            st.info("No interviews recorded")

                    with action_col:
                        st.markdown("### ⚙️ Actions")
                        st.caption(f"ID: {candidate_id}")

                        # Toggle edit permission
                        current_can_edit = candidate.get('can_edit', False)
                        toggle_label = "🔓 Grant Edit" if not current_can_edit else "🔒 Revoke Edit"

                        if st.button(toggle_label, key=f"toggle_{candidate_id}"):
                            try:
                                success = set_candidate_permission(candidate_id, not current_can_edit)
                                if success:
                                    st.success(f"Updated edit permission")
                                    _clear_candidate_cache()
                                    st.rerun()
                                else:
                                    st.error("Failed to update permission")
                            except Exception as e:
                                st.error(f"Error: {e}")

                        # Delete single candidate
                        if perms.get("can_delete_records"):
                            if st.button("🗑️ Delete", key=f"del_{candidate_id}", type="primary"):
                                if _delete_candidate_fast(candidate_id, user_id):
                                    st.success("Candidate deleted")
                                    _clear_candidate_cache()
                                    st.rerun()
                                else:
                                    st.error("Delete failed")


def _delete_candidate_fast(candidate_id: str, user_id: int) -> bool:
    """Fast candidate deletion."""
    try:
        ok, reason = delete_candidate(candidate_id, user_id)
        return ok
    except Exception:
        return False


def _batch_delete_fast(candidate_ids: List[str], user_id: int):
    """Fast batch deletion."""
    try:
        for cid in candidate_ids:
            delete_candidate(cid, user_id)
        st.success(f"Deleted {len(candidate_ids)} candidates")
    except Exception as e:
        st.error(f"Batch delete failed: {e}")


# =============================================================================
# User Management - Simplified
# =============================================================================

def show_user_management_panel():
    """Simplified user management."""
    require_login()

    user = get_current_user(refresh=True)
    perms = _check_user_permissions(user.get("id"))

    if not perms.get("can_manage_users", False):
        st.error("Access denied. Admin privileges required.")
        st.stop()

    st.title("👥 User Management")

    try:
        users = get_all_users_with_permissions() or []
    except Exception as e:
        st.error(f"Failed to load users: {e}")
        return

    for user_data in users:
        with st.expander(f"👤 {user_data.get('email', 'No email')}"):
            st.markdown(f"""
            **ID:** {user_data.get('id')}  
            **Role:** {user_data.get('role', 'user')}  
            **Created:** {_format_datetime(user_data.get('created_at'))}
            """)

            # Permission controls
            can_view_cvs = st.checkbox(
                "Can View CVs",
                value=bool(user_data.get('can_view_cvs', False)),
                key=f"cv_{user_data.get('id')}"
            )

            can_delete = st.checkbox(
                "Can Delete Records",
                value=bool(user_data.get('can_delete_records', False)),
                key=f"del_{user_data.get('id')}"
            )

            if st.button("💾 Update Permissions", key=f"save_{user_data.get('id')}"):
                new_perms = {
                    "can_view_cvs": can_view_cvs,
                    "can_delete_records": can_delete
                }

                try:
                    if update_user_permissions(user_data.get('id'), new_perms):
                        st.success("✅ Permissions updated!")
                        st.rerun()
                    else:
                        st.error("❌ Update failed")
                except Exception as e:
                    st.error(f"Error: {e}")


# =============================================================================
# Main Router
# =============================================================================

def main():
    """Main application router."""
    require_login()

    user = get_current_user(refresh=True)
    if not user:
        st.error("Authentication required")
        st.stop()

    perms = _check_user_permissions(user.get("id"))
    role = perms.get("role", "user")

    if role not in ("ceo", "admin"):
        st.error("Access denied. CEO/Admin role required.")
        st.stop()

    # Sidebar navigation
    st.sidebar.title("🎯 CEO Control Panel")
    st.sidebar.caption(f"👤 {user.get('email', 'User')}")
    st.sidebar.caption(f"🔑 Role: {role.title()}")
    st.sidebar.markdown("---")

    pages = {
        "📊 Dashboard": show_ceo_panel,
        "👥 Manage Users": show_user_management_panel
    }

    selected_page = st.sidebar.radio("Navigate to:", list(pages.keys()))
    st.sidebar.markdown("---")
    st.sidebar.caption("⚡ Optimized for speed and reliability")

    # Run selected page
    pages[selected_page]()


if __name__ == "__main__":
    main()