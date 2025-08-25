# =============================================================================
# Fixed CEO Control Panel - Complete Data Display & Working Delete
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
import psycopg2
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
    """Fast candidate loading with ALL available data from both columns and form_data."""
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            # Get ALL existing columns in candidates table
            cur.execute("""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = 'candidates'
                        ORDER BY ordinal_position
                        """)
            existing_columns = [row[0] for row in cur.fetchall()]

            # Build comprehensive SELECT to get all data
            select_parts = []

            # Always include these core columns
            core_columns = ['candidate_id', 'name', 'email', 'phone', 'created_at', 'updated_at', 'can_edit']
            for col in core_columns:
                if col in existing_columns:
                    select_parts.append(col)

            # Add all additional columns that exist
            additional_columns = [
                'address', 'current_address', 'permanent_address', 'dob', 'caste', 'sub_caste',
                'marital_status', 'highest_qualification', 'work_experience', 'referral',
                'ready_festivals', 'ready_late_nights', 'cv_filename', 'resume_link',
                'form_data', 'created_by'
            ]

            for col in additional_columns:
                if col in existing_columns:
                    select_parts.append(col)

            # Check for CV file existence
            if 'cv_file' in existing_columns:
                select_parts.append('cv_file IS NOT NULL as has_cv_file')
            else:
                select_parts.append('FALSE as has_cv_file')

            # Check for resume link existence
            if 'resume_link' in existing_columns:
                select_parts.append('resume_link IS NOT NULL AND resume_link != \'\' as has_resume_link')
            else:
                select_parts.append('FALSE as has_resume_link')

            # Build and execute query
            query = f"""
                SELECT {', '.join(select_parts)}
                FROM candidates
                ORDER BY created_at DESC LIMIT 1000
            """

            cur.execute(query)
            columns = [desc[0] for desc in cur.description]

            candidates = []
            for row in cur.fetchall():
                # Create candidate dict from row data
                candidate = {}
                for i, col_name in enumerate(columns):
                    candidate[col_name] = row[i]

                # Parse form_data if it exists and merge it with candidate data
                form_data = candidate.get('form_data', {})
                if isinstance(form_data, dict):
                    # Merge form_data into candidate (form_data takes precedence for duplicates)
                    for key, value in form_data.items():
                        if value is not None and str(value).strip():  # Only non-empty values
                            candidate[f'form_{key}'] = value  # Prefix to distinguish
                            # Also add without prefix if column doesn't exist directly
                            if key not in candidate:
                                candidate[key] = value

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
# Access Rights Check - Strict Permission Enforcement
# =============================================================================

def _check_user_permissions(user_id: int) -> Dict[str, Any]:
    """Check user permissions with STRICT enforcement."""
    try:
        perms = get_user_permissions(user_id)
        if not perms:
            return {"role": "user", "can_view_cvs": False, "can_delete_records": False, "can_manage_users": False}

        role = (perms.get("role") or "user").lower()

        return {
            "role": role,
            "can_view_cvs": bool(perms.get("can_view_cvs", False)),
            "can_delete_records": bool(perms.get("can_delete_records", False)),
            "can_manage_users": role in ("ceo", "admin")
        }
    except Exception as e:
        st.error(f"Permission check failed: {e}")
        return {"role": "user", "can_view_cvs": False, "can_delete_records": False, "can_manage_users": False}


# =============================================================================
# CV Access with Proper Rights Check
# =============================================================================

def _get_cv_with_proper_access(candidate_id: str, user_id: int) -> Tuple[Optional[bytes], Optional[str], str]:
    """Get CV with proper access control."""
    try:
        perms = _check_user_permissions(user_id)
        if not perms.get("can_view_cvs", False):
            return None, None, "no_permission"

        conn = get_conn()
        try:
            with conn.cursor() as cur:
                # Check what CV columns exist
                cur.execute("""
                            SELECT column_name
                            FROM information_schema.columns
                            WHERE table_name = 'candidates'
                              AND column_name IN ('cv_file', 'cv_filename', 'resume_link')
                            """)
                existing_cols = {row[0] for row in cur.fetchall()}

                select_parts = []
                if 'cv_file' in existing_cols:
                    select_parts.append('cv_file')
                if 'cv_filename' in existing_cols:
                    select_parts.append('cv_filename')
                if 'resume_link' in existing_cols:
                    select_parts.append('resume_link')

                if not select_parts:
                    return None, None, "not_found"

                query = f"SELECT {', '.join(select_parts)} FROM candidates WHERE candidate_id = %s"
                cur.execute(query, (candidate_id,))
                result = cur.fetchone()

                if not result:
                    return None, None, "not_found"

                cv_file = result[0] if len(result) > 0 and 'cv_file' in select_parts else None
                cv_filename = result[1] if len(result) > 1 and 'cv_filename' in select_parts else None
                resume_link = result[2] if len(result) > 2 and 'resume_link' in select_parts else None

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
# FIXED Complete Application Details Display - Shows ALL Information
# =============================================================================

