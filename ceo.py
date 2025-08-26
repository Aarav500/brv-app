
# FIXED CEO Control Panel - Complete Version with All Functionality
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
import asyncio
import concurrent.futures
import threading
from functools import partial

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
# Performance Optimizations with Async/Threading and Better Caching
# =============================================================================

@st.cache_data(ttl=600, show_spinner=False)  # 10 minute cache
def _get_candidates_fast():
    """Ultra-fast candidate loading with connection pooling."""
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            # Optimized query - get only essential data first
            cur.execute("""
                        SELECT candidate_id,
                               name,
                               email,
                               phone,
                               created_at,
                               updated_at,
                               can_edit,
                               cv_file IS NOT NULL as has_cv_file,
                               resume_link IS NOT NULL AND resume_link != '' as has_resume_link,
                    form_data
                        FROM candidates
                        ORDER BY created_at DESC
                            LIMIT 1000
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
                    'form_data': row[9] or {}
                }

                # Merge form_data efficiently
                if isinstance(candidate['form_data'], dict):
                    for key, value in candidate['form_data'].items():
                        if value and str(value).strip():
                            candidate[f'form_{key}'] = value
                            if key not in candidate:
                                candidate[key] = value

                candidates.append(candidate)

        conn.close()
        return candidates
    except Exception as e:
        st.error(f"Failed to load candidates: {e}")
        return []


def _get_detailed_candidate_data(candidate_id: str) -> Dict[str, Any]:
    """Load detailed data for a specific candidate only when needed."""
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            # Get all columns for this specific candidate
            cur.execute("""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = 'candidates'
                        ORDER BY ordinal_position
                        """)
            existing_columns = [row[0] for row in cur.fetchall()]

            # Build comprehensive SELECT
            select_parts = [col for col in existing_columns if col not in ['cv_file']]

            query = f"""
                SELECT {', '.join(select_parts)}
                FROM candidates
                WHERE candidate_id = %s
            """

            cur.execute(query, (candidate_id,))
            result = cur.fetchone()

            if result:
                candidate = {}
                for i, col_name in enumerate(select_parts):
                    candidate[col_name] = result[i]

                # Process form_data
                form_data = candidate.get('form_data', {})
                if isinstance(form_data, dict):
                    for key, value in form_data.items():
                        if value and str(value).strip():
                            candidate[f'form_{key}'] = value
                            if key not in candidate:
                                candidate[key] = value

                return candidate

        conn.close()
    except Exception as e:
        st.error(f"Failed to load detailed data: {e}")

    return {}


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
# Smart State Management - No Reruns on Selection
# =============================================================================

def _initialize_selection_state():
    """Initialize selection state without causing reruns."""
    if 'selected_candidates' not in st.session_state:
        st.session_state.selected_candidates = set()
    if 'selection_changed' not in st.session_state:
        st.session_state.selection_changed = False
    if 'bulk_delete_confirmed' not in st.session_state:
        st.session_state.bulk_delete_confirmed = False


def _update_selection_state(candidate_id: str, is_selected: bool):
    """Update selection state without rerun."""
    if is_selected:
        st.session_state.selected_candidates.add(candidate_id)
    else:
        st.session_state.selected_candidates.discard(candidate_id)
    st.session_state.selection_changed = True


# JavaScript for instant selection without rerun
def _render_instant_checkbox(candidate_id: str, is_selected: bool) -> bool:
    """Render checkbox with instant feedback via JavaScript."""

    checkbox_html = f"""
    <div style="padding: 0;">
        <input 
            type="checkbox" 
            id="cb_{candidate_id}" 
            {'checked' if is_selected else ''}
            onchange="updateSelection('{candidate_id}', this.checked)"
            style="
                width: 20px; 
                height: 20px; 
                cursor: pointer;
                accent-color: #ff4444;
            "
        />
    </div>

    <script>
    function updateSelection(candidateId, checked) {{
        // Store selection in browser storage for instant feedback
        let selections = JSON.parse(localStorage.getItem('candidate_selections') || '{{}}');
        if (checked) {{
            selections[candidateId] = true;
        }} else {{
            delete selections[candidateId];
        }}
        localStorage.setItem('candidate_selections', JSON.stringify(selections));

        // Update UI instantly
        updateSelectionDisplay();

        // Send to Streamlit (debounced)
        setTimeout(() => {{
            const event = new CustomEvent('candidateSelectionChanged', {{
                detail: {{ candidateId, checked }}
            }});
            window.dispatchEvent(event);
        }}, 100);
    }}

    function updateSelectionDisplay() {{
        const selections = JSON.parse(localStorage.getItem('candidate_selections') || '{{}}');
        const count = Object.keys(selections).length;

        // Update selection count display
        const countElements = document.querySelectorAll('.selection-count');
        countElements.forEach(el => {{
            el.textContent = count;
        }});

        // Show/hide delete button
        const deleteBar = document.querySelector('.bulk-delete-bar');
        if (deleteBar) {{
            if (count > 0) {{
                deleteBar.style.display = 'block';
                deleteBar.querySelector('.delete-count').textContent = count;
            }} else {{
                deleteBar.style.display = 'none';
            }}
        }}
    }}

    // Initialize on page load
    document.addEventListener('DOMContentLoaded', updateSelectionDisplay);
    </script>
    """

    components.html(checkbox_html, height=30)


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
# FIXED Personal Details Display - Better Organization
# =============================================================================

def _render_personal_details_organized(candidate: Dict[str, Any]):
    """Render personal details in a well-organized, comprehensive format."""

    st.markdown("### 👤 Personal Details")

    # Comprehensive field mapping for better display
    field_labels = {
        "name": "👤 Full Name",
        "email": "📧 Email Address",
        "phone": "📱 Phone Number",
        "dob": "🎂 Date of Birth",
        "current_address": "🏠 Current Address",
        "permanent_address": "🏡 Permanent Address",
        "address": "🏠 Address",
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
        st.info("📋 No detailed personal information available")
        return

    # Display in organized sections with better formatting
    with st.container():
        # Basic Information Section
        st.markdown("#### 👤 Basic Information")
        basic_col1, basic_col2, basic_col3 = st.columns(3)

        basic_fields = ["name", "email", "phone", "dob"]
        basic_items = [(k, v) for k, v in all_data.items() if k in basic_fields]

        if basic_items:
            for i, (key, value) in enumerate(basic_items):
                label = field_labels.get(key, key.replace('_', ' ').title())
                display_value = _format_datetime(value) if key == "dob" else str(value)

                if i % 3 == 0:
                    with basic_col1:
                        st.markdown(f"**{label}:**")
                        st.write(display_value)
                elif i % 3 == 1:
                    with basic_col2:
                        st.markdown(f"**{label}:**")
                        st.write(display_value)
                else:
                    with basic_col3:
                        st.markdown(f"**{label}:**")
                        st.write(display_value)

        # Address Information Section
        st.markdown("#### 🏠 Address Information")
        address_fields = ["current_address", "permanent_address", "address"]
        address_items = [(k, v) for k, v in all_data.items() if k in address_fields]

        if address_items:
            addr_col1, addr_col2 = st.columns(2)
            for i, (key, value) in enumerate(address_items):
                label = field_labels.get(key, key.replace('_', ' ').title())
                if i % 2 == 0:
                    with addr_col1:
                        st.markdown(f"**{label}:**")
                        st.write(value)
                else:
                    with addr_col2:
                        st.markdown(f"**{label}:**")
                        st.write(value)
        else:
            st.info("No address information available")

        # Personal & Family Details Section
        st.markdown("#### 👥 Personal & Family Details")
        personal_fields = ["caste", "sub_caste", "marital_status"]
        personal_items = [(k, v) for k, v in all_data.items() if k in personal_fields]

        if personal_items:
            pers_col1, pers_col2, pers_col3 = st.columns(3)
            for i, (key, value) in enumerate(personal_items):
                label = field_labels.get(key, key.replace('_', ' ').title())
                if i % 3 == 0:
                    with pers_col1:
                        st.markdown(f"**{label}:**")
                        st.write(value)
                elif i % 3 == 1:
                    with pers_col2:
                        st.markdown(f"**{label}:**")
                        st.write(value)
                else:
                    with pers_col3:
                        st.markdown(f"**{label}:**")
                        st.write(value)
        else:
            st.info("No personal details available")

        # Professional Information Section
        st.markdown("#### 💼 Professional Information")
        prof_fields = ["highest_qualification", "work_experience", "referral"]
        prof_items = [(k, v) for k, v in all_data.items() if k in prof_fields]

        if prof_items:
            for key, value in prof_items:
                label = field_labels.get(key, key.replace('_', ' ').title())
                st.markdown(f"**{label}:**")
                st.write(value)
                st.markdown("")  # Add spacing
        else:
            st.info("No professional information available")

        # Work Preferences Section
        st.markdown("#### ⚙️ Work Preferences")
        pref_fields = ["ready_festivals", "ready_late_nights"]
        pref_items = [(k, v) for k, v in all_data.items() if k in pref_fields]

        if pref_items:
            pref_col1, pref_col2 = st.columns(2)
            for i, (key, value) in enumerate(pref_items):
                label = field_labels.get(key, key.replace('_', ' ').title())
                display_value = "✅ Yes" if str(value).lower() in ["yes", "true", "1"] else "❌ No"

                if i % 2 == 0:
                    with pref_col1:
                        st.markdown(f"**{label}:** {display_value}")
                else:
                    with pref_col2:
                        st.markdown(f"**{label}:** {display_value}")
        else:
            st.info("No work preference information available")

        # System Information Section
        st.markdown("#### 🔧 System Information")
        system_fields = ["created_at", "updated_at", "cv_filename", "resume_link", "created_by"]
        system_items = [(k, v) for k, v in all_data.items() if k in system_fields]

        if system_items:
            sys_col1, sys_col2 = st.columns(2)
            for i, (key, value) in enumerate(system_items):
                label = field_labels.get(key, key.replace('_', ' ').title())
                if key in ["created_at", "updated_at"]:
                    display_value = _format_datetime(value)
                elif key == "resume_link":
                    display_value = f"[Open Link]({value})" if value else str(value)
                else:
                    display_value = str(value)

                if i % 2 == 0:
                    with sys_col1:
                        st.markdown(f"**{label}:** {display_value}")
                else:
                    with sys_col2:
                        st.markdown(f"**{label}:** {display_value}")

        # Additional Information Section (for any remaining fields)
        remaining_items = [(k, v) for k, v in all_data.items()
                           if k not in (basic_fields + address_fields + personal_fields +
                                        prof_fields + pref_fields + system_fields)]

        if remaining_items:
            st.markdown("#### 📋 Additional Information")
            add_col1, add_col2 = st.columns(2)
            for i, (key, value) in enumerate(remaining_items):
                label = key.replace('_', ' ').title()
                if i % 2 == 0:
                    with add_col1:
                        st.markdown(f"**{label}:** {value}")
                else:
                    with add_col2:
                        st.markdown(f"**{label}:** {value}")


# =============================================================================
# FIXED Interview History Display with Proper Formatting
# =============================================================================

def _get_interview_history_comprehensive(candidate_id: str) -> List[Dict[str, Any]]:
    """Get comprehensive interview history with proper formatting."""
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
                        interview_id, interviewer, created_at, scheduled_at, result, notes = row

                        # Build detailed interview information
                        details = []
                        if result:
                            details.append(f"**Result:** {result}")
                        if interviewer:
                            details.append(f"**Interviewer:** {interviewer}")
                        if scheduled_at:
                            details.append(f"**Scheduled:** {_format_datetime(scheduled_at)}")
                        if notes and notes.strip():
                            details.append(f"**Notes:** {notes}")

                        event_time = scheduled_at if scheduled_at else created_at

                        history.append({
                            'id': f"interview_{interview_id}",
                            'type': 'interview',
                            'title': '🎤 Interview',
                            'actor': interviewer or 'Interviewer',
                            'created_at': event_time,
                            'details': details,
                            'raw_details': {
                                'result': result,
                                'interviewer': interviewer,
                                'scheduled_at': scheduled_at,
                                'notes': notes
                            }
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
                        assess_id, created_at, speed_test, accuracy_test, work_commitment, english_understanding, comments = row

                        # Build detailed assessment information
                        details = []
                        if speed_test is not None:
                            details.append(f"**Speed Test:** {speed_test}/100")
                        if accuracy_test is not None:
                            details.append(f"**Accuracy Test:** {accuracy_test}/100")
                        if work_commitment:
                            details.append(f"**Work Commitment:** {work_commitment}")
                        if english_understanding:
                            details.append(f"**English Understanding:** {english_understanding}")
                        if comments and comments.strip():
                            details.append(f"**Comments:** {comments}")

                        history.append({
                            'id': f"assessment_{assess_id}",
                            'type': 'assessment',
                            'title': '📊 Receptionist Assessment',
                            'actor': 'Receptionist',
                            'created_at': created_at,
                            'details': details,
                            'raw_details': {
                                'speed_test': speed_test,
                                'accuracy_test': accuracy_test,
                                'work_commitment': work_commitment,
                                'english_understanding': english_understanding,
                                'comments': comments
                            }
                        })
                except Exception as e:
                    st.warning(f"Could not load assessments: {e}")

            conn.close()

    except Exception as e:
        st.error(f"Error connecting to database for history: {e}")

    # Sort by created_at desc
    history.sort(key=lambda x: x.get('created_at') or datetime.min, reverse=True)
    return history


def _render_interview_history_comprehensive(history_records: List[Dict[str, Any]]):
    """Render interview history with comprehensive formatting and details."""

    st.markdown("### 🎤 Interview & Assessment History")

    if not history_records:
        st.info("📝 No interview or assessment history found")
        return

    # Separate different types of records
    interviews = []
    assessments = []

    for record in history_records:
        record_type = record.get('type', '')
        if record_type == 'interview':
            interviews.append(record)
        elif record_type == 'assessment':
            assessments.append(record)

    # Display interviews with detailed formatting
    if interviews:
        st.markdown("#### 🎤 Interview History")
        for interview in interviews:
            _render_interview_record_detailed(interview)

    # Display assessments with detailed formatting
    if assessments:
        st.markdown("#### 📊 Assessment History")
        for assessment in assessments:
            _render_assessment_record_detailed(assessment)

    if not interviews and not assessments:
        st.info("📝 No interview or assessment records found")


def _render_interview_record_detailed(record: Dict[str, Any]):
    """Render a detailed interview record with all information."""

    title = record.get('title', '🎤 Interview')
    actor = record.get('actor', 'Unknown')
    when = _format_datetime(record.get('created_at'))
    details = record.get('details', [])
    raw_details = record.get('raw_details', {})

    # Use expander for each interview record
    with st.expander(f"{title} • {actor} • {when}", expanded=False):
        if details:
            for detail in details:
                st.markdown(detail)
        else:
            st.markdown("📝 No additional details available")

        # Add visual separator
        st.markdown("---")
        st.caption(f"🕐 Recorded on {when}")


def _render_assessment_record_detailed(record: Dict[str, Any]):
    """Render a detailed assessment record with all information."""

    title = record.get('title', '📊 Assessment')
    actor = record.get('actor', 'Unknown')
    when = _format_datetime(record.get('created_at'))
    details = record.get('details', [])
    raw_details = record.get('raw_details', {})

    # Use expander for each assessment record
    with st.expander(f"{title} • {actor} • {when}", expanded=False):
        if details:
            # Display assessment scores prominently
            speed = raw_details.get('speed_test')
            accuracy = raw_details.get('accuracy_test')

            if speed is not None or accuracy is not None:
                col1, col2 = st.columns(2)
                if speed is not None:
                    with col1:
                        st.metric("Speed Test", f"{speed}/100", delta=None)
                if accuracy is not None:
                    with col2:
                        st.metric("Accuracy Test", f"{accuracy}/100", delta=None)
                st.markdown("---")

            # Display other details
            for detail in details:
                if not any(test in detail for test in ["Speed Test:", "Accuracy Test:"]):
                    st.markdown(detail)
        else:
            st.markdown("📝 No additional details available")

        # Add visual separator
        st.markdown("---")
        st.caption(f"🕐 Recorded on {when}")


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
# User Management Panel
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
# FIXED Delete Functions with Proper Error Handling and Fast Refresh
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


def _render_candidate_delete_section(candidate_id: str, user_id: int, perms: Dict[str, Any]):
    """Render delete section with proper confirmation flow."""

    if not perms.get("can_delete_records"):
        return

    st.markdown("---")
    st.markdown("### 🗑️ Danger Zone")

    # Check if this candidate is in confirmation state
    confirm_key = f"confirm_delete_{candidate_id}"

    if st.session_state.get(confirm_key, False):
        # Show confirmation UI
        st.warning(f"⚠️ Are you sure you want to delete candidate {candidate_id}?")
        st.write("This action cannot be undone.")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("✅ Yes, Delete", key=f"confirm_yes_{candidate_id}", type="primary"):
                with st.spinner("Deleting candidate..."):
                    if _delete_candidate_with_feedback(candidate_id, user_id):
                        # Clear confirmation state and refresh
                        st.session_state[confirm_key] = False
                        _clear_candidate_cache()
                        st.rerun()

        with col2:
            if st.button("❌ Cancel", key=f"confirm_no_{candidate_id}"):
                st.session_state[confirm_key] = False
                st.rerun()

    else:
        # Show initial delete button
        if st.button(f"🗑️ Delete Candidate", key=f"delete_init_{candidate_id}", type="secondary"):
            st.session_state[confirm_key] = True
            st.rerun()


def _bulk_delete_candidates(candidate_ids: List[str], user_id: int) -> Tuple[int, int]:
    """Bulk delete candidates with proper error handling."""
    try:
        perms = _check_user_permissions(user_id)
        if not perms.get("can_delete_records", False):
            st.error("🔒 Access Denied: You need 'Delete Records' permission")
            return 0, len(candidate_ids)

        # Call the delete function from db_postgres with list
        success, reason = delete_candidate(candidate_ids, user_id)

        if success:
            return len(candidate_ids), 0
        else:
            st.error(f"❌ Bulk delete failed: {reason}")
            return 0, len(candidate_ids)

    except Exception as e:
        st.error(f"❌ Bulk delete error: {e}")
        return 0, len(candidate_ids)


def _render_always_visible_bulk_delete_bar(selected: set, user_id: int, perms: Dict[str, Any]):
    """Always show a bulk action bar with real-time selection count."""
    if not perms.get("can_delete_records"):
        return

    selected_count = len(selected)

    # Always visible bulk action bar with JavaScript integration
    bulk_bar_html = f"""
    <div class="bulk-delete-bar" style="
        background: linear-gradient(90deg, {'#ff4444, #ff6666' if selected_count > 0 else '#f0f0f0, #e0e0e0'});
        color: {'white' if selected_count > 0 else '#666'};
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        display: flex;
        justify-content: space-between;
        align-items: center;
        transition: all 0.3s ease;
    ">
        <div>
            <h3 style="margin: 0; display: inline;">
                🗑️ <span class="delete-count selection-count">{selected_count}</span> 
                Candidates Selected for Deletion
            </h3>
        </div>
        <div style="display: flex; gap: 1rem; align-items: center;">
            <div class="selection-count" style="
                background-color: {'white' if selected_count > 0 else '#ccc'};
                color: {'#ff4444' if selected_count > 0 else '#666'};
                padding: 0.75rem 1.5rem;
                border-radius: 50px;
                font-weight: bold;
                font-size: 1.2rem;
            ">{selected_count}</div>
        </div>
    </div>

    <script>
    // Sync with localStorage on page load
    document.addEventListener('DOMContentLoaded', function() {{
        const selections = JSON.parse(localStorage.getItem('candidate_selections') || '{{}}');
        const count = Object.keys(selections).length;

        // Update Streamlit session state
        if (count !== {selected_count}) {{
            // Trigger update
            window.dispatchEvent(new CustomEvent('syncSelections', {{
                detail: {{ selections: selections }}
            }}));
        }}
    }});
    </script>
    """

    components.html(bulk_bar_html, height=80)

    # Show actual buttons only when candidates are selected
    if selected_count > 0:
        col1, col2, col3 = st.columns([4, 2, 2])

        with col2:
            if st.button(
                    f"🗑️ DELETE {selected_count} NOW",
                    key="instant_bulk_delete",
                    type="primary",
                    help=f"Delete {selected_count} selected candidates"
            ):
                st.session_state.bulk_delete_confirmed = True
                st.rerun()

        with col3:
            if st.button("❌ Clear All", key="clear_selection_main"):
                selected.clear()
                # Clear localStorage
                components.html("""
                <script>
                localStorage.removeItem('candidate_selections');
                document.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
                </script>
                """, height=1)
                st.rerun()


def _render_bulk_delete_confirmation(selected: set, user_id: int, perms: Dict[str, Any]):
    """Render bulk delete confirmation dialog."""
    if not st.session_state.get('bulk_delete_confirmed', False):
        return

    # Show prominent confirmation dialog
    st.markdown("""
    <div style="
        background-color: #ffcccc; 
        padding: 2rem; 
        border-radius: 0.5rem; 
        border: 2px solid #ff0000;
        margin: 2rem 0;
        text-align: center;
    ">
    </div>
    """, unsafe_allow_html=True)

    st.error(f"⚠️ **FINAL WARNING: Permanently Delete {len(selected)} Candidates?**")
    st.markdown("---")
    st.markdown("### 🚨 This action CANNOT be undone!")
    st.markdown("**The following candidates will be permanently removed:**")

    # Show list of candidates to be deleted
    candidates = _get_candidates_fast()
    candidates_to_delete = [c for c in candidates if c.get('candidate_id') in selected]

    if candidates_to_delete:
        delete_col1, delete_col2 = st.columns(2)
        for i, candidate in enumerate(candidates_to_delete[:10]):  # Show first 10
            candidate_id = candidate.get('candidate_id', 'Unknown ID')
            candidate_name = candidate.get('name', 'Unknown Name')

            if i % 2 == 0:
                with delete_col1:
                    st.write(f"• **{candidate_name}** ({candidate_id})")
            else:
                with delete_col2:
                    st.write(f"• **{candidate_name}** ({candidate_id})")

        if len(candidates_to_delete) > 10:
            st.write(f"... and {len(candidates_to_delete) - 10} more candidates")

    st.markdown("---")

    # Confirmation buttons
    confirm_col1, confirm_col2, confirm_col3 = st.columns([1, 2, 1])

    with confirm_col1:
        if st.button("❌ **CANCEL**", key="cancel_final_bulk_delete", type="secondary"):
            st.session_state.bulk_delete_confirmed = False
            st.rerun()

    with confirm_col2:
        # Require typing confirmation
        confirmation_text = st.text_input(
            f"Type 'DELETE {len(selected)} CANDIDATES' to confirm:",
            key="bulk_delete_confirmation_text"
        )

        expected_text = f"DELETE {len(selected)} CANDIDATES"
        confirmation_matches = confirmation_text.strip() == expected_text

    with confirm_col3:
        if confirmation_matches:
            if st.button(
                    f"🗑️ **DELETE {len(selected)}**",
                    key="execute_bulk_delete",
                    type="primary"
            ):
                with st.spinner(f"Deleting {len(selected)} candidates..."):
                    success_count, failed_count = _bulk_delete_candidates(list(selected), user_id)

                if success_count > 0:
                    st.success(f"✅ Successfully deleted {success_count} candidates!")
                    selected.clear()
                    _clear_candidate_cache()
                    st.session_state.bulk_delete_confirmed = False
                    st.rerun()

                if failed_count > 0:
                    st.error(f"❌ Failed to delete {failed_count} candidates")
        else:
            st.button(
                f"Type confirmation text",
                key="disabled_bulk_delete",
                disabled=True
            )

    if not confirmation_matches and confirmation_text:
        st.error(f"Please type exactly: '{expected_text}'")


def _render_bulk_delete_section(selected: set, user_id: int, perms: Dict[str, Any]):
    """Render bulk delete section - always show the bar, handle confirmation separately."""

    # Always show the bulk action bar
    _render_always_visible_bulk_delete_bar(selected, user_id, perms)

    # Show confirmation dialog if in confirmation state
    if st.session_state.get('bulk_delete_confirmed', False) and selected:
        _render_bulk_delete_confirmation(selected, user_id, perms)


# =============================================================================
# Main CEO Dashboard - ENHANCED Version with Prominent Bulk Delete
# =============================================================================

def show_ceo_panel():
    """ENHANCED CEO dashboard with prominent bulk delete functionality."""
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

    # Selection management
    if 'selected_candidates' not in st.session_state:
        st.session_state.selected_candidates = set()

    selected = st.session_state.selected_candidates

    # Update selection based on select_all checkbox with instant feedback
    if select_all:
        # Select all filtered candidates immediately
        for candidate in filtered_candidates:
            selected.add(candidate.get('candidate_id', ''))
    else:
        # If select_all was unchecked, clear selection
        if 'previous_select_all' in st.session_state and st.session_state.previous_select_all:
            selected.clear()

    # Track previous select_all state
    st.session_state.previous_select_all = select_all

    # ALWAYS show bulk delete section (it handles empty selection internally)
    _render_bulk_delete_section(selected, user_id, perms)

    # Show selection info if no delete permissions but candidates are selected
    if not perms.get("can_delete_records") and selected:
        st.info(f"📋 {len(selected)} candidates selected (Delete permission required for bulk operations)")

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

    # Display selected count if any
    if selected:
        st.info(f"📋 {len(selected)} candidates selected across all pages")

    # Render candidates with improved layout
    for candidate in page_candidates:
        candidate_id = candidate.get('candidate_id', '')
        candidate_name = candidate.get('name', 'Unnamed')
        is_selected = candidate_id in selected

        with st.container():
            sel_col, content_col = st.columns([0.05, 0.95])

            with sel_col:
                if perms.get("can_delete_records"):
                    # Use session state to avoid rerun on every checkbox change
                    checkbox_key = f"sel_{candidate_id}"
                    if st.checkbox("", value=is_selected, key=checkbox_key):
                        if candidate_id not in selected:
                            selected.add(candidate_id)
                    else:
                        if candidate_id in selected:
                            selected.discard(candidate_id)
                else:
                    st.write("")

            with content_col:
                with st.expander(f"👤 {candidate_name} ({candidate_id})", expanded=False):
                    main_col, action_col = st.columns([3, 1])

                    with main_col:
                        # FIXED Personal details - comprehensive and well-organized
                        _render_personal_details_organized(candidate)

                        # CV Section - FIXED with proper access control
                        _render_cv_section_fixed(
                            candidate_id,
                            user_id,
                            candidate.get('has_cv_file', False),
                            candidate.get('has_resume_link', False)
                        )

                        # FIXED Interview History - comprehensive with proper formatting
                        history = _get_interview_history_comprehensive(candidate_id)
                        _render_interview_history_comprehensive(history)

                    with action_col:
                        st.markdown("### ⚙️ Actions")
                        st.caption(f"ID: {candidate_id}")

                        if perms.get("can_delete_records"):
                            if is_selected:
                                st.success("✅ Selected")
                                if st.button("❌ Unselect", key=f"unselect_{candidate_id}"):
                                    selected.discard(candidate_id)
                                    st.rerun()
                            else:
                                if st.button("☑️ Select for Bulk Delete", key=f"select_{candidate_id}"):
                                    selected.add(candidate_id)
                                    st.rerun()

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

                        # FIXED: Single candidate delete with proper state management
                        _render_candidate_delete_section(candidate_id, user_id, perms)

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

    # Initialize session state
    if 'selected_candidates' not in st.session_state:
        st.session_state.selected_candidates = set()
    if 'bulk_delete_confirmed' not in st.session_state:
        st.session_state.bulk_delete_confirmed = False

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
    st.sidebar.caption("⚡ Features:")
    st.sidebar.caption("- Complete Personal Details")
    st.sidebar.caption("- Comprehensive Interview History")
    st.sidebar.caption("- **PROMINENT Bulk Delete**")
    st.sidebar.caption("- Fast Refresh (10s cache)")
    st.sidebar.caption("- User Management")
    st.sidebar.caption("- Enhanced UI/UX")

    # Run selected page
    try:
        pages[selected_page]()
    except Exception as e:
        st.error(f"Page error: {e}")
        st.exception(e)


if __name__ == "__main__":
    main()