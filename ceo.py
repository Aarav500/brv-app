# OPTIMIZED CEO Control Panel - Zero Refresh Operations + Bulk User Management
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
# ZERO REFRESH OPERATIONS - JavaScript-based UI Management
# =============================================================================

def _render_zero_refresh_selection_manager():
    """Complete JavaScript-based selection management with zero refreshes."""

    selection_js = """
    <div id="zero-refresh-manager" style="display: none;"></div>

    <script>
    // Global selection state
    window.candidateSelections = window.candidateSelections || new Set();
    window.userSelections = window.userSelections || new Set();
    window.bulkDeleteConfirmed = window.bulkDeleteConfirmed || false;
    window.bulkUserDeleteConfirmed = window.bulkUserDeleteConfirmed || false;

    // Update selection display across all UI elements
    function updateSelectionDisplay() {
        const candidateCount = window.candidateSelections.size;
        const userCount = window.userSelections.size;

        // Update all selection count displays
        document.querySelectorAll('.candidate-selection-count').forEach(el => {
            el.textContent = candidateCount;
        });

        document.querySelectorAll('.user-selection-count').forEach(el => {
            el.textContent = userCount;
        });

        // Show/hide bulk action bars
        const candidateBulkBar = document.querySelector('.candidate-bulk-bar');
        const userBulkBar = document.querySelector('.user-bulk-bar');

        if (candidateBulkBar) {
            if (candidateCount > 0) {
                candidateBulkBar.style.display = 'flex';
                candidateBulkBar.style.background = 'linear-gradient(90deg, #ff4444, #ff6666)';
                candidateBulkBar.style.color = 'white';
            } else {
                candidateBulkBar.style.display = 'none';
            }
        }

        if (userBulkBar) {
            if (userCount > 0) {
                userBulkBar.style.display = 'flex';
                userBulkBar.style.background = 'linear-gradient(90deg, #4444ff, #6666ff)';
                userBulkBar.style.color = 'white';
            } else {
                userBulkBar.style.display = 'none';
            }
        }

        // Update confirmation dialogs
        updateConfirmationDialogs();
    }

    // Candidate selection functions
    function toggleCandidateSelection(candidateId, forceValue = null) {
        if (forceValue !== null) {
            if (forceValue) {
                window.candidateSelections.add(candidateId);
            } else {
                window.candidateSelections.delete(candidateId);
            }
        } else {
            if (window.candidateSelections.has(candidateId)) {
                window.candidateSelections.delete(candidateId);
            } else {
                window.candidateSelections.add(candidateId);
            }
        }

        // Update checkbox state
        const checkbox = document.getElementById('cb_candidate_' + candidateId);
        if (checkbox) {
            checkbox.checked = window.candidateSelections.has(candidateId);
        }

        updateSelectionDisplay();
        saveSelectionState();
    }

    // User selection functions
    function toggleUserSelection(userId, forceValue = null) {
        if (forceValue !== null) {
            if (forceValue) {
                window.userSelections.add(userId);
            } else {
                window.userSelections.delete(userId);
            }
        } else {
            if (window.userSelections.has(userId)) {
                window.userSelections.delete(userId);
            } else {
                window.userSelections.add(userId);
            }
        }

        // Update checkbox state
        const checkbox = document.getElementById('cb_user_' + userId);
        if (checkbox) {
            checkbox.checked = window.userSelections.has(userId);
        }

        updateSelectionDisplay();
        saveSelectionState();
    }

    // Select all functions
    function selectAllCandidates(candidates) {
        candidates.forEach(id => window.candidateSelections.add(id));
        document.querySelectorAll('[id^="cb_candidate_"]').forEach(cb => {
            cb.checked = true;
        });
        updateSelectionDisplay();
        saveSelectionState();
    }

    function clearAllCandidates() {
        window.candidateSelections.clear();
        document.querySelectorAll('[id^="cb_candidate_"]').forEach(cb => {
            cb.checked = false;
        });
        updateSelectionDisplay();
        saveSelectionState();
    }

    function selectAllUsers(users) {
        users.forEach(id => window.userSelections.add(id));
        document.querySelectorAll('[id^="cb_user_"]').forEach(cb => {
            cb.checked = true;
        });
        updateSelectionDisplay();
        saveSelectionState();
    }

    function clearAllUsers() {
        window.userSelections.clear();
        document.querySelectorAll('[id^="cb_user_"]').forEach(cb => {
            cb.checked = false;
        });
        updateSelectionDisplay();
        saveSelectionState();
    }

    // Confirmation dialog management
    function showCandidateDeleteConfirmation() {
        window.bulkDeleteConfirmed = true;
        updateConfirmationDialogs();
    }

    function hideCandidateDeleteConfirmation() {
        window.bulkDeleteConfirmed = false;
        updateConfirmationDialogs();
    }

    function showUserDeleteConfirmation() {
        window.bulkUserDeleteConfirmed = true;
        updateConfirmationDialogs();
    }

    function hideUserDeleteConfirmation() {
        window.bulkUserDeleteConfirmed = false;
        updateConfirmationDialogs();
    }

    function updateConfirmationDialogs() {
        const candidateConfirm = document.querySelector('.candidate-delete-confirmation');
        const userConfirm = document.querySelector('.user-delete-confirmation');

        if (candidateConfirm) {
            candidateConfirm.style.display = window.bulkDeleteConfirmed ? 'block' : 'none';
        }

        if (userConfirm) {
            userConfirm.style.display = window.bulkUserDeleteConfirmed ? 'block' : 'none';
        }
    }

    // Execute bulk operations
    function executeBulkCandidateDelete() {
        const selectedIds = Array.from(window.candidateSelections);
        if (selectedIds.length === 0) return;

        // Show loading state
        const deleteBtn = document.getElementById('bulk-candidate-delete-btn');
        if (deleteBtn) {
            deleteBtn.innerHTML = '⏳ Deleting...';
            deleteBtn.disabled = true;
        }

        // Send to Streamlit
        const event = new CustomEvent('bulkCandidateDelete', {
            detail: { candidateIds: selectedIds }
        });
        window.dispatchEvent(event);
    }

    function executeBulkUserDelete() {
        const selectedIds = Array.from(window.userSelections);
        if (selectedIds.length === 0) return;

        // Show loading state
        const deleteBtn = document.getElementById('bulk-user-delete-btn');
        if (deleteBtn) {
            deleteBtn.innerHTML = '⏳ Deleting...';
            deleteBtn.disabled = true;
        }

        // Send to Streamlit
        const event = new CustomEvent('bulkUserDelete', {
            detail: { userIds: selectedIds }
        });
        window.dispatchEvent(event);
    }

    // Bulk permission updates
    function executeBulkPermissionUpdate(permission, value) {
        const selectedIds = Array.from(window.userSelections);
        if (selectedIds.length === 0) return;

        // Show loading state
        const updateBtn = document.getElementById('bulk-permission-update-btn');
        if (updateBtn) {
            updateBtn.innerHTML = '⏳ Updating...';
            updateBtn.disabled = true;
        }

        // Send to Streamlit
        const event = new CustomEvent('bulkPermissionUpdate', {
            detail: { 
                userIds: selectedIds,
                permission: permission,
                value: value
            }
        });
        window.dispatchEvent(event);
    }

    // Save/load selection state
    function saveSelectionState() {
        localStorage.setItem('candidateSelections', JSON.stringify(Array.from(window.candidateSelections)));
        localStorage.setItem('userSelections', JSON.stringify(Array.from(window.userSelections)));
    }

    function loadSelectionState() {
        const candidateSelections = JSON.parse(localStorage.getItem('candidateSelections') || '[]');
        const userSelections = JSON.parse(localStorage.getItem('userSelections') || '[]');

        window.candidateSelections = new Set(candidateSelections);
        window.userSelections = new Set(userSelections);

        // Update UI
        candidateSelections.forEach(id => {
            const checkbox = document.getElementById('cb_candidate_' + id);
            if (checkbox) checkbox.checked = true;
        });

        userSelections.forEach(id => {
            const checkbox = document.getElementById('cb_user_' + id);
            if (checkbox) checkbox.checked = true;
        });

        updateSelectionDisplay();
    }

    // Initialize on page load
    document.addEventListener('DOMContentLoaded', function() {
        loadSelectionState();
        updateSelectionDisplay();
    });

    // Handle Streamlit component communication
    window.addEventListener('streamlit:componentReady', function() {
        loadSelectionState();
        updateSelectionDisplay();
    });

    </script>
    """

    components.html(selection_js, height=1)