def _render_complete_application_details(candidate: Dict[str, Any]):
    """Render ALL application details from both direct columns and form_data."""

    st.markdown("### 📋 Complete Application Details")

    # Comprehensive field mapping for better display
    field_labels = {
        "name": "👤 Full Name",
        "email": "📧 Email Address",
        "phone": "📱 Phone Number",
        "dob": "🎂 Date of Birth",
        "address": "🏠 Address",
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
        "updated_at": "🕐 Last Updated",
        "cv_filename": "📄 CV File Name",
        "resume_link": "🔗 Resume Link",
        "created_by": "👥 Created By"
    }

    # Collect ALL available data
    all_data = {}

    # Get data from direct columns
    for key, value in candidate.items():
        if key.startswith('form_'):
            # This is from form_data, use the key without prefix
            clean_key = key[5:]  # Remove 'form_' prefix
            if value and str(value).strip():
                all_data[clean_key] = value
        elif not key.startswith('has_') and key not in ['id', 'form_data']:
            # Regular column data
            if value and str(value).strip():
                all_data[key] = value

    # Also check form_data directly if it exists
    form_data = candidate.get('form_data', {})
    if isinstance(form_data, dict):
        for key, value in form_data.items():
            if value and str(value).strip():
                all_data[key] = value

    if not all_data:
        st.info("📋 No detailed application information available")
        return

    # Display in organized sections
    with st.container():
        # Basic Information Section
        st.markdown("#### 👤 Basic Information")
        basic_fields = ["name", "email", "phone"]
        basic_col1, basic_col2 = st.columns(2)

        basic_items = [(k, v) for k, v in all_data.items() if k in basic_fields]
        if basic_items:
            mid_basic = len(basic_items) // 2

            with basic_col1:
                for key, value in basic_items[:mid_basic + 1]:
                    label = field_labels.get(key, key.replace('_', ' ').title())
                    st.markdown(f"**{label}:** {value}")

            with basic_col2:
                for key, value in basic_items[mid_basic + 1:]:
                    label = field_labels.get(key, key.replace('_', ' ').title())
                    st.markdown(f"**{label}:** {value}")

        # Address Information Section
        st.markdown("#### 🏠 Address Information")
        address_fields = ["address", "current_address", "permanent_address"]
        address_items = [(k, v) for k, v in all_data.items() if k in address_fields]

        if address_items:
            for key, value in address_items:
                label = field_labels.get(key, key.replace('_', ' ').title())
                st.markdown(f"**{label}:** {value}")
        else:
            st.info("No address information available")

        # Personal Details Section
        st.markdown("#### 👥 Personal Details")
        personal_fields = ["dob", "caste", "sub_caste", "marital_status"]
        personal_items = [(k, v) for k, v in all_data.items() if k in personal_fields]

        if personal_items:
            personal_col1, personal_col2 = st.columns(2)
            mid_personal = len(personal_items) // 2

            with personal_col1:
                for key, value in personal_items[:mid_personal + 1]:
                    label = field_labels.get(key, key.replace('_', ' ').title())
                    display_value = _format_datetime(value) if key == "dob" else str(value)
                    st.markdown(f"**{label}:** {display_value}")

            with personal_col2:
                for key, value in personal_items[mid_personal + 1:]:
                    label = field_labels.get(key, key.replace('_', ' ').title())
                    display_value = _format_datetime(value) if key == "dob" else str(value)
                    st.markdown(f"**{label}:** {display_value}")
        else:
            st.info("No personal details available")

        # Professional Information Section
        st.markdown("#### 💼 Professional Information")
        prof_fields = ["highest_qualification", "work_experience", "referral"]
        prof_items = [(k, v) for k, v in all_data.items() if k in prof_fields]

        if prof_items:
            for key, value in prof_items:
                label = field_labels.get(key, key.replace('_', ' ').title())
                st.markdown(f"**{label}:** {value}")
        else:
            st.info("No professional information available")

        # Work Preferences Section
        st.markdown("#### ⚙️ Work Preferences")
        pref_fields = ["ready_festivals", "ready_late_nights"]
        pref_items = [(k, v) for k, v in all_data.items() if k in pref_fields]

        if pref_items:
            pref_col1, pref_col2 = st.columns(2)

            with pref_col1:
                for key, value in pref_items[:1]:
                    label = field_labels.get(key, key.replace('_', ' ').title())
                    display_value = "✅ Yes" if str(value).lower() in ["yes", "true", "1"] else "❌ No"
                    st.markdown(f"**{label}:** {display_value}")

            with pref_col2:
                for key, value in pref_items[1:]:
                    label = field_labels.get(key, key.replace('_', ' ').title())
                    display_value = "✅ Yes" if str(value).lower() in ["yes", "true", "1"] else "❌ No"
                    st.markdown(f"**{label}:** {display_value}")
        else:
            st.info("No work preference information available")

        # System Information Section
        st.markdown("#### 🔧 System Information")
        system_fields = ["created_at", "updated_at", "cv_filename", "resume_link", "created_by"]
        system_items = [(k, v) for k, v in all_data.items() if k in system_fields]

        if system_items:
            for key, value in system_items:
                label = field_labels.get(key, key.replace('_', ' ').title())
                if key in ["created_at", "updated_at"]:
                    display_value = _format_datetime(value)
                elif key == "resume_link":
                    display_value = f"[Open Link]({value})" if value else str(value)
                else:
                    display_value = str(value)
                st.markdown(f"**{label}:** {display_value}")

        # Additional Information Section (for any remaining fields)
        remaining_items = [(k, v) for k, v in all_data.items()
                           if k not in (basic_fields + address_fields + personal_fields +
                                        prof_fields + pref_fields + system_fields)]

        if remaining_items:
            st.markdown("#### 📋 Additional Information")
            for key, value in remaining_items:
                label = key.replace('_', ' ').title()
                st.markdown(f"**{label}:** {value}")


