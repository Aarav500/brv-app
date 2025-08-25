# =============================================================================
# Fixed CEO Control Panel - Access Rights & Data Display Corrected
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

@st.cache_data(ttl=60, show_spinner=False)
def _get_candidates_fast():
    """Fast candidate loading with complete form data."""
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("""
                        SELECT candidate_id,
                               name,
                               email,
                               phone,
                               address,
                               dob,
                               caste,
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
                # Parse form_data to get complete application details
                form_data = row[12] if row[12] else {}

                candidate = {
                    'candidate_id': row[0],
                    'name': row[1],
                    'email': row[2],
                    'phone': row[3],
                    'address': row[4],
                    'dob': row[5],
                    'caste': row[6],
                    'created_at': row[7],
                    'updated_at': row[8],
                    'can_edit': row[9],
                    'has_cv_file': row[10],
                    'has_resume_link': row[11],
                    'form_data': form_data
                }
                candidates.append(candidate)

            conn.close()
            return candidates
    except Exception as e:
        st.error(f"Failed to load candidates: {e}")
        return []


@st.cache_data(ttl=300, show_spinner=False)
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
    """Check user permissions with proper error handling."""
    try:
        perms = get_user_permissions(user_id)
        if not perms:
            return {"role": "user", "can_view_cvs": False, "can_delete_records": False, "can_manage_users": False}

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
            "can_manage_users": role == "admin"  # Only admins can manage users
        }
    except Exception as e:
        st.error(f"Permission check failed: {e}")
        return {"role": "user", "can_view_cvs": False, "can_delete_records": False, "can_manage_users": False}


# =============================================================================
# Fixed CV Access with Proper Rights Check
# =============================================================================

def _get_cv_with_proper_access(candidate_id: str, user_id: int) -> Tuple[Optional[bytes], Optional[str], str]:
    """Get CV with proper access control - fixed version."""
    try:
        # First check if user has CV viewing permissions
        perms = _check_user_permissions(user_id)

        # For CEO/Admin role or explicit can_view_cvs permission
        if not (perms.get("role") in ("ceo", "admin") or perms.get("can_view_cvs", False)):
            return None, None, "no_permission"

        # Use the secure CV fetch function with proper actor_id
        result = get_candidate_cv_secure(candidate_id, user_id)

        # Handle different return formats from get_candidate_cv_secure
        if isinstance(result, tuple):
            if len(result) == 4:
                cv_bytes, cv_filename, mime_type, reason = result
            elif len(result) == 3:
                cv_bytes, cv_filename, reason = result
                mime_type = None
            else:
                return None, None, "error"

            if reason == "ok" and cv_bytes:
                return bytes(cv_bytes), cv_filename or f"{candidate_id}.pdf", "ok"
            elif reason == "no_permission":
                return None, None, "no_permission"
            elif reason == "not_found":
                return None, None, "not_found"
            else:
                return None, None, "error"
        elif isinstance(result, (bytes, bytearray)):
            return bytes(result), f"{candidate_id}.pdf", "ok"
        else:
            return None, None, "not_found"

    except Exception as e:
        st.error(f"CV fetch error: {e}")
        return None, None, "error"


# =============================================================================
# Complete Form Data Display - Fixed
# =============================================================================

def _render_complete_application_details(candidate: Dict[str, Any]):
    """Render ALL application details from both top-level and form_data fields."""

    st.markdown("### 📋 Complete Application Details")

    # Combine data from top-level fields and form_data
    form_data = candidate.get('form_data', {}) or {}

    # Field mapping for better display
    field_labels = {
        "name": "👤 Full Name",
        "email": "📧 Email Address",
        "phone": "📱 Phone Number",
        "dob": "🎂 Date of Birth",
        "address": "🏠 Address (from record)",
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
        "created_at": "📅 Application Created",
        "updated_at": "🕐 Last Updated"
    }

    # Create comprehensive data dictionary
    all_data = {}

    # Add top-level fields
    for key in ["name", "email", "phone", "address", "dob", "caste", "created_at", "updated_at"]:
        value = candidate.get(key)
        if value and str(value).strip():
            all_data[key] = value

    # Add form_data fields (these take precedence for duplicates)
    for key, value in form_data.items():
        if value and str(value).strip():
            all_data[key] = value

    if not all_data:
        st.info("📋 No detailed application information available")
        return

    # Display in two columns for better layout
    col1, col2 = st.columns(2)

    # Split data into two columns
    data_items = list(all_data.items())
    mid_point = (len(data_items) + 1) // 2

    with col1:
        for key, value in data_items[:mid_point]:
            if value and str(value).strip():
                label = field_labels.get(key, key.replace('_', ' ').title())

                # Special formatting for specific fields
                if key in ["ready_festivals", "ready_late_nights"]:
                    display_value = "✅ Yes" if str(value).lower() == "yes" else "❌ No"
                elif key in ["dob", "created_at", "updated_at"]:
                    display_value = _format_datetime(value)
                else:
                    display_value = str(value)

                st.markdown(f"**{label}:** {display_value}")

    with col2:
        for key, value in data_items[mid_point:]:
            if value and str(value).strip():
                label = field_labels.get(key, key.replace('_', ' ').title())

                # Special formatting for specific fields
                if key in ["ready_festivals", "ready_late_nights"]:
                    display_value = "✅ Yes" if str(value).lower() == "yes" else "❌ No"
                elif key in ["dob", "created_at", "updated_at"]:
                    display_value = _format_datetime(value)
                else:
                    display_value = str(value)

                st.markdown(f"**{label}:** {display_value}")


# =============================================================================
# Fixed Interview History Display
# =============================================================================

def _get_interview_history_fixed(candidate_id: str) -> List[Dict[str, Any]]:
    """Get interview history with better filtering."""
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            # Get all history records, not just those without 'created' in details
            cur.execute("""
                        SELECT id, actor, created_at, details, actor_id
                        FROM candidate_history
                        WHERE candidate_id = %s
                        ORDER BY created_at DESC LIMIT 50
                        """, (candidate_id,))

            history = []
            for row in cur.fetchall():
                history.append({
                    'id': row[0],
                    'actor': row[1] or 'Unknown',
                    'created_at': row[2],
                    'details': row[3] or '',
                    'actor_id': row[4]
                })

            conn.close()
            return history
    except Exception as e:
        st.error(f"Error loading interview history: {e}")
        return []


def _render_interview_history_fixed(history_records: List[Dict[str, Any]]):
    """Render interview history with better categorization."""
    if not history_records:
        st.info("📝 No interview history found")
        return

    # Separate different types of records
    interviews = []
    assessments = []
    system_records = []

    for record in history_records:
        details = record.get('details', '').lower()

        # Categorize based on content
        if any(keyword in details for keyword in ['interview', 'meeting', 'discussion', 'call']):
            interviews.append(record)
        elif any(keyword in details for keyword in ['assessment', 'test', 'evaluation', 'score']):
            assessments.append(record)
        elif any(keyword in details for keyword in ['created', 'system', 'automatic']):
            system_records.append(record)
        else:
            # If it has substantial content, treat as interview
            if len(details.strip()) > 20:
                interviews.append(record)
            else:
                system_records.append(record)

    # Display interviews
    if interviews:
        st.markdown("#### 🎤 Interviews & Discussions")
        for interview in interviews:
            _render_single_record(interview)

    # Display assessments
    if assessments:
        st.markdown("#### 📊 Assessments")
        for assessment in assessments:
            _render_single_record(assessment)

    # Display system records if they contain useful info
    if system_records:
        with st.expander("🔧 System Records", expanded=False):
            for record in system_records:
                _render_single_record(record)

    if not interviews and not assessments:
        st.info("📝 No interviews or assessments recorded yet")


def _render_single_record(record: Dict[str, Any]):
    """Render a single history record."""
    actor = record.get('actor', 'Unknown')
    when = _format_datetime(record.get('created_at'))
    details = record.get('details', '')

    with st.container():
        st.markdown(f"**👤 {actor}** • {when}")

        if details:
            # Try to parse as JSON for structured display
            try:
                if details.strip().startswith('{') and details.strip().endswith('}'):
                    data = json.loads(details)
                    if isinstance(data, dict):
                        for key, value in data.items():
                            if value and str(value).strip():
                                clean_key = key.replace('_', ' ').title()
                                st.markdown(f"• **{clean_key}:** {value}")
                    else:
                        st.markdown(f"📝 {details}")
                else:
                    st.markdown(f"📝 {details}")
            except json.JSONDecodeError:
                st.markdown(f"📝 {details}")

        st.markdown("---")


# =============================================================================
# Utility Functions
# =============================================================================

def _format_datetime(dt) -> str:
    """Format datetime with better handling."""
    if not dt:
        return "—"
    if isinstance(dt, str):
        try:
            # Handle ISO format strings
            if 'T' in dt:
                dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
            else:
                dt = datetime.fromisoformat(dt)
        except:
            return dt
    try:
        return dt.strftime("%Y-%m-%d %H:%M")
    except:
        return str(dt)


def _detect_mimetype(filename: str) -> str:
    """Detect mimetype from filename."""
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
# Enhanced PDF Preview
# =============================================================================

def _render_cv_section_fixed(candidate_id: str, user_id: int, has_cv_file: bool, has_resume_link: bool):
    """Render CV section with proper access control."""
    st.markdown("### 📄 CV & Documents")

    if not (has_cv_file or has_resume_link):
        st.info("📂 No CV uploaded")
        return

    # Check permissions
    perms = _check_user_permissions(user_id)
    can_view = perms.get("role") in ("ceo", "admin") or perms.get("can_view_cvs", False)

    if not can_view:
        st.warning("🔒 You don't have permission to view CVs")
        return

    # Get CV data
    cv_bytes, cv_name, status = _get_cv_with_proper_access(candidate_id, user_id)

    if status == "ok" and cv_bytes:
        # Create download button
        st.download_button(
            "📥 Download CV",
            data=cv_bytes,
            file_name=cv_name or f"{candidate_id}_cv.pdf",
            mime=_detect_mimetype(cv_name or ""),
            key=f"cv_dl_{candidate_id}"
        )

        # Show PDF preview if it's a PDF
        if cv_name and cv_name.lower().endswith('.pdf'):
            try:
                b64 = base64.b64encode(cv_bytes).decode()
                st.markdown(f"""
                    <iframe 
                        src="data:application/pdf;base64,{b64}" 
                        width="100%" 
                        height="500px" 
                        style="border: 1px solid #ddd; border-radius: 5px;">
                    </iframe>
                """, unsafe_allow_html=True)
            except Exception:
                st.info("📄 PDF preview not available, but file can be downloaded")

    elif status == "no_permission":
        st.warning("🔒 Access denied to CV")
    elif status == "not_found":
        st.info("📂 CV file not found")
    else:
        st.error("❌ Error accessing CV")


# =============================================================================
# Fixed User Management - Only Show Actual Users
# =============================================================================

def _get_actual_users_only():
    """Get only actual system users, not candidate records."""
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            # Get users from the users table, not candidates table
            cur.execute("""
                        SELECT u.id,
                               u.email,
                               u.created_at,
                               u.role,
                               up.can_view_cvs,
                               up.can_delete_records
                        FROM users u
                                 LEFT JOIN user_permissions up ON u.id = up.user_id
                        WHERE u.email IS NOT NULL
                          AND u.email != ''
                        ORDER BY u.created_at DESC
                        """)

            users = []
            for row in cur.fetchall():
                users.append({
                    'id': row[0],
                    'email': row[1],
                    'created_at': row[2],
                    'role': row[3] or 'user',
                    'can_view_cvs': bool(row[4]) if row[4] is not None else False,
                    'can_delete_records': bool(row[5]) if row[5] is not None else False
                })

            conn.close()
            return users
    except Exception as e:
        st.error(f"Error loading users: {e}")
        return []


def show_user_management_panel():
    """Fixed user management panel - only shows actual users."""
    require_login()

    user = get_current_user(refresh=True)
    perms = _check_user_permissions(user.get("id"))

    if not perms.get("can_manage_users", False):
        st.error("Access denied. Admin privileges required.")
        st.stop()

    st.title("👥 User Management")
    st.caption("Manage system user permissions")

    users = _get_actual_users_only()

    if not users:
        st.info("No system users found.")
        return

    for user_data in users:
        user_id = user_data.get('id')
        user_email = user_data.get('email', 'No email')
        user_role = user_data.get('role', 'user')

        with st.expander(f"👤 {user_email} (Role: {user_role})"):
            st.markdown(f"""
            **User ID:** {user_id}  
            **Email:** {user_email}  
            **Role:** {user_role}  
            **Created:** {_format_datetime(user_data.get('created_at'))}
            """)

            # Permission controls (only for non-CEO/admin users)
            if user_role.lower() not in ('ceo', 'admin'):
                col1, col2 = st.columns(2)

                with col1:
                    can_view_cvs = st.checkbox(
                        "Can View CVs",
                        value=user_data.get('can_view_cvs', False),
                        key=f"cv_{user_id}",
                        help="Allow this user to view candidate CVs"
                    )

                with col2:
                    can_delete = st.checkbox(
                        "Can Delete Records",
                        value=user_data.get('can_delete_records', False),
                        key=f"del_{user_id}",
                        help="Allow this user to delete candidate records"
                    )

                if st.button("💾 Update Permissions", key=f"save_{user_id}"):
                    new_perms = {
                        "can_view_cvs": can_view_cvs,
                        "can_delete_records": can_delete
                    }

                    try:
                        if update_user_permissions(user_id, new_perms):
                            st.success("✅ Permissions updated!")
                            st.rerun()
                        else:
                            st.error("❌ Update failed")
                    except Exception as e:
                        st.error(f"Error updating permissions: {e}")
            else:
                st.info("🔑 CEO/Admin users have all permissions by default")


# =============================================================================
# Main CEO Dashboard - Fixed Version
# =============================================================================

def show_ceo_panel():
    """Fixed CEO dashboard with proper access controls and complete data display."""
    require_login()

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

    # Quick stats
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

    # Candidate management section
    st.header("👥 Candidate Management")

    # Controls
    ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4 = st.columns([3, 1, 1, 1])

    with ctrl_col1:
        search_term = st.text_input("🔍 Search candidates", key="search")

    with ctrl_col2:
        show_no_cv = st.checkbox("📂 No CV only", key="filter_no_cv")

    with ctrl_col3:
        select_all = st.checkbox("☑️ Select all", key="select_all")

    with ctrl_col4:
        if st.button("🔄 Refresh"):
            _clear_candidate_cache()
            st.rerun()

    # Load candidates
    candidates = _get_candidates_fast()

    if not candidates:
        st.warning("No candidates found.")
        return

    # Filter candidates
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
            success_count = 0
            for candidate_id in list(selected):
                if _delete_candidate_fast(candidate_id, user_id):
                    success_count += 1

            st.success(f"Deleted {success_count} candidates")
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
                        # Complete application details - FIXED
                        _render_complete_application_details(candidate)

                        # CV Section - FIXED with proper access control
                        _render_cv_section_fixed(
                            candidate_id,
                            user_id,
                            candidate.get('has_cv_file', False),
                            candidate.get('has_resume_link', False)
                        )

                        # Interview History - FIXED
                        st.markdown("### 🎤 Interview History")
                        history = _get_interview_history_fixed(candidate_id)
                        _render_interview_history_fixed(history)

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
                                    st.success("Updated edit permission")
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
    """Delete candidate with proper error handling."""
    try:
        success, reason = delete_candidate(candidate_id, user_id)
        return success
    except Exception as e:
        st.error(f"Delete error: {e}")
        return False


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
    st.sidebar.caption("⚡ Fixed: CV Access, Complete Data Display, User Management")

    # Run selected page
    pages[selected_page]()


if __name__ == "__main__":
    main()