def _render_instant_candidate_checkbox(candidate_id: str) -> None:
    """Render instant candidate checkbox with zero refresh."""

    checkbox_html = f"""
    <div style="padding: 2px 0;">
        <input 
            type="checkbox" 
            id="cb_candidate_{candidate_id}" 
            onchange="toggleCandidateSelection('{candidate_id}')"
            style="
                width: 18px; 
                height: 18px; 
                cursor: pointer;
                accent-color: #ff4444;
                transform: scale(1.2);
            "
        />
    </div>
    """

    components.html(checkbox_html, height=25)


def _render_instant_user_checkbox(user_id: int) -> None:
    """Render instant user checkbox with zero refresh."""

    checkbox_html = f"""
    <div style="padding: 2px 0;">
        <input 
            type="checkbox" 
            id="cb_user_{user_id}" 
            onchange="toggleUserSelection('{user_id}')"
            style="
                width: 18px; 
                height: 18px; 
                cursor: pointer;
                accent-color: #4444ff;
                transform: scale(1.2);
            "
        />
    </div>
    """

    components.html(checkbox_html, height=25)


def _render_bulk_candidate_controls(candidates: List[Dict], perms: Dict[str, Any]):
    """Render bulk candidate controls with zero refresh operations."""

    if not perms.get("can_delete_records"):
        return

    candidate_ids = [c.get('candidate_id', '') for c in candidates if c.get('candidate_id')]
    candidate_ids_js = json.dumps(candidate_ids)

    bulk_controls_html = f"""
    <!-- Always visible bulk action bar -->
    <div class="candidate-bulk-bar" style="
        background: linear-gradient(90deg, #f0f0f0, #e0e0e0);
        color: #666;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        display: none;
        justify-content: space-between;
        align-items: center;
        transition: all 0.3s ease;
    ">
        <div>
            <h3 style="margin: 0; display: inline;">
                🗑️ <span class="candidate-selection-count">0</span> Candidates Selected
            </h3>
        </div>
        <div style="display: flex; gap: 1rem; align-items: center;">
            <button onclick="showCandidateDeleteConfirmation()" style="
                background: #ff4444;
                color: white;
                border: none;
                padding: 0.75rem 1.5rem;
                border-radius: 25px;
                cursor: pointer;
                font-weight: bold;
                font-size: 1rem;
                transition: all 0.2s ease;
            " onmouseover="this.style.background='#ff6666'" onmouseout="this.style.background='#ff4444'">
                🗑️ DELETE SELECTED
            </button>
            <button onclick="clearAllCandidates()" style="
                background: #666;
                color: white;
                border: none;
                padding: 0.75rem 1.5rem;
                border-radius: 25px;
                cursor: pointer;
                font-weight: bold;
            " onmouseover="this.style.background='#888'" onmouseout="this.style.background='#666'">
                ❌ CLEAR ALL
            </button>
        </div>
    </div>

    <!-- Bulk action quick buttons -->
    <div style="margin: 1rem 0; display: flex; gap: 1rem; flex-wrap: wrap;">
        <button onclick="selectAllCandidates({candidate_ids_js})" style="
            background: #28a745;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.9rem;
        ">☑️ SELECT ALL VISIBLE</button>

        <button onclick="clearAllCandidates()" style="
            background: #dc3545;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.9rem;
        ">❌ CLEAR ALL</button>

        <span style="
            background: #f8f9fa;
            padding: 0.5rem 1rem;
            border-radius: 5px;
            border: 1px solid #dee2e6;
            font-size: 0.9rem;
        ">📊 <span class="candidate-selection-count">0</span> selected</span>
    </div>

    <!-- Zero-refresh confirmation dialog -->
    <div class="candidate-delete-confirmation" style="
        display: none;
        background: linear-gradient(135deg, #ffebee, #ffcdd2);
        border: 2px solid #f44336;
        border-radius: 10px;
        padding: 2rem;
        margin: 2rem 0;
        text-align: center;
    ">
        <h2 style="color: #c62828; margin-top: 0;">
            ⚠️ CONFIRM BULK DELETE
        </h2>
        <p style="font-size: 1.1rem; color: #d32f2f;">
            You are about to permanently delete <strong><span class="candidate-selection-count">0</span> candidates</strong>.
            <br><strong>This action cannot be undone!</strong>
        </p>

        <div style="margin: 2rem 0;">
            <input type="text" id="candidate-delete-confirmation-input" placeholder="Type 'DELETE CANDIDATES' to confirm" style="
                padding: 1rem;
                font-size: 1rem;
                border: 2px solid #f44336;
                border-radius: 5px;
                width: 300px;
                text-align: center;
            " onkeyup="checkCandidateDeleteConfirmation()" />
        </div>

        <div style="display: flex; gap: 1rem; justify-content: center;">
            <button onclick="hideCandidateDeleteConfirmation()" style="
                background: #6c757d;
                color: white;
                border: none;
                padding: 1rem 2rem;
                border-radius: 5px;
                cursor: pointer;
                font-size: 1rem;
            ">❌ CANCEL</button>

            <button id="bulk-candidate-delete-btn" onclick="executeBulkCandidateDelete()" disabled style="
                background: #ccc;
                color: #666;
                border: none;
                padding: 1rem 2rem;
                border-radius: 5px;
                cursor: not-allowed;
                font-size: 1rem;
            ">🗑️ DELETE ALL</button>
        </div>
    </div>

    <script>
    function checkCandidateDeleteConfirmation() {{
        const input = document.getElementById('candidate-delete-confirmation-input');
        const button = document.getElementById('bulk-candidate-delete-btn');

        if (input.value.trim() === 'DELETE CANDIDATES') {{
            button.disabled = false;
            button.style.background = '#dc3545';
            button.style.color = 'white';
            button.style.cursor = 'pointer';
        }} else {{
            button.disabled = true;
            button.style.background = '#ccc';
            button.style.color = '#666';
            button.style.cursor = 'not-allowed';
        }}
    }}
    </script>
    """

    components.html(bulk_controls_html, height=1)