# =============================================================================
# Interview History Display (Fixed)
# =============================================================================

def _get_interview_history_fixed(candidate_id: str) -> List[Dict[str, Any]]:
    """Get interview history from available tables."""
    history = []

    try:
        conn = get_conn()
        with conn.cursor() as cur:
            # Check what tables exist
            cur.execute("""
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                          AND table_name IN ('candidate_history', 'interviews', 'receptionist_assessments')
                        """)
            existing_tables = {row[0] for row in cur.fetchall()}

            # Get from interviews table
            if 'interviews' in existing_tables:
                try:
                    cur.execute("""
                                SELECT id, interviewer, created_at, scheduled_at, result, notes
                                FROM interviews
                                WHERE candidate_id = %s
                                ORDER BY COALESCE(scheduled_at, created_at) DESC
                                """, (candidate_id,))

                    for row in cur.fetchall():
                        interview_details = []
                        if row[4]:  # result
                            interview_details.append(f"Result: {row[4]}")
                        if row[5]:  # notes
                            interview_details.append(f"Notes: {row[5]}")

                        event_time = row[3] if row[3] else row[2]

                        history.append({
                            'id': f"interview_{row[0]}",
                            'actor': row[1] or 'Interviewer',
                            'created_at': event_time,
                            'details': '; '.join(interview_details) if interview_details else 'Interview scheduled',
                            'source': 'interview'
                        })
                except Exception as e:
                    st.warning(f"Could not load interviews: {e}")

            # Get from receptionist_assessments table
            if 'receptionist_assessments' in existing_tables:
                try:
                    cur.execute("""
                                SELECT id,
                                       created_at,
                                       speed_test,
                                       accuracy_test,
                                       work_commitment,
                                       english_understanding,
                                       comments
                                FROM receptionist_assessments
                                WHERE candidate_id = %s
                                ORDER BY created_at DESC
                                """, (candidate_id,))

                    for row in cur.fetchall():
                        assessment_details = []
                        if row[2] is not None:  # speed_test
                            assessment_details.append(f"Speed Test: {row[2]}")
                        if row[3] is not None:  # accuracy_test
                            assessment_details.append(f"Accuracy Test: {row[3]}")
                        if row[4]:  # work_commitment
                            assessment_details.append(f"Work Commitment: {row[4]}")
                        if row[5]:  # english_understanding
                            assessment_details.append(f"English Understanding: {row[5]}")
                        if row[6]:  # comments
                            assessment_details.append(f"Comments: {row[6]}")

                        history.append({
                            'id': f"assessment_{row[0]}",
                            'actor': 'Receptionist',
                            'created_at': row[1],
                            'details': '; '.join(assessment_details) if assessment_details else 'Assessment completed',
                            'source': 'assessment'
                        })
                except Exception as e:
                    st.warning(f"Could not load assessments: {e}")

            conn.close()

    except Exception as e:
        st.error(f"Error connecting to database for history: {e}")

    # Sort by created_at desc
    history.sort(key=lambda x: x.get('created_at') or datetime.min, reverse=True)
    return history