def _render_bulk_user_controls(users: List[Dict], perms: Dict[str, Any]):
    """Render bulk user controls with zero refresh operations."""

    if not perms.get("can_manage_users"):
        return

    user_ids = [str(u.get('id', '')) for u in users if u.get('id')]
    user_ids_js = json.dumps(user_ids)

    bulk_user_controls_html = f"""
    <!-- Always visible bulk user action bar -->
    <div class="user-bulk-bar" style="
        background: linear-gradient(90deg, #f0f0f0, #e0e0e0);
        color: #666;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        display: none;
        justify-content: space-between;
        align-items: center;
        transition: all 0.3s ease;
    ">
        <div>
            <h3 style="margin: 0; display: inline;">
                👥 <span class="user-selection-count">0</span> Users Selected
            </h3>
        </div>
        <div style="display: flex; gap: 1rem; align-items: center;">
            <button onclick="executeBulkPermissionUpdate('can_view_cvs', true)" style="
                background: #28a745;
                color: white;
                border: none;
                padding: 0.5rem 1rem;
                border-radius: 20px;
                cursor: pointer;
                font-size: 0.9rem;
            ">✅ GRANT CV VIEW</button>

            <button onclick="executeBulkPermissionUpdate('can_delete_records', true)" style="
                background: #ffc107;
                color: black;
                border: none;
                padding: 0.5rem 1rem;
                border-radius: 20px;
                cursor: pointer;
                font-size: 0.9rem;
            ">🗑️ GRANT DELETE</button>

            <button onclick="showUserDeleteConfirmation()" style="
                background: #dc3545;
                color: white;
                border: none;
                padding: 0.75rem 1.5rem;
                border-radius: 25px;
                cursor: pointer;
                font-weight: bold;
            ">🗑️ DELETE USERS</button>

            <button onclick="clearAllUsers()" style="
                background: #666;
                color: white;
                border: none;
                padding: 0.5rem 1rem;
                border-radius: 20px;
                cursor: pointer;
            ">❌ CLEAR</button>
        </div>
    </div>

    <!-- Bulk user action quick buttons -->
    <div style="margin: 1rem 0; display: flex; gap: 1rem; flex-wrap: wrap;">
        <button onclick="selectAllUsers({user_ids_js})" style="
            background: #007bff;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.9rem;
        ">☑️ SELECT ALL USERS</button>

        <button onclick="clearAllUsers()" style="
            background: #6c757d;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.9rem;
        ">❌ CLEAR ALL</button>

        <span style="
            background: #e3f2fd;
            padding: 0.5rem 1rem;
            border-radius: 5px;
            border: 1px solid #2196f3;
            font-size: 0.9rem;
        ">👥 <span class="user-selection-count">0</span> selected</span>
    </div>

    <!-- Zero-refresh user delete confirmation dialog -->
    <div class="user-delete-confirmation" style="
        display: none;
        background: linear-gradient(135deg, #e8f4fd, #bbdefb);
        border: 2px solid #2196f3;
        border-radius: 10px;
        padding: 2rem;
        margin: 2rem 0;
        text-align: center;
    ">
        <h2 style="color: #1976d2; margin-top: 0;">
            ⚠️ CONFIRM BULK USER DELETE
        </h2>
        <p style="font-size: 1.1rem; color: #1565c0;">
            You are about to permanently delete <strong><span class="user-selection-count">0</span> users</strong>.
            <br><strong>This will remove their access completely!</strong>
        </p>

        <div style="margin: 2rem 0;">
            <input type="text" id="user-delete-confirmation-input" placeholder="Type 'DELETE USERS' to confirm" style="
                padding: 1rem;
                font-size: 1rem;
                border: 2px solid #2196f3;
                border-radius: 5px;
                width: 300px;
                text-align: center;
            " onkeyup="checkUserDeleteConfirmation()" />
        </div>

        <div style="display: flex; gap: 1rem; justify-content: center;">
            <button onclick="hideUserDeleteConfirmation()" style="
                background: #6c757d;
                color: white;
                border: none;
                padding: 1rem 2rem;
                border-radius: 5px;
                cursor: pointer;
                font-size: 1rem;
            ">❌ CANCEL</button>

            <button id="bulk-user-delete-btn" onclick="executeBulkUserDelete()" disabled style="
                background: #ccc;
                color: #666;
                border: none;
                padding: 1rem 2rem;
                border-radius: 5px;
                cursor: not-allowed;
                font-size: 1rem;
            ">🗑️ DELETE ALL</button>
        </div>
    </div>

    <script>
    function checkUserDeleteConfirmation() {{
        const input = document.getElementById('user-delete-confirmation-input');
        const button = document.getElementById('bulk-user-delete-btn');

        if (input.value.trim() === 'DELETE USERS') {{
            button.disabled = false;
            button.style.background = '#dc3545';
            button.style.color = 'white';
            button.style.cursor = 'pointer';
        }} else {{
            button.disabled = true;
            button.style.background = '#ccc';
            button.style.color = '#666';
            button.style.cursor = 'not-allowed';
        }}
    }}
    </script>
    """

    components.html(bulk_user_controls_html, height=1)


# =============================================================================
# Access Rights Check - Strict Permission Enforcement
# =============================================================================

def _check_user_permissions(user_id: int) -> Dict[str, Any]:
    """Check user permissions with STRICT enforcement."""
    try:
        perms = get_user_permissions(user_id)
        if not perms:
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
# ZERO REFRESH Backend Operations
# =============================================================================

def _handle_bulk_candidate_delete(candidate_ids: List[str], user_id: int) -> bool:
    """Handle bulk candidate deletion with proper error handling."""
    try:
        perms = _check_user_permissions(user_id)
        if not perms.get("can_delete_records", False):
            st.error("🔒 Access Denied: You need 'Delete Records' permission")
            return False

        # Call the delete function from db_postgres with list
        success, reason = delete_candidate(candidate_ids, user_id)

        if success:
            st.success(f"✅ Successfully deleted {len(candidate_ids)} candidates!")
            _clear_candidate_cache()
            return True
        else:
            st.error(f"❌ Bulk delete failed: {reason}")
            return False

    except Exception as e:
        st.error(f"❌ Bulk delete error: {e}")
        return False


def _handle_bulk_user_delete(user_ids: List[str], current_user_id: int) -> bool:
    """Handle bulk user deletion with proper error handling."""
    try:
        perms = _check_user_permissions(current_user_id)
        if not perms.get("can_manage_users", False):
            st.error("🔒 Access Denied: You need 'Manage Users' permission")
            return False

        # Prevent self-deletion
        if str(current_user_id) in user_ids:
            st.error("❌ Cannot delete your own account!")
            return False

        success_count = 0
        failed_count = 0

        conn = get_conn()
        try:
            with conn.cursor() as cur:
                for user_id in user_ids:
                    try:
                        cur.execute("DELETE FROM users WHERE id = %s", (int(user_id),))
                        if cur.rowcount > 0:
                            success_count += 1
                        else:
                            failed_count += 1
                    except Exception as e:
                        st.warning(f"Failed to delete user {user_id}: {e}")
                        failed_count += 1

                conn.commit()

        finally:
            conn.close()

        if success_count > 0:
            st.success(f"✅ Successfully deleted {success_count} users!")
        if failed_count > 0:
            st.error(f"❌ Failed to delete {failed_count} users")

        return success_count > 0

    except Exception as e:
        st.error(f"❌ Bulk user delete error: {e}")
        return False