def _render_interview_history_fixed(history_records: List[Dict[str, Any]]):
    """Render interview history with better categorization."""
    if not history_records:
        st.info("📝 No interview history found")
        return

    # Separate different types of records
    interviews = []
    assessments = []

    for record in history_records:
        source = record.get('source', '')
        if source == 'interview':
            interviews.append(record)
        elif source == 'assessment':
            assessments.append(record)

    # Display interviews
    if interviews:
        st.markdown("#### 🎤 Interviews")
        for interview in interviews:
            _render_single_record(interview)

    # Display assessments
    if assessments:
        st.markdown("#### 📊 Assessments")
        for assessment in assessments:
            _render_single_record(assessment)

    if not interviews and not assessments:
        st.info("📝 No interview or assessment records found")


def _render_single_record(record: Dict[str, Any]):
    """Render a single history record."""
    actor = record.get('actor', 'Unknown')
    when = _format_datetime(record.get('created_at'))
    details = record.get('details', '')

    with st.container():
        st.markdown(f"**👤 {actor}** • {when}")
        if details:
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
# CV Section with Access Control
# =============================================================================

def _render_cv_section_fixed(candidate_id: str, user_id: int, has_cv_file: bool, has_resume_link: bool):
    """Render CV section with proper access control."""
    st.markdown("### 📄 CV & Documents")

    if not (has_cv_file or has_resume_link):
        st.info("📂 No CV uploaded")
        return

    perms = _check_user_permissions(user_id)
    can_view = perms.get("can_view_cvs", False)

    if not can_view:
        st.warning("🔒 Access Denied: You need 'View CVs' permission to access candidate documents")
        return

    cv_bytes, cv_name, status = _get_cv_with_proper_access(candidate_id, user_id)

    if status == "ok" and cv_bytes:
        st.download_button(
            "📥 Download CV",
            data=cv_bytes,
            file_name=cv_name or f"{candidate_id}_cv.pdf",
            mime=_detect_mimetype(cv_name or ""),
            key=f"cv_dl_{candidate_id}"
        )

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

    elif status == "link_only" and cv_name:
        st.markdown(f"🔗 **Resume Link:** [Open CV]({cv_name})")

        if "drive.google.com" in cv_name:
            try:
                if "file/d/" in cv_name:
                    file_id = cv_name.split("file/d/")[1].split("/")[0]
                    embed_url = f"https://drive.google.com/file/d/{file_id}/preview"
                elif "id=" in cv_name:
                    file_id = cv_name.split("id=")[1].split("&")[0]
                    embed_url = f"https://drive.google.com/file/d/{file_id}/preview"
                else:
                    embed_url = cv_name

                st.markdown(f"""
                    <iframe 
                        src="{embed_url}" 
                        width="100%" 
                        height="500px" 
                        style="border: 1px solid #ddd; border-radius: 5px;">
                    </iframe>
                """, unsafe_allow_html=True)
            except Exception:
                st.info("📄 CV link preview not available")

    elif status == "no_permission":
        st.warning("🔒 Access Denied: CV viewing permission required")
    elif status == "not_found":
        st.info("📂 CV file not found")
    else:
        st.error("❌ Error accessing CV")


# =============================================================================
# FIXED User Management - Removed Candidate Records Management
# =============================================================================

def show_user_management_panel():
    """Clean user management panel - only user permissions, no candidate records."""
    require_login()

    user = get_current_user(refresh=True)
    perms = _check_user_permissions(user.get("id"))

    if not perms.get("can_manage_users", False):
        st.error("Access denied. Admin privileges required.")
        st.stop()

    st.title("👥 User Management")
    st.caption("Manage system user permissions")

    try:
        users = get_all_users_with_permissions()
    except Exception as e:
        st.error(f"Failed to load users: {e}")
        return

    if not users:
        st.info("No system users found.")
        return

    st.info(f"Found {len(users)} system users")

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

            # Permission controls
            col1, col2 = st.columns(2)

            with col1:
                can_view_cvs = st.checkbox(
                    "Can View CVs",
                    value=bool(user_data.get('can_view_cvs', False)),
                    key=f"cv_{user_id}",
                    help="Allow this user to view candidate CVs"
                )

            with col2:
                can_delete = st.checkbox(
                    "Can Delete Records",
                    value=bool(user_data.get('can_delete_records', False)),
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

            # Show current permissions for reference
            st.markdown("**Current Permissions:**")
            st.markdown(f"- View CVs: {'✅' if user_data.get('can_view_cvs') else '❌'}")
            st.markdown(f"- Delete Records: {'✅' if user_data.get('can_delete_records') else '❌'}")


# =============================================================================
# FIXED Delete Function with Proper Error Handling
# =============================================================================

def _delete_candidate_with_feedback(candidate_id: str, user_id: int) -> bool:
    """Delete candidate with proper error handling."""
    try:
        perms = _check_user_permissions(user_id)
        if not perms.get("can_delete_records", False):
            st.error("🔒 Access Denied: You need 'Delete Records' permission")
            return False

        # Call the delete function from db_postgres
        success, reason = delete_candidate(candidate_id, user_id)

        if success:
            st.success(f"✅ Candidate {candidate_id} deleted successfully")
            return True
        else:
            if reason == "no_permission":
                st.error("🔒 Access Denied: Insufficient permissions")
            elif reason == "not_found":
                st.error("❌ Candidate not found")
            elif reason == "db_error":
                st.error("❌ Database error during deletion")
            else:
                st.error(f"❌ Delete failed: {reason}")
            return False

    except Exception as e:
        st.error(f"❌ Delete error: {e}")
        return False


# =============================================================================
# Main CEO Dashboard - FIXED Version
# =============================================================================

def show_ceo_panel():
    """FIXED CEO dashboard with working delete and complete data display."""
    require_login()

    user = get_current_user(refresh=True)
    if not user:
        st.error("Please log in again.")
        st.stop()

    user_id = user.get("id")
    perms = _check_user_permissions(user_id)

    # Allow access for CEO and admin roles
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

    # Show user permissions clearly
    st.sidebar.markdown("### 🔑 Your Permissions")
    st.sidebar.markdown(f"- **View CVs:** {'✅ Enabled' if perms.get('can_view_cvs') else '❌ Disabled'}")
    st.sidebar.markdown(f"- **Delete Records:** {'✅ Enabled' if perms.get('can_delete_records') else '❌ Disabled'}")
    st.sidebar.markdown(f"- **Manage Users:** {'✅ Enabled' if perms.get('can_manage_users') else '❌ Disabled'}")

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

    # Update selection based on select_all checkbox
    if select_all:
        for candidate in page_candidates:
            selected.add(candidate.get('candidate_id', ''))
    elif 'select_all' in st.session_state and not select_all:
        selected.clear()

    # Batch actions - only show if user has delete permission
    if perms.get("can_delete_records") and selected:
        st.warning(f"⚠️ {len(selected)} candidates selected for deletion")
        if st.button(f"🗑️ Delete Selected ({len(selected)})", type="primary"):
            success_count = 0
            failed_count = 0

            with st.spinner("Deleting candidates..."):
                for candidate_id in list(selected):
                    if _delete_candidate_with_feedback(candidate_id, user_id):
                        success_count += 1
                        selected.discard(candidate_id)
                    else:
                        failed_count += 1

            if success_count > 0:
                st.success(f"✅ Deleted {success_count} candidates")
            if failed_count > 0:
                st.error(f"❌ Failed to delete {failed_count} candidates")

            _clear_candidate_cache()
            st.rerun()
    elif not perms.get("can_delete_records") and selected:
        st.info(f"📋 {len(selected)} candidates selected (Delete permission required for bulk operations)")

    # Display selected count if any
    if selected:
        st.info(f"📋 {len(selected)} candidates selected across all pages")

    # Render candidates
    for candidate in page_candidates:
        candidate_id = candidate.get('candidate_id', '')
        candidate_name = candidate.get('name', 'Unnamed')
        is_selected = candidate_id in selected

        with st.container():
            sel_col, content_col = st.columns([0.05, 0.95])

            with sel_col:
                if perms.get("can_delete_records"):
                    if st.checkbox("", value=is_selected, key=f"sel_{candidate_id}"):
                        selected.add(candidate_id)
                    else:
                        selected.discard(candidate_id)
                else:
                    st.write("")

            with content_col:
                with st.expander(f"👤 {candidate_name} ({candidate_id})", expanded=False):
                    main_col, action_col = st.columns([3, 1])

                    with main_col:
                        # Complete application details - FIXED to show ALL data
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

                        if perms.get("can_delete_records"):
                            if is_selected:
                                st.success("✅ Selected for batch action")

                        # Toggle edit permission
                        current_can_edit = candidate.get('can_edit', False)
                        toggle_label = "🔓 Grant Edit" if not current_can_edit else "🔒 Revoke Edit"

                        if st.button(toggle_label, key=f"toggle_{candidate_id}"):
                            try:
                                success = set_candidate_permission(candidate_id, not current_can_edit)
                                if success:
                                    st.success("✅ Updated edit permission")
                                    _clear_candidate_cache()
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to update permission")
                            except Exception as e:
                                st.error(f"Error: {e}")

                        # Current permission status
                        if current_can_edit:
                            st.info("✏️ Can edit application")
                        else:
                            st.info("🔒 Cannot edit application")

                        # Delete single candidate - only show if user has permission
                        if perms.get("can_delete_records"):
                            st.markdown("---")
                            if st.button("🗑️ Delete This Candidate", key=f"del_{candidate_id}", type="primary"):
                                # Double confirmation for safety
                                if st.button("⚠️ Confirm Delete", key=f"confirm_del_{candidate_id}"):
                                    if _delete_candidate_with_feedback(candidate_id, user_id):
                                        selected.discard(candidate_id)
                                        _clear_candidate_cache()
                                        st.rerun()

                        # Additional metadata
                        st.markdown("---")
                        st.caption("**Metadata:**")
                        st.caption(f"Created: {_format_datetime(candidate.get('created_at'))}")
                        st.caption(f"Updated: {_format_datetime(candidate.get('updated_at'))}")

                        # Show CV status
                        cv_status = []
                        if candidate.get('has_cv_file'):
                            cv_status.append("📄 File")
                        if candidate.get('has_resume_link'):
                            cv_status.append("🔗 Link")

                        if cv_status:
                            st.caption(f"CV: {' + '.join(cv_status)}")
                        else:
                            st.caption("CV: ❌ None")

    # Summary at bottom
    if filtered_candidates:
        st.markdown("---")
        st.info(
            f"📊 Showing {len(page_candidates)} of {total_candidates} candidates (Page {page if total_pages > 1 else 1} of {total_pages})")

        if selected:
            if perms.get("can_delete_records"):
                st.warning(f"⚠️ {len(selected)} candidates selected for batch operations")
            else:
                st.info(f"📋 {len(selected)} candidates selected (Delete permission needed for operations)")


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
    st.sidebar.caption("⚡ Features: Complete Data Display, Working Delete, User Management, Batch Operations")

    # Run selected page
    try:
        pages[selected_page]()
    except Exception as e:
        st.error(f"Page error: {e}")
        st.exception(e)


if __name__ == "__main__":
    main()