def _handle_bulk_permission_update(user_ids: List[str], permission: str, value: bool, current_user_id: int) -> bool:
    """Handle bulk permission updates."""
    try:
        perms = _check_user_permissions(current_user_id)
        if not perms.get("can_manage_users", False):
            st.error("🔒 Access Denied: You need 'Manage Users' permission")
            return False

        success_count = 0
        failed_count = 0

        for user_id in user_ids:
            try:
                new_perms = {permission: value}
                if update_user_permissions(int(user_id), new_perms):
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                st.warning(f"Failed to update user {user_id}: {e}")
                failed_count += 1

        if success_count > 0:
            st.success(f"✅ Successfully updated {success_count} users!")
        if failed_count > 0:
            st.error(f"❌ Failed to update {failed_count} users")

        return success_count > 0

    except Exception as e:
        st.error(f"❌ Bulk permission update error: {e}")
        return False


# =============================================================================
# Enhanced User Management Panel with Bulk Operations
# =============================================================================

def show_user_management_panel():
    """Enhanced user management panel with bulk operations and zero refresh."""
    require_login()

    user = get_current_user(refresh=True)
    perms = _check_user_permissions(user.get("id"))

    if not perms.get("can_manage_users", False):
        st.error("Access denied. Admin privileges required.")
        st.stop()

    st.title("👥 User Management Panel")
    st.caption("Manage system users with bulk operations")

    # Render zero refresh manager
    _render_zero_refresh_selection_manager()

    try:
        users = get_all_users_with_permissions()
    except Exception as e:
        st.error(f"Failed to load users: {e}")
        return

    if not users:
        st.info("No system users found.")
        return

    st.info(f"Found {len(users)} system users")

    # Render bulk user controls
    _render_bulk_user_controls(users, perms)

    # Handle JavaScript events
    if 'js_events' not in st.session_state:
        st.session_state.js_events = {}

    # Listen for JavaScript events via query params or session state
    js_event_listener = """
    <script>
    window.addEventListener('bulkUserDelete', function(e) {
        // Send to Streamlit via form submission or session state
        const userIds = e.detail.userIds;
        console.log('Bulk user delete requested:', userIds);

        // Use Streamlit's communication method
        window.parent.postMessage({
            type: 'bulk_user_delete',
            userIds: userIds
        }, '*');
    });

    window.addEventListener('bulkPermissionUpdate', function(e) {
        const {userIds, permission, value} = e.detail;
        console.log('Bulk permission update:', userIds, permission, value);

        window.parent.postMessage({
            type: 'bulk_permission_update',
            userIds: userIds,
            permission: permission,
            value: value
        }, '*');
    });
    </script>
    """
    components.html(js_event_listener, height=1)

    # Process bulk operations if requested
    if st.session_state.get('bulk_user_delete_requested'):
        user_ids = st.session_state.get('bulk_user_delete_ids', [])
        if user_ids:
            if _handle_bulk_user_delete(user_ids, user.get("id")):
                st.session_state.bulk_user_delete_requested = False
                st.session_state.bulk_user_delete_ids = []
                st.rerun()

    if st.session_state.get('bulk_permission_update_requested'):
        user_ids = st.session_state.get('bulk_permission_update_ids', [])
        permission = st.session_state.get('bulk_permission_update_permission', '')
        value = st.session_state.get('bulk_permission_update_value', False)

        if user_ids and permission:
            if _handle_bulk_permission_update(user_ids, permission, value, user.get("id")):
                st.session_state.bulk_permission_update_requested = False
                st.session_state.bulk_permission_update_ids = []
                st.session_state.bulk_permission_update_permission = ''
                st.session_state.bulk_permission_update_value = False
                st.rerun()

    # Display users with instant selection
    for user_data in users:
        user_id = user_data.get('id')
        user_email = user_data.get('email', 'No email')
        user_role = user_data.get('role', 'user')

        with st.container():
            sel_col, content_col = st.columns([0.05, 0.95])

            with sel_col:
                _render_instant_user_checkbox(user_id)

            with content_col:
                with st.expander(f"👤 {user_email} (Role: {user_role})", expanded=False):

                    # User info section
                    info_col, perm_col = st.columns([1, 1])

                    with info_col:
                        st.markdown(f"""
**User ID:** {user_id}
**Email:** {user_email}  
**Role:** {user_role}
**Created:** {_format_datetime(user_data.get('created_at'))}
""")

                    with perm_col:
                        st.markdown("**Quick Actions:**")

                        # Individual permission toggles (still with refresh, but faster)
                        can_view_cvs = st.checkbox(
                            "Can View CVs",
                            value=bool(user_data.get('can_view_cvs', False)),
                            key=f"cv_{user_id}",
                            help="Allow this user to view candidate CVs"
                        )

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
                    st.markdown("---")
                    st.markdown("**Current Permissions:**")
                    perm_col1, perm_col2 = st.columns(2)

                    with perm_col1:
                        cv_status = '✅ Enabled' if user_data.get('can_view_cvs') else '❌ Disabled'
                        st.markdown(f"- **View CVs:** {cv_status}")

                    with perm_col2:
                        del_status = '✅ Enabled' if user_data.get('can_delete_records') else '❌ Disabled'
                        st.markdown(f"- **Delete Records:** {del_status}")


# =============================================================================
# Enhanced CEO Dashboard with Zero Refresh Operations
# =============================================================================

def show_ceo_panel():
    """Enhanced CEO dashboard with zero refresh bulk operations."""
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

    # Render zero refresh manager
    _render_zero_refresh_selection_manager()

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
        st.write("")  # Spacing

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

    # Render bulk candidate controls
    _render_bulk_candidate_controls(filtered_candidates, perms)

    # Handle JavaScript events for bulk operations
    js_event_handler = """
    <script>
    window.addEventListener('bulkCandidateDelete', function(e) {
        const candidateIds = e.detail.candidateIds;
        console.log('Bulk candidate delete requested:', candidateIds);

        // Trigger Streamlit rerun with bulk delete flag
        window.parent.postMessage({
            type: 'bulk_candidate_delete',
            candidateIds: candidateIds
        }, '*');
    });
    </script>
    """
    components.html(js_event_handler, height=1)

    # Process bulk operations if requested
    if st.session_state.get('bulk_candidate_delete_requested'):
        candidate_ids = st.session_state.get('bulk_candidate_delete_ids', [])
        if candidate_ids:
            if _handle_bulk_candidate_delete(candidate_ids, user_id):
                st.session_state.bulk_candidate_delete_requested = False
                st.session_state.bulk_candidate_delete_ids = []
                st.rerun()

    # Alternative method: Use buttons with session state for immediate operations
    bulk_ops_col1, bulk_ops_col2, bulk_ops_col3 = st.columns([2, 1, 1])

    with bulk_ops_col1:
        st.write("")  # Spacing

    with bulk_ops_col2:
        if st.button("🗑️ DELETE SELECTED", key="bulk_delete_btn", type="primary"):
            # Get selected candidates from JavaScript state (would need bridge)
            # For now, use a simple approach with session state
            if hasattr(st.session_state, 'selected_candidate_ids') and st.session_state.selected_candidate_ids:
                st.session_state.bulk_candidate_delete_requested = True
                st.session_state.bulk_candidate_delete_ids = list(st.session_state.selected_candidate_ids)
                st.rerun()
            else:
                st.warning("No candidates selected. Please select candidates using the checkboxes.")

    with bulk_ops_col3:
        if st.button("❌ CLEAR SELECTION", key="clear_selection_btn"):
            if hasattr(st.session_state, 'selected_candidate_ids'):
                st.session_state.selected_candidate_ids = set()
            # Clear JavaScript selection too
            clear_js = """
            <script>
            window.candidateSelections.clear();
            document.querySelectorAll('[id^="cb_candidate_"]').forEach(cb => cb.checked = false);
            updateSelectionDisplay();
            saveSelectionState();
            </script>
            """
            components.html(clear_js, height=1)
            st.rerun()

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

    # Initialize session state for selected candidates
    if 'selected_candidate_ids' not in st.session_state:
        st.session_state.selected_candidate_ids = set()

    # Render candidates with zero refresh selection
    for candidate in page_candidates:
        candidate_id = candidate.get('candidate_id', '')
        candidate_name = candidate.get('name', 'Unnamed')

        with st.container():
            sel_col, content_col = st.columns([0.05, 0.95])

            with sel_col:
                if perms.get("can_delete_records"):
                    _render_instant_candidate_checkbox(candidate_id)
                else:
                    st.write("")

            with content_col:
                with st.expander(f"👤 {candidate_name} ({candidate_id})", expanded=False):
                    main_col, action_col = st.columns([3, 1])

                    with main_col:
                        # Personal details - comprehensive and well-organized
                        _render_personal_details_organized(candidate)

                        # CV Section - with proper access control
                        _render_cv_section_fixed(
                            candidate_id,
                            user_id,
                            candidate.get('has_cv_file', False),
                            candidate.get('has_resume_link', False)
                        )

                        # Interview History - comprehensive with proper formatting
                        history = _get_interview_history_comprehensive(candidate_id)
                        _render_interview_history_comprehensive(history)

                    with action_col:
                        st.markdown("### ⚙️ Actions")
                        st.caption(f"ID: {candidate_id}")

                        # Selection status (read-only display)
                        if perms.get("can_delete_records"):
                            selection_status = """
                            <div id="selection_status_{}" style="
                                padding: 0.5rem;
                                border-radius: 5px;
                                text-align: center;
                                font-weight: bold;
                                margin: 0.5rem 0;
                            ">
                                <span id="status_text_{}">Click checkbox to select</span>
                            </div>

                            <script>
                            function updateSelectionStatus() {{
                                const isSelected = window.candidateSelections && window.candidateSelections.has('{}');
                                const statusDiv = document.getElementById('selection_status_{}');
                                const statusText = document.getElementById('status_text_{}');

                                if (isSelected) {{
                                    statusDiv.style.background = '#d4edda';
                                    statusDiv.style.color = '#155724';
                                    statusDiv.style.border = '1px solid #c3e6cb';
                                    statusText.textContent = '✅ Selected for bulk operations';
                                }} else {{
                                    statusDiv.style.background = '#f8f9fa';
                                    statusDiv.style.color = '#6c757d';
                                    statusDiv.style.border = '1px solid #dee2e6';
                                    statusText.textContent = 'Click checkbox to select';
                                }}
                            }}

                            // Update status periodically
                            setInterval(updateSelectionStatus, 500);
                            setTimeout(updateSelectionStatus, 100);
                            </script>
                            """.format(candidate_id, candidate_id, candidate_id, candidate_id, candidate_id)

                            components.html(selection_status, height=60)

                        # Toggle edit permission (still requires refresh but faster)
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
                            st.success("✏️ Can edit application")
                        else:
                            st.info("🔒 Cannot edit application")

                        # Individual delete button (with confirmation)
                        if perms.get("can_delete_records"):
                            st.markdown("---")
                            individual_delete_key = f"individual_delete_{candidate_id}"

                            if st.session_state.get(individual_delete_key, False):
                                st.warning("⚠️ Confirm individual delete?")
                                del_col1, del_col2 = st.columns(2)

                                with del_col1:
                                    if st.button("✅ Yes", key=f"confirm_individual_{candidate_id}"):
                                        if _handle_bulk_candidate_delete([candidate_id], user_id):
                                            st.session_state[individual_delete_key] = False
                                            st.rerun()

                                with del_col2:
                                    if st.button("❌ No", key=f"cancel_individual_{candidate_id}"):
                                        st.session_state[individual_delete_key] = False
                                        st.rerun()
                            else:
                                if st.button("🗑️ Delete Individual", key=f"delete_individual_{candidate_id}",
                                             type="secondary"):
                                    st.session_state[individual_delete_key] = True
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
        summary_col1, summary_col2 = st.columns(2)

        with summary_col1:
            st.info(
                f"📊 Showing {len(page_candidates)} of {total_candidates} candidates (Page {page if total_pages > 1 else 1} of {total_pages})")

        with summary_col2:
            # Live selection count
            live_count_html = """
            <div style="
                background: linear-gradient(135deg, #e3f2fd, #bbdefb);
                padding: 1rem;
                border-radius: 8px;
                text-align: center;
                border: 1px solid #2196f3;
            ">
                <strong>🎯 <span class="candidate-selection-count">0</span> candidates selected for bulk operations</strong>
            </div>
            """
            components.html(live_count_html, height=60)


# =============================================================================
# Main Router
# =============================================================================

def main():
    """Main application router with enhanced zero refresh capabilities."""
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

    # Initialize session state for all operations
    if 'selected_candidate_ids' not in st.session_state:
        st.session_state.selected_candidate_ids = set()
    if 'bulk_candidate_delete_requested' not in st.session_state:
        st.session_state.bulk_candidate_delete_requested = False
    if 'bulk_user_delete_requested' not in st.session_state:
        st.session_state.bulk_user_delete_requested = False
    if 'bulk_permission_update_requested' not in st.session_state:
        st.session_state.bulk_permission_update_requested = False

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
    st.sidebar.caption("⚡ **ZERO REFRESH** Features:")
    st.sidebar.caption("- ✅ Instant Selection (No Refresh)")
    st.sidebar.caption("- ✅ Bulk Delete (1 Confirmation)")
    st.sidebar.caption("- ✅ Bulk User Management")
    st.sidebar.caption("- ✅ Live Selection Counter")
    st.sidebar.caption("- ✅ JavaScript-Powered UI")
    st.sidebar.caption("- ✅ Fast Cache (10s)")
    st.sidebar.caption("- ✅ Real-time Feedback")

    # Run selected page
    try:
        pages[selected_page]()
    except Exception as e:
        st.error(f"Page error: {e}")
        st.exception(e)


if __name__ == "__main__":
    main()
    _manage_users
    ": False}

    role = (perms.get("role") or "user").lower()

    return {
        "role": role,
        "can_view_cvs": bool(perms.get("can_view_cvs", False)),
        "can_delete_records": bool(perms.get("can_delete_records", False)),
        "can_manage_users": role in ("ceo", "admin")
    }
except Exception as e:
st.error(f"Permission check failed: {e}")
return {"role": "user", "can_view_cvs": False, "can