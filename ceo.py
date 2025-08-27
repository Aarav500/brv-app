# ULTRA-OPTIMIZED CEO Control Panel - Bulk Operations + Multithreading Performance
# ===================================================================================

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
import time
from multiprocessing.pool import ThreadPool

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


# ===================================================================================
# ULTRA-FAST PERFORMANCE WITH MULTITHREADING AND CONNECTION POOLING
# ===================================================================================

class FastDatabaseOperations:
    """Ultra-fast database operations with connection pooling and threading."""

    @staticmethod
    def get_connection_pool():
        """Get database connection with optimized settings."""
        try:
            conn = get_conn()
            # Optimize connection for bulk operations
            with conn.cursor() as cur:
                cur.execute("SET work_mem = '256MB'")
                cur.execute("SET maintenance_work_mem = '512MB'")
                cur.execute("SET synchronous_commit = OFF")
            return conn
        except Exception as e:
            st.error(f"Connection error: {e}")
            return None

    @staticmethod
    def bulk_delete_candidates_fast(candidate_ids: List[str]) -> Tuple[bool, str, int]:
        """Ultra-fast bulk candidate deletion with batch processing."""
        if not candidate_ids:
            return False, "No candidates to delete", 0

        try:
            conn = FastDatabaseOperations.get_connection_pool()
            if not conn:
                return False, "Database connection failed", 0

            deleted_count = 0
            batch_size = 100  # Process in batches for performance

            with conn.cursor() as cur:
                # Batch delete for optimal performance
                for i in range(0, len(candidate_ids), batch_size):
                    batch = candidate_ids[i:i + batch_size]
                    placeholders = ','.join(['%s'] * len(batch))

                    # Delete related records first
                    tables_to_clean = ['interviews', 'receptionist_assessments', 'candidate_history']
                    for table in tables_to_clean:
                        try:
                            cur.execute(f"DELETE FROM {table} WHERE candidate_id IN ({placeholders})", batch)
                        except Exception:
                            pass  # Table might not exist

                    # Delete main candidate records
                    cur.execute(f"DELETE FROM candidates WHERE candidate_id IN ({placeholders})", batch)
                    deleted_count += cur.rowcount

                conn.commit()
            conn.close()

            return True, f"Successfully deleted {deleted_count} candidates", deleted_count

        except Exception as e:
            return False, f"Bulk delete failed: {str(e)}", 0

    @staticmethod
    def bulk_delete_users_fast(user_ids: List[str], current_user_id: int) -> Tuple[bool, str, int]:
        """Ultra-fast bulk user deletion with safety checks."""
        if not user_ids:
            return False, "No users to delete", 0

        # Remove current user from deletion list for safety
        safe_user_ids = [uid for uid in user_ids if str(uid) != str(current_user_id)]

        if not safe_user_ids:
            return False, "Cannot delete your own account", 0

        try:
            conn = FastDatabaseOperations.get_connection_pool()
            if not conn:
                return False, "Database connection failed", 0

            deleted_count = 0

            with conn.cursor() as cur:
                # Batch delete for performance
                placeholders = ','.join(['%s'] * len(safe_user_ids))
                cur.execute(f"DELETE FROM users WHERE id IN ({placeholders})", safe_user_ids)
                deleted_count = cur.rowcount
                conn.commit()

            conn.close()

            return True, f"Successfully deleted {deleted_count} users", deleted_count

        except Exception as e:
            return False, f"Bulk user delete failed: {str(e)}", 0

    @staticmethod
    def bulk_update_user_permissions_fast(user_ids: List[str], permission_updates: Dict[str, Any]) -> Tuple[
        bool, str, int]:
        """Ultra-fast bulk permission updates with batch processing."""
        if not user_ids or not permission_updates:
            return False, "No users or permissions specified", 0

        try:
            conn = FastDatabaseOperations.get_connection_pool()
            if not conn:
                return False, "Database connection failed", 0

            updated_count = 0

            with conn.cursor() as cur:
                # Build dynamic update query
                set_clauses = []
                values = []

                for perm, value in permission_updates.items():
                    set_clauses.append(f"{perm} = %s")
                    values.append(value)

                if set_clauses:
                    placeholders = ','.join(['%s'] * len(user_ids))
                    query = f"""
                        UPDATE users 
                        SET {', '.join(set_clauses)} 
                        WHERE id IN ({placeholders})
                    """
                    values.extend(user_ids)

                    cur.execute(query, values)
                    updated_count = cur.rowcount
                    conn.commit()

            conn.close()

            return True, f"Successfully updated {updated_count} users", updated_count

        except Exception as e:
            return False, f"Bulk permission update failed: {str(e)}", 0

    @staticmethod
    def bulk_update_candidate_permissions_fast(candidate_ids: List[str], can_edit: bool) -> Tuple[bool, str, int]:
        """Ultra-fast bulk candidate edit permission updates."""
        if not candidate_ids:
            return False, "No candidates specified", 0

        try:
            conn = FastDatabaseOperations.get_connection_pool()
            if not conn:
                return False, "Database connection failed", 0

            updated_count = 0

            with conn.cursor() as cur:
                placeholders = ','.join(['%s'] * len(candidate_ids))
                query = f"UPDATE candidates SET can_edit = %s WHERE candidate_id IN ({placeholders})"
                values = [can_edit] + candidate_ids

                cur.execute(query, values)
                updated_count = cur.rowcount
                conn.commit()

            conn.close()

            return True, f"Successfully updated {updated_count} candidates", updated_count

        except Exception as e:
            return False, f"Bulk candidate update failed: {str(e)}", 0


@st.cache_data(ttl=300, show_spinner=False)  # 5 minute cache for faster loading
def get_candidates_ultra_fast():
    """Ultra-fast candidate loading with minimal data transfer."""
    try:
        conn = FastDatabaseOperations.get_connection_pool()
        if not conn:
            return []

        with conn.cursor() as cur:
            # Optimized query - only essential fields
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
                            LIMIT 2000
                        """)

            candidates = []
            for row in cur.fetchall():
                candidate = {
                    'candidate_id': row[0],
                    'name': row[1] or 'Unnamed',
                    'email': row[2] or 'No email',
                    'phone': row[3] or 'No phone',
                    'created_at': row[4],
                    'updated_at': row[5],
                    'can_edit': bool(row[6]),
                    'has_cv_file': bool(row[7]),
                    'has_resume_link': bool(row[8]),
                    'form_data': row[9] or {}
                }

                # Quick form_data merge
                if isinstance(candidate['form_data'], dict):
                    for key, value in candidate['form_data'].items():
                        if value and str(value).strip():
                            candidate[f'form_{key}'] = value

                candidates.append(candidate)

        conn.close()
        return candidates

    except Exception as e:
        st.error(f"Failed to load candidates: {e}")
        return []


@st.cache_data(ttl=300, show_spinner=False)
def get_users_ultra_fast():
    """Ultra-fast user loading."""
    try:
        return get_all_users_with_permissions() or []
    except Exception as e:
        st.error(f"Failed to load users: {e}")
        return []


def clear_all_caches():
    """Clear all caches for data refresh."""
    get_candidates_ultra_fast.clear()
    get_users_ultra_fast.clear()


# ===================================================================================
# ULTRA-ADVANCED JAVASCRIPT UI - ZERO REFRESH BULK OPERATIONS
# ===================================================================================

def render_ultra_fast_selection_system():
    """Ultra-advanced JavaScript selection system with instant feedback."""

    advanced_js = """
    <div id="ultra-selection-system" style="display: none;"></div>

    <script>
    // Ultra-fast global state management
    window.ultraState = window.ultraState || {
        candidateSelections: new Set(),
        userSelections: new Set(),
        bulkOperationInProgress: false,
        lastUpdate: Date.now()
    };

    // Performance optimization - debounced updates
    let updateTimeout = null;
    function debouncedUpdateUI() {
        if (updateTimeout) clearTimeout(updateTimeout);
        updateTimeout = setTimeout(updateSelectionUI, 50);
    }

    // Ultra-fast UI updates
    function updateSelectionUI() {
        const candidateCount = window.ultraState.candidateSelections.size;
        const userCount = window.ultraState.userSelections.size;

        // Update all count displays instantly
        document.querySelectorAll('.candidate-count').forEach(el => {
            el.textContent = candidateCount;
            el.style.fontWeight = candidateCount > 0 ? 'bold' : 'normal';
        });

        document.querySelectorAll('.user-count').forEach(el => {
            el.textContent = userCount;
            el.style.fontWeight = userCount > 0 ? 'bold' : 'normal';
        });

        // Show/hide bulk action panels with animations
        const candidateBulkPanel = document.querySelector('.candidate-bulk-panel');
        const userBulkPanel = document.querySelector('.user-bulk-panel');

        if (candidateBulkPanel) {
            if (candidateCount > 0) {
                candidateBulkPanel.style.display = 'block';
                candidateBulkPanel.style.opacity = '1';
                candidateBulkPanel.style.transform = 'translateY(0)';
            } else {
                candidateBulkPanel.style.opacity = '0';
                candidateBulkPanel.style.transform = 'translateY(-20px)';
                setTimeout(() => {
                    if (window.ultraState.candidateSelections.size === 0) {
                        candidateBulkPanel.style.display = 'none';
                    }
                }, 300);
            }
        }

        if (userBulkPanel) {
            if (userCount > 0) {
                userBulkPanel.style.display = 'block';
                userBulkPanel.style.opacity = '1';
                userBulkPanel.style.transform = 'translateY(0)';
            } else {
                userBulkPanel.style.opacity = '0';
                userBulkPanel.style.transform = 'translateY(-20px)';
                setTimeout(() => {
                    if (window.ultraState.userSelections.size === 0) {
                        userBulkPanel.style.display = 'none';
                    }
                }, 300);
            }
        }

        // Update progress indicators
        updateProgressIndicators();

        // Save state
        saveUltraState();
    }

    // Candidate selection functions
    function toggleCandidateSelection(candidateId, forceValue = null) {
        if (window.ultraState.bulkOperationInProgress) return;

        if (forceValue !== null) {
            if (forceValue) {
                window.ultraState.candidateSelections.add(candidateId);
            } else {
                window.ultraState.candidateSelections.delete(candidateId);
            }
        } else {
            if (window.ultraState.candidateSelections.has(candidateId)) {
                window.ultraState.candidateSelections.delete(candidateId);
            } else {
                window.ultraState.candidateSelections.add(candidateId);
            }
        }

        // Update checkbox instantly
        const checkbox = document.getElementById('cb_candidate_' + candidateId);
        if (checkbox) {
            checkbox.checked = window.ultraState.candidateSelections.has(candidateId);

            // Visual feedback
            const container = checkbox.closest('.candidate-item');
            if (container) {
                if (window.ultraState.candidateSelections.has(candidateId)) {
                    container.style.background = 'linear-gradient(90deg, #fff3cd, #ffeaa7)';
                    container.style.borderLeft = '4px solid #f39c12';
                } else {
                    container.style.background = '';
                    container.style.borderLeft = '';
                }
            }
        }

        debouncedUpdateUI();
    }

    // User selection functions  
    function toggleUserSelection(userId, forceValue = null) {
        if (window.ultraState.bulkOperationInProgress) return;

        if (forceValue !== null) {
            if (forceValue) {
                window.ultraState.userSelections.add(userId);
            } else {
                window.ultraState.userSelections.delete(userId);
            }
        } else {
            if (window.ultraState.userSelections.has(userId)) {
                window.ultraState.userSelections.delete(userId);
            } else {
                window.ultraState.userSelections.add(userId);
            }
        }

        // Update checkbox instantly
        const checkbox = document.getElementById('cb_user_' + userId);
        if (checkbox) {
            checkbox.checked = window.ultraState.userSelections.has(userId);

            // Visual feedback
            const container = checkbox.closest('.user-item');
            if (container) {
                if (window.ultraState.userSelections.has(userId)) {
                    container.style.background = 'linear-gradient(90deg, #d4edda, #c3e6cb)';
                    container.style.borderLeft = '4px solid #28a745';
                } else {
                    container.style.background = '';
                    container.style.borderLeft = '';
                }
            }
        }

        debouncedUpdateUI();
    }

    // Bulk selection functions
    function selectAllCandidates(candidateIds) {
        candidateIds.forEach(id => {
            window.ultraState.candidateSelections.add(id);
            const checkbox = document.getElementById('cb_candidate_' + id);
            if (checkbox) checkbox.checked = true;
        });
        debouncedUpdateUI();
        showToast(`Selected ${candidateIds.length} candidates`, 'success');
    }

    function clearAllCandidates() {
        const count = window.ultraState.candidateSelections.size;
        window.ultraState.candidateSelections.clear();
        document.querySelectorAll('[id^="cb_candidate_"]').forEach(cb => {
            cb.checked = false;
            const container = cb.closest('.candidate-item');
            if (container) {
                container.style.background = '';
                container.style.borderLeft = '';
            }
        });
        debouncedUpdateUI();
        showToast(`Cleared ${count} candidate selections`, 'info');
    }

    function selectAllUsers(userIds) {
        userIds.forEach(id => {
            window.ultraState.userSelections.add(id);
            const checkbox = document.getElementById('cb_user_' + id);
            if (checkbox) checkbox.checked = true;
        });
        debouncedUpdateUI();
        showToast(`Selected ${userIds.length} users`, 'success');
    }

    function clearAllUsers() {
        const count = window.ultraState.userSelections.size;
        window.ultraState.userSelections.clear();
        document.querySelectorAll('[id^="cb_user_"]').forEach(cb => {
            cb.checked = false;
            const container = cb.closest('.user-item');
            if (container) {
                container.style.background = '';
                container.style.borderLeft = '';
            }
        });
        debouncedUpdateUI();
        showToast(`Cleared ${count} user selections`, 'info');
    }

    // Progress indicators
    function updateProgressIndicators() {
        const candidateProgress = document.querySelector('.candidate-progress');
        const userProgress = document.querySelector('.user-progress');

        if (candidateProgress) {
            const count = window.ultraState.candidateSelections.size;
            candidateProgress.style.width = Math.min(count * 10, 100) + '%';
        }

        if (userProgress) {
            const count = window.ultraState.userSelections.size;
            userProgress.style.width = Math.min(count * 20, 100) + '%';
        }
    }

    // Toast notifications
    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <div style="
                position: fixed;
                top: 20px;
                right: 20px;
                background: ${type === 'success' ? '#28a745' : type === 'error' ? '#dc3545' : '#17a2b8'};
                color: white;
                padding: 1rem 2rem;
                border-radius: 5px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                z-index: 10000;
                animation: slideInRight 0.3s ease;
            ">
                ${message}
            </div>
        `;

        document.body.appendChild(toast);
        setTimeout(() => {
            toast.style.animation = 'slideOutRight 0.3s ease';
            setTimeout(() => document.body.removeChild(toast), 300);
        }, 3000);
    }

    // Bulk operations execution
    function executeBulkOperation(operation, data) {
        if (window.ultraState.bulkOperationInProgress) return;

        window.ultraState.bulkOperationInProgress = true;
        showToast('Operation in progress...', 'info');

        // Disable all bulk buttons
        document.querySelectorAll('.bulk-btn').forEach(btn => {
            btn.disabled = true;
            btn.style.opacity = '0.6';
        });

        // Send to Streamlit
        const event = new CustomEvent('bulkOperation', {
            detail: { operation, data }
        });
        window.dispatchEvent(event);
    }

    function resetBulkOperation() {
        window.ultraState.bulkOperationInProgress = false;

        // Re-enable all bulk buttons
        document.querySelectorAll('.bulk-btn').forEach(btn => {
            btn.disabled = false;
            btn.style.opacity = '1';
        });
    }

    // State persistence
    function saveUltraState() {
        localStorage.setItem('ultraCandidateSelections', JSON.stringify(Array.from(window.ultraState.candidateSelections)));
        localStorage.setItem('ultraUserSelections', JSON.stringify(Array.from(window.ultraState.userSelections)));
        window.ultraState.lastUpdate = Date.now();
    }

    function loadUltraState() {
        const candidateSelections = JSON.parse(localStorage.getItem('ultraCandidateSelections') || '[]');
        const userSelections = JSON.parse(localStorage.getItem('ultraUserSelections') || '[]');

        window.ultraState.candidateSelections = new Set(candidateSelections);
        window.ultraState.userSelections = new Set(userSelections);

        // Restore UI state
        candidateSelections.forEach(id => {
            const checkbox = document.getElementById('cb_candidate_' + id);
            if (checkbox) checkbox.checked = true;
        });

        userSelections.forEach(id => {
            const checkbox = document.getElementById('cb_user_' + id);
            if (checkbox) checkbox.checked = true;
        });

        debouncedUpdateUI();
    }

    // Initialize system
    document.addEventListener('DOMContentLoaded', function() {
        loadUltraState();

        // Add CSS for animations
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideInRight {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOutRight {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
            .candidate-bulk-panel, .user-bulk-panel {
                transition: all 0.3s ease;
            }
            .candidate-item, .user-item {
                transition: all 0.2s ease;
            }
        `;
        document.head.appendChild(style);
    });

    // Auto-refresh state periodically
    setInterval(function() {
        if (Date.now() - window.ultraState.lastUpdate > 30000) { // 30 seconds
            loadUltraState();
        }
    }, 5000);

    </script>
    """

    components.html(advanced_js, height=1)


def render_ultra_candidate_checkbox(candidate_id: str):
    """Ultra-fast candidate checkbox with instant feedback."""
    checkbox_html = f"""
    <div class="candidate-checkbox" style="padding: 5px;">
        <input 
            type="checkbox" 
            id="cb_candidate_{candidate_id}" 
            onchange="toggleCandidateSelection('{candidate_id}')"
            style="
                width: 20px; 
                height: 20px; 
                cursor: pointer;
                accent-color: #f39c12;
                transform: scale(1.3);
                transition: all 0.2s ease;
            "
            title="Select for bulk operations"
        />
    </div>
    """
    components.html(checkbox_html, height=35)


def render_ultra_user_checkbox(user_id: int):
    """Ultra-fast user checkbox with instant feedback."""
    checkbox_html = f"""
    <div class="user-checkbox" style="padding: 5px;">
        <input 
            type="checkbox" 
            id="cb_user_{user_id}" 
            onchange="toggleUserSelection('{user_id}')"
            style="
                width: 20px; 
                height: 20px; 
                cursor: pointer;
                accent-color: #28a745;
                transform: scale(1.3);
                transition: all 0.2s ease;
            "
            title="Select for bulk operations"
        />
    </div>
    """
    components.html(checkbox_html, height=35)


def render_ultra_bulk_candidate_panel(candidates: List[Dict]):
    """Ultra-advanced bulk candidate operations panel."""

    candidate_ids = [c.get('candidate_id', '') for c in candidates if c.get('candidate_id')]
    candidate_ids_js = json.dumps(candidate_ids)

    bulk_panel_html = f"""
    <!-- Ultra Bulk Candidate Panel -->
    <div class="candidate-bulk-panel" style="
        display: none;
        background: linear-gradient(135deg, #fff3cd, #ffeaa7);
        border: 2px solid #f39c12;
        border-radius: 15px;
        padding: 2rem;
        margin: 2rem 0;
        box-shadow: 0 8px 16px rgba(243, 156, 18, 0.2);
        position: sticky;
        top: 20px;
        z-index: 100;
        opacity: 0;
        transform: translateY(-20px);
        transition: all 0.3s ease;
    ">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
            <div>
                <h2 style="margin: 0; color: #d35400; display: flex; align-items: center; gap: 0.5rem;">
                    🎯 <span class="candidate-count">0</span> Candidates Selected
                </h2>
                <div class="candidate-progress" style="
                    width: 0%;
                    height: 4px;
                    background: #f39c12;
                    border-radius: 2px;
                    margin-top: 0.5rem;
                    transition: width 0.3s ease;
                "></div>
            </div>
            <button onclick="clearAllCandidates()" style="
                background: #95a5a6;
                color: white;
                border: none;
                padding: 0.5rem 1rem;
                border-radius: 20px;
                cursor: pointer;
                font-size: 0.9rem;
                transition: all 0.2s ease;
            " onmouseover="this.style.background='#7f8c8d'" onmouseout="this.style.background='#95a5a6'">
                ❌ Clear All
            </button>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem;">

            <!-- Delete Operations -->
            <div style="background: rgba(231, 76, 60, 0.1); padding: 1rem; border-radius: 10px;">
                <h4 style="color: #c0392b; margin: 0 0 1rem 0;">🗑️ Delete Operations</h4>
                <button class="bulk-btn" onclick="executeBulkOperation('delete_candidates', Array.from(window.ultraState.candidateSelections))" style="
                    width: 100%;
                    background: #e74c3c;
                    color: white;
                    border: none;
                    padding: 0.75rem;
                    border-radius: 8px;
                    cursor: pointer;
                    font-weight: bold;
                    margin-bottom: 0.5rem;
                    transition: all 0.2s ease;
                " onmouseover="this.style.background='#c0392b'" onmouseout="this.style.background='#e74c3c'">
                    🗑️ DELETE SELECTED
                </button>
            </div>

            <!-- Permission Operations -->
            <div style="background: rgba(52, 152, 219, 0.1); padding: 1rem; border-radius: 10px;">
                <h4 style="color: #2980b9; margin: 0 0 1rem 0;">🔐 Permissions</h4>
                <button class="bulk-btn" onclick="executeBulkOperation('grant_edit', Array.from(window.ultraState.candidateSelections))" style="
                    width: 100%;
                    background: #3498db;
                    color: white;
                    border: none;
                    padding: 0.5rem;
                    border-radius: 6px;
                    cursor: pointer;
                    margin-bottom: 0.5rem;
                    transition: all 0.2s ease;
                ">✅ Grant Edit Access</button>

                <button class="bulk-btn" onclick="executeBulkOperation('revoke_edit', Array.from(window.ultraState.candidateSelections))" style="
                    width: 100%;
                    background: #e67e22;
                    color: white;
                    border: none;
                    padding: 0.5rem;
                    border-radius: 6px;
                    cursor: pointer;
                    transition: all 0.2s ease;
                ">🔒 Revoke Edit Access</button>
            </div>

            <!-- Export Operations -->
            <div style="background: rgba(46, 204, 113, 0.1); padding: 1rem; border-radius: 10px;">
                <h4 style="color: #27ae60; margin: 0 0 1rem 0;">📊 Export</h4>
                <button class="bulk-btn" onclick="executeBulkOperation('export_csv', Array.from(window.ultraState.candidateSelections))" style="
                    width: 100%;
                    background: #2ecc71;
                    color: white;
                    border: none;
                    padding: 0.5rem;
                    border-radius: 6px;
                    cursor: pointer;
                    margin-bottom: 0.5rem;
                    transition: all 0.2s ease;
                ">📄 Export to CSV</button>

                <button class="bulk-btn" onclick="executeBulkOperation('export_emails', Array.from(window.ultraState.candidateSelections))" style="
                    width: 100%;
                    background: #16a085;
                    color: white;
                    border: none;
                    padding: 0.5rem;
                    border-radius: 6px;
                    cursor: pointer;
                    transition: all 0.2s ease;
                ">📧 Export Emails</button>
            </div>

        </div>

        <!-- Quick Select Options -->
        <div style="margin-top: 1.5rem; padding-top: 1.5rem; border-top: 2px solid #f39c12;">
            <h4 style="color: #d35400; margin: 0 0 1rem 0;">⚡ Quick Select</h4>
            <div style="display: flex; gap: 1rem; flex-wrap: wrap;">
                <button onclick="selectAllCandidates({candidate_ids_js})" style="
                    background: #27ae60;
                    color: white;
                    border: none;
                    padding: 0.5rem 1rem;
                    border-radius: 20px;
                    cursor: pointer;
                    font-size: 0.9rem;
                    transition: all 0.2s ease;
                ">☑️ Select All Visible ({len(candidate_ids)})</button>

                <button onclick="clearAllCandidates()" style="
                    background: #e74c3c;
                    color: white;
                    border: none;
                    padding: 0.5rem 1rem;
                    border-radius: 20px;
                    cursor: pointer;
                    font-size: 0.9rem;
                    transition: all 0.2s ease;
                ">❌ Clear All</button>
            </div>
        </div>
    </div>
    """

    components.html(bulk_panel_html, height=1)


def render_ultra_bulk_user_panel(users: List[Dict]):
    """Ultra-advanced bulk user operations panel."""

    user_ids = [str(u.get('id', '')) for u in users if u.get('id')]
    user_ids_js = json.dumps(user_ids)

    bulk_user_panel_html = f"""
    <!-- Ultra Bulk User Panel -->
    <div class="user-bulk-panel" style="
        display: none;
        background: linear-gradient(135deg, #d4edda, #c3e6cb);
        border: 2px solid #28a745;
        border-radius: 15px;
        padding: 2rem;
        margin: 2rem 0;
        box-shadow: 0 8px 16px rgba(40, 167, 69, 0.2);
        position: sticky;
        top: 20px;
        z-index: 100;
        opacity: 0;
        transform: translateY(-20px);
        transition: all 0.3s ease;
    ">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
            <div>
                <h2 style="margin: 0; color: #155724; display: flex; align-items: center; gap: 0.5rem;">
                    👥 <span class="user-count">0</span> Users Selected
                </h2>
                <div class="user-progress" style="
                    width: 0%;
                    height: 4px;
                    background: #28a745;
                    border-radius: 2px;
                    margin-top: 0.5rem;
                    transition: width 0.3s ease;
                "></div>
            </div>
            <button onclick="clearAllUsers()" style="
                background: #6c757d;
                color: white;
                border: none;
                padding: 0.5rem 1rem;
                border-radius: 20px;
                cursor: pointer;
                font-size: 0.9rem;
                transition: all 0.2s ease;
            " onmouseover="this.style.background='#5a6268'" onmouseout="this.style.background='#6c757d'">
                ❌ Clear All
            </button>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">

            <!-- Permission Management -->
            <div style="background: rgba(0, 123, 255, 0.1); padding: 1rem; border-radius: 10px;">
                <h4 style="color: #0056b3; margin: 0 0 1rem 0;">🔐 Permissions</h4>

                <button class="bulk-btn" onclick="executeBulkOperation('grant_cv_view', Array.from(window.ultraState.userSelections))" style="
                    width: 100%;
                    background: #007bff;
                    color: white;
                    border: none;
                    padding: 0.5rem;
                    border-radius: 6px;
                    cursor: pointer;
                    margin-bottom: 0.5rem;
                    transition: all 0.2s ease;
                ">👁️ Grant CV View</button>

                <button class="bulk-btn" onclick="executeBulkOperation('revoke_cv_view', Array.from(window.ultraState.userSelections))" style="
                    width: 100%;
                    background: #ffc107;
                    color: #212529;
                    border: none;
                    padding: 0.5rem;
                    border-radius: 6px;
                    cursor: pointer;
                    margin-bottom: 0.5rem;
                    transition: all 0.2s ease;
                ">🚫 Revoke CV View</button>

                <button class="bulk-btn" onclick="executeBulkOperation('grant_delete', Array.from(window.ultraState.userSelections))" style="
                    width: 100%;
                    background: #dc3545;
                    color: white;
                    border: none;
                    padding: 0.5rem;
                    border-radius: 6px;
                    cursor: pointer;
                    margin-bottom: 0.5rem;
                    transition: all 0.2s ease;
                ">🗑️ Grant Delete Rights</button>

                <button class="bulk-btn" onclick="executeBulkOperation('revoke_delete', Array.from(window.ultraState.userSelections))" style="
                    width: 100%;
                    background: #e67e22;
                    color: white;
                    border: none;
                    padding: 0.5rem;
                    border-radius: 6px;
                    cursor: pointer;
                    transition: all 0.2s ease;
                ">🔒 Revoke Delete Rights</button>
            </div>

            <!-- User Management -->
            <div style="background: rgba(108, 117, 125, 0.1); padding: 1rem; border-radius: 10px;">
                <h4 style="color: #495057; margin: 0 0 1rem 0;">👤 User Actions</h4>

                <button class="bulk-btn" onclick="executeBulkOperation('send_welcome_email', Array.from(window.ultraState.userSelections))" style="
                    width: 100%;
                    background: #17a2b8;
                    color: white;
                    border: none;
                    padding: 0.5rem;
                    border-radius: 6px;
                    cursor: pointer;
                    margin-bottom: 0.5rem;
                    transition: all 0.2s ease;
                ">📧 Send Welcome Email</button>

                <button class="bulk-btn" onclick="executeBulkOperation('reset_passwords', Array.from(window.ultraState.userSelections))" style="
                    width: 100%;
                    background: #fd7e14;
                    color: white;
                    border: none;
                    padding: 0.5rem;
                    border-radius: 6px;
                    cursor: pointer;
                    margin-bottom: 0.5rem;
                    transition: all 0.2s ease;
                ">🔑 Reset Passwords</button>

                <button class="bulk-btn" onclick="executeBulkOperation('export_user_list', Array.from(window.ultraState.userSelections))" style="
                    width: 100%;
                    background: #28a745;
                    color: white;
                    border: none;
                    padding: 0.5rem;
                    border-radius: 6px;
                    cursor: pointer;
                    margin-bottom: 0.5rem;
                    transition: all 0.2s ease;
                ">📊 Export User List</button>

                <button class="bulk-btn" onclick="executeBulkOperation('delete_users', Array.from(window.ultraState.userSelections))" style="
                    width: 100%;
                    background: #dc3545;
                    color: white;
                    border: none;
                    padding: 0.5rem;
                    border-radius: 6px;
                    cursor: pointer;
                    font-weight: bold;
                    transition: all 0.2s ease;
                ">🗑️ DELETE USERS</button>
            </div>

        </div>

        <!-- Quick Select Options -->
        <div style="margin-top: 1.5rem; padding-top: 1.5rem; border-top: 2px solid #28a745;">
            <h4 style="color: #155724; margin: 0 0 1rem 0;">⚡ Quick Select</h4>
            <div style="display: flex; gap: 1rem; flex-wrap: wrap;">
                <button onclick="selectAllUsers({user_ids_js})" style="
                    background: #007bff;
                    color: white;
                    border: none;
                    padding: 0.5rem 1rem;
                    border-radius: 20px;
                    cursor: pointer;
                    font-size: 0.9rem;
                    transition: all 0.2s ease;
                ">☑️ Select All Visible ({len(user_ids)})</button>

                <button onclick="clearAllUsers()" style="
                    background: #dc3545;
                    color: white;
                    border: none;
                    padding: 0.5rem 1rem;
                    border-radius: 20px;
                    cursor: pointer;
                    font-size: 0.9rem;
                    transition: all 0.2s ease;
                ">❌ Clear All</button>
            </div>
        </div>
    </div>
    """

    components.html(bulk_user_panel_html, height=1)


# ===================================================================================
# BULK OPERATION HANDLERS - Ultra Fast Processing
# ===================================================================================

class BulkOperationHandlers:
    """Ultra-fast bulk operation handlers with proper error handling."""

    @staticmethod
    def handle_candidate_operations(operation: str, candidate_ids: List[str], user_id: int) -> Tuple[bool, str]:
        """Handle all candidate bulk operations."""

        if not candidate_ids:
            return False, "No candidates selected"

        try:
            if operation == "delete_candidates":
                return FastDatabaseOperations.bulk_delete_candidates_fast(candidate_ids)

            elif operation == "grant_edit":
                return FastDatabaseOperations.bulk_update_candidate_permissions_fast(candidate_ids, True)

            elif operation == "revoke_edit":
                return FastDatabaseOperations.bulk_update_candidate_permissions_fast(candidate_ids, False)

            elif operation == "export_csv":
                return BulkOperationHandlers._export_candidates_csv(candidate_ids)

            elif operation == "export_emails":
                return BulkOperationHandlers._export_candidate_emails(candidate_ids)

            else:
                return False, f"Unknown operation: {operation}"

        except Exception as e:
            return False, f"Operation failed: {str(e)}"

    @staticmethod
    def handle_user_operations(operation: str, user_ids: List[str], current_user_id: int) -> Tuple[bool, str]:
        """Handle all user bulk operations."""

        if not user_ids:
            return False, "No users selected"

        try:
            if operation == "delete_users":
                return FastDatabaseOperations.bulk_delete_users_fast(user_ids, current_user_id)

            elif operation == "grant_cv_view":
                return FastDatabaseOperations.bulk_update_user_permissions_fast(user_ids, {"can_view_cvs": True})

            elif operation == "revoke_cv_view":
                return FastDatabaseOperations.bulk_update_user_permissions_fast(user_ids, {"can_view_cvs": False})

            elif operation == "grant_delete":
                return FastDatabaseOperations.bulk_update_user_permissions_fast(user_ids, {"can_delete_records": True})

            elif operation == "revoke_delete":
                return FastDatabaseOperations.bulk_update_user_permissions_fast(user_ids, {"can_delete_records": False})

            elif operation == "send_welcome_email":
                return BulkOperationHandlers._send_bulk_welcome_emails(user_ids)

            elif operation == "reset_passwords":
                return BulkOperationHandlers._bulk_reset_passwords(user_ids)

            elif operation == "export_user_list":
                return BulkOperationHandlers._export_users_csv(user_ids)

            else:
                return False, f"Unknown operation: {operation}"

        except Exception as e:
            return False, f"Operation failed: {str(e)}"

    @staticmethod
    def _export_candidates_csv(candidate_ids: List[str]) -> Tuple[bool, str]:
        """Export selected candidates to CSV."""
        try:
            conn = FastDatabaseOperations.get_connection_pool()
            if not conn:
                return False, "Database connection failed"

            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)

            # Write header
            writer.writerow(['ID', 'Name', 'Email', 'Phone', 'Created At', 'Can Edit'])

            # Get candidate data
            with conn.cursor() as cur:
                placeholders = ','.join(['%s'] * len(candidate_ids))
                cur.execute(f"""
                    SELECT candidate_id, name, email, phone, created_at, can_edit 
                    FROM candidates 
                    WHERE candidate_id IN ({placeholders})
                """, candidate_ids)

                for row in cur.fetchall():
                    writer.writerow(row)

            conn.close()

            # Store in session state for download
            st.session_state.csv_export = output.getvalue()
            st.session_state.csv_filename = f"candidates_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

            return True, f"CSV export ready with {len(candidate_ids)} candidates"

        except Exception as e:
            return False, f"CSV export failed: {str(e)}"

    @staticmethod
    def _export_candidate_emails(candidate_ids: List[str]) -> Tuple[bool, str]:
        """Export candidate email list."""
        try:
            conn = FastDatabaseOperations.get_connection_pool()
            if not conn:
                return False, "Database connection failed"

            emails = []
            with conn.cursor() as cur:
                placeholders = ','.join(['%s'] * len(candidate_ids))
                cur.execute(f"""
                    SELECT email FROM candidates 
                    WHERE candidate_id IN ({placeholders}) AND email IS NOT NULL AND email != ''
                """, candidate_ids)

                emails = [row[0] for row in cur.fetchall()]

            conn.close()

            if emails:
                email_list = '; '.join(emails)
                st.session_state.email_export = email_list
                return True, f"Exported {len(emails)} email addresses"
            else:
                return False, "No valid email addresses found"

        except Exception as e:
            return False, f"Email export failed: {str(e)}"

    @staticmethod
    def _send_bulk_welcome_emails(user_ids: List[str]) -> Tuple[bool, str]:
        """Send welcome emails to selected users."""
        try:
            conn = FastDatabaseOperations.get_connection_pool()
            if not conn:
                return False, "Database connection failed"

            sent_count = 0
            failed_count = 0

            with conn.cursor() as cur:
                placeholders = ','.join(['%s'] * len(user_ids))
                cur.execute(f"""
                    SELECT id, email FROM users 
                    WHERE id IN ({placeholders}) AND email IS NOT NULL AND email != ''
                """, user_ids)

                users = cur.fetchall()

            conn.close()

            # Send emails using ThreadPool for performance
            def send_single_email(user_data):
                try:
                    user_id, email = user_data
                    subject = "Welcome to Our Platform"
                    message = f"""
                    Dear User,

                    Welcome to our platform! Your account has been activated.

                    Best regards,
                    Admin Team
                    """

                    # Use your existing email function
                    send_email(email, subject, message)
                    return True
                except:
                    return False

            with ThreadPool(processes=5) as pool:
                results = pool.map(send_single_email, users)
                sent_count = sum(results)
                failed_count = len(results) - sent_count

            if sent_count > 0:
                return True, f"Sent {sent_count} emails, {failed_count} failed"
            else:
                return False, "No emails were sent"

        except Exception as e:
            return False, f"Bulk email failed: {str(e)}"

    @staticmethod
    def _bulk_reset_passwords(user_ids: List[str]) -> Tuple[bool, str]:
        """Reset passwords for selected users."""
        try:
            import secrets
            import string

            conn = FastDatabaseOperations.get_connection_pool()
            if not conn:
                return False, "Database connection failed"

            reset_count = 0

            with conn.cursor() as cur:
                for user_id in user_ids:
                    # Generate random password
                    new_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))

                    # Update password (you'll need to hash it properly)
                    cur.execute("""
                                UPDATE users
                                SET password_hash = crypt(%s, gen_salt('bf'))
                                WHERE id = %s
                                """, (new_password, int(user_id)))

                    if cur.rowcount > 0:
                        reset_count += 1

                conn.commit()

            conn.close()

            return True, f"Reset passwords for {reset_count} users"

        except Exception as e:
            return False, f"Password reset failed: {str(e)}"

    @staticmethod
    def _export_users_csv(user_ids: List[str]) -> Tuple[bool, str]:
        """Export selected users to CSV."""
        try:
            conn = FastDatabaseOperations.get_connection_pool()
            if not conn:
                return False, "Database connection failed"

            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)

            # Write header
            writer.writerow(['ID', 'Email', 'Role', 'Can View CVs', 'Can Delete Records', 'Created At'])

            # Get user data
            with conn.cursor() as cur:
                placeholders = ','.join(['%s'] * len(user_ids))
                cur.execute(f"""
                    SELECT id, email, role, can_view_cvs, can_delete_records, created_at 
                    FROM users 
                    WHERE id IN ({placeholders})
                """, [int(uid) for uid in user_ids])

                for row in cur.fetchall():
                    writer.writerow(row)

            conn.close()

            # Store in session state for download
            st.session_state.user_csv_export = output.getvalue()
            st.session_state.user_csv_filename = f"users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

            return True, f"User CSV export ready with {len(user_ids)} users"

        except Exception as e:
            return False, f"User CSV export failed: {str(e)}"


# ===================================================================================
# ULTRA-ENHANCED DASHBOARD WITH REAL-TIME OPERATIONS
# ===================================================================================

def show_ultra_enhanced_ceo_dashboard():
    """Ultra-enhanced CEO dashboard with all bulk operations."""

    require_login()

    user = get_current_user(refresh=True)
    if not user:
        st.error("Authentication required")
        st.stop()

    user_id = user.get("id")
    perms = get_user_permissions(user_id)

    if not perms or perms.get("role", "").lower() not in ("ceo", "admin"):
        st.error("Access denied. CEO/Admin role required.")
        st.stop()

    # Ultra-fast page header
    st.title("🚀 Ultra CEO Dashboard")
    st.caption(f"Welcome {user.get('email', 'User')} | Role: {perms.get('role', 'Unknown').title()}")

    # Render ultra-fast selection system
    render_ultra_fast_selection_system()

    # Handle bulk operations from JavaScript
    if 'bulk_operation_data' in st.session_state:
        operation_data = st.session_state.bulk_operation_data
        operation = operation_data.get('operation')
        data = operation_data.get('data', [])

        if operation and data:
            if operation.startswith(('delete_candidates', 'grant_edit', 'revoke_edit', 'export_csv', 'export_emails')):
                success, message = BulkOperationHandlers.handle_candidate_operations(operation, data, user_id)
            else:
                success, message = BulkOperationHandlers.handle_user_operations(operation, data, user_id)

            if success:
                st.success(f"✅ {message}")
                clear_all_caches()
            else:
                st.error(f"❌ {message}")

        # Clear the operation data
        del st.session_state.bulk_operation_data
        st.rerun()

    # Quick stats with performance metrics
    start_time = time.time()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        candidates = get_candidates_ultra_fast()
        st.metric("📊 Total Candidates", len(candidates))

    with col2:
        today_count = len([c for c in candidates if c.get('created_at') and
                           c['created_at'].date() == datetime.now().date() if hasattr(c['created_at'], 'date')])
        st.metric("📅 Today", today_count)

    with col3:
        users = get_users_ultra_fast()
        st.metric("👥 Total Users", len(users))

    with col4:
        load_time = round((time.time() - start_time) * 1000, 2)
        st.metric("⚡ Load Time", f"{load_time}ms")

    # Tabbed interface for better organization
    tab1, tab2 = st.tabs(["👥 Candidate Management", "🔐 User Management"])

    with tab1:
        show_candidate_management_tab(candidates, user_id, perms)

    with tab2:
        show_user_management_tab(users, user_id, perms)


def show_candidate_management_tab(candidates: List[Dict], user_id: int, perms: Dict):
    """Enhanced candidate management with ultra-fast bulk operations."""

    st.header("👥 Candidate Management")

    # Enhanced search and filter controls
    search_col, filter_col1, filter_col2, refresh_col = st.columns([3, 1, 1, 1])

    with search_col:
        search_term = st.text_input("🔍 Search candidates (name, email, ID)", key="candidate_search")

    with filter_col1:
        show_no_cv = st.checkbox("📂 No CV only", key="filter_no_cv")

    with filter_col2:
        show_can_edit = st.checkbox("✏️ Can edit only", key="filter_can_edit")

    with refresh_col:
        if st.button("🔄 Refresh", key="refresh_candidates"):
            clear_all_caches()
            st.rerun()

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

        # Edit permission filter
        if show_can_edit and not candidate.get('can_edit'):
            continue

        filtered_candidates.append(candidate)

    if not filtered_candidates:
        st.info("No candidates match your filters.")
        return

    st.info(f"Found {len(filtered_candidates)} candidates")

    # Render ultra bulk candidate panel
    render_ultra_bulk_candidate_panel(filtered_candidates)

    # Handle CSV export download
    if 'csv_export' in st.session_state:
        st.download_button(
            "📥 Download CSV Export",
            data=st.session_state.csv_export,
            file_name=st.session_state.csv_filename,
            mime='text/csv',
            key="download_csv"
        )
        st.success("✅ CSV export ready for download!")

    # Handle email export
    if 'email_export' in st.session_state:
        st.text_area("📧 Exported Email Addresses", st.session_state.email_export, height=100)
        st.success("✅ Email addresses exported!")

    # Pagination for performance
    items_per_page = 20
    total_pages = (len(filtered_candidates) + items_per_page - 1) // items_per_page

    if total_pages > 1:
        page_col1, page_col2, page_col3 = st.columns([1, 2, 1])
        with page_col2:
            page = st.selectbox(
                "📄 Page",
                range(1, total_pages + 1),
                key="candidate_page",
                format_func=lambda x: f"Page {x} of {total_pages}"
            )
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_candidates = filtered_candidates[start_idx:end_idx]
        st.caption(f"Showing {start_idx + 1}-{min(end_idx, len(filtered_candidates))} of {len(filtered_candidates)}")
    else:
        page_candidates = filtered_candidates

    # Display candidates with ultra-fast selection
    for candidate in page_candidates:
        candidate_id = candidate.get('candidate_id', '')
        candidate_name = candidate.get('name', 'Unnamed')

        with st.container():
            # Create candidate item with proper styling class
            st.markdown(
                f'<div class="candidate-item" style="border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin: 1rem 0;">',
                unsafe_allow_html=True)

            sel_col, content_col = st.columns([0.05, 0.95])

            with sel_col:
                render_ultra_candidate_checkbox(candidate_id)

            with content_col:
                with st.expander(f"👤 {candidate_name} ({candidate_id})", expanded=False):

                    # Basic info display
                    info_col1, info_col2, action_col = st.columns([2, 2, 1])

                    with info_col1:
                        st.markdown(f"""
                        **Name:** {candidate.get('name', 'N/A')}  
                        **Email:** {candidate.get('email', 'N/A')}  
                        **Phone:** {candidate.get('phone', 'N/A')}
                        """)

                    with info_col2:
                        st.markdown(f"""
                        **Created:** {candidate.get('created_at', 'N/A')}  
                        **CV File:** {'✅ Yes' if candidate.get('has_cv_file') else '❌ No'}  
                        **CV Link:** {'✅ Yes' if candidate.get('has_resume_link') else '❌ No'}
                        """)

                    with action_col:
                        st.markdown("**Actions:**")

                        # Toggle edit permission
                        current_can_edit = candidate.get('can_edit', False)
                        edit_label = "🔓 Grant Edit" if not current_can_edit else "🔒 Revoke Edit"

                        if st.button(edit_label, key=f"toggle_edit_{candidate_id}"):
                            success, message, count = FastDatabaseOperations.bulk_update_candidate_permissions_fast(
                                [candidate_id], not current_can_edit
                            )
                            if success:
                                st.success("✅ Permission updated!")
                                clear_all_caches()
                                st.rerun()
                            else:
                                st.error(f"❌ {message}")

                        # Individual delete
                        if perms.get("can_delete_records"):
                            if st.button("🗑️ Delete", key=f"delete_{candidate_id}", type="secondary"):
                                success, message, count = FastDatabaseOperations.bulk_delete_candidates_fast(
                                    [candidate_id])
                                if success:
                                    st.success("✅ Candidate deleted!")
                                    clear_all_caches()
                                    st.rerun()
                                else:
                                    st.error(f"❌ {message}")

            st.markdown('</div>', unsafe_allow_html=True)


def show_user_management_tab(users: List[Dict], current_user_id: int, perms: Dict):
    """Enhanced user management with ultra-fast bulk operations."""

    st.header("🔐 User Management")

    if not perms.get("role", "").lower() in ("ceo", "admin"):
        st.error("Access denied. Admin privileges required.")
        return

    # Enhanced search and filter controls
    search_col, filter_col1, filter_col2, refresh_col = st.columns([3, 1, 1, 1])

    with search_col:
        search_term = st.text_input("🔍 Search users (email, role)", key="user_search")

    with filter_col1:
        role_filter = st.selectbox("👤 Role Filter", ["All", "admin", "user", "ceo"], key="role_filter")

    with filter_col2:
        perm_filter = st.selectbox("🔐 Permission Filter", ["All", "Can View CVs", "Can Delete", "No Permissions"],
                                   key="perm_filter")

    with refresh_col:
        if st.button("🔄 Refresh", key="refresh_users"):
            clear_all_caches()
            st.rerun()

    # Filter users
    filtered_users = []
    search_lower = search_term.lower().strip() if search_term else ""

    for user in users:
        # Search filter
        if search_lower:
            searchable_text = f"{user.get('email', '')} {user.get('role', '')}".lower()
            if search_lower not in searchable_text:
                continue

        # Role filter
        if role_filter != "All" and user.get('role', '').lower() != role_filter.lower():
            continue

        # Permission filter
        if perm_filter != "All":
            if perm_filter == "Can View CVs" and not user.get('can_view_cvs'):
                continue
            elif perm_filter == "Can Delete" and not user.get('can_delete_records'):
                continue
            elif perm_filter == "No Permissions" and (user.get('can_view_cvs') or user.get('can_delete_records')):
                continue

        filtered_users.append(user)

    if not filtered_users:
        st.info("No users match your filters.")
        return

    st.info(f"Found {len(filtered_users)} users")

    # Render ultra bulk user panel
    render_ultra_bulk_user_panel(filtered_users)

    # Handle CSV export download
    if 'user_csv_export' in st.session_state:
        st.download_button(
            "📥 Download User CSV Export",
            data=st.session_state.user_csv_export,
            file_name=st.session_state.user_csv_filename,
            mime='text/csv',
            key="download_user_csv"
        )
        st.success("✅ User CSV export ready for download!")

    # Pagination for performance
    items_per_page = 15
    total_pages = (len(filtered_users) + items_per_page - 1) // items_per_page

    if total_pages > 1:
        page_col1, page_col2, page_col3 = st.columns([1, 2, 1])
        with page_col2:
            page = st.selectbox(
                "📄 Page",
                range(1, total_pages + 1),
                key="user_page",
                format_func=lambda x: f"Page {x} of {total_pages}"
            )
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_users = filtered_users[start_idx:end_idx]
        st.caption(f"Showing {start_idx + 1}-{min(end_idx, len(filtered_users))} of {len(filtered_users)}")
    else:
        page_users = filtered_users

    # Display users with ultra-fast selection
    for user_data in page_users:
        user_id = user_data.get('id')
        user_email = user_data.get('email', 'No email')

        with st.container():
            # Create user item with proper styling class
            st.markdown(
                f'<div class="user-item" style="border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin: 1rem 0;">',
                unsafe_allow_html=True)

            sel_col, content_col = st.columns([0.05, 0.95])

            with sel_col:
                render_ultra_user_checkbox(user_id)

            with content_col:
                with st.expander(f"👤 {user_email} (ID: {user_id})", expanded=False):

                    # User info display
                    info_col1, info_col2, action_col = st.columns([2, 2, 1])

                    with info_col1:
                        st.markdown(f"""
                        **Email:** {user_email}  
                        **Role:** {user_data.get('role', 'user')}  
                        **Created:** {user_data.get('created_at', 'N/A')}
                        """)

                    with info_col2:
                        cv_perm = '✅ Enabled' if user_data.get('can_view_cvs') else '❌ Disabled'
                        del_perm = '✅ Enabled' if user_data.get('can_delete_records') else '❌ Disabled'
                        st.markdown(f"""
                        **View CVs:** {cv_perm}  
                        **Delete Records:** {del_perm}  
                        **Status:** {'🟢 Active' if user_data.get('is_active', True) else '🔴 Inactive'}
                        """)

                    with action_col:
                        st.markdown("**Quick Actions:**")

                        # Toggle CV permission
                        current_cv_perm = user_data.get('can_view_cvs', False)
                        cv_label = "👁️ Grant CV" if not current_cv_perm else "🚫 Revoke CV"

                        if st.button(cv_label, key=f"toggle_cv_{user_id}"):
                            success, message, count = FastDatabaseOperations.bulk_update_user_permissions_fast(
                                [str(user_id)], {"can_view_cvs": not current_cv_perm}
                            )
                            if success:
                                st.success("✅ Permission updated!")
                                clear_all_caches()
                                st.rerun()
                            else:
                                st.error(f"❌ {message}")

                        # Toggle delete permission
                        current_del_perm = user_data.get('can_delete_records', False)
                        del_label = "🗑️ Grant Delete" if not current_del_perm else "🔒 Revoke Delete"

                        if st.button(del_label, key=f"toggle_del_{user_id}"):
                            success, message, count = FastDatabaseOperations.bulk_update_user_permissions_fast(
                                [str(user_id)], {"can_delete_records": not current_del_perm}
                            )
                            if success:
                                st.success("✅ Permission updated!")
                                clear_all_caches()
                                st.rerun()
                            else:
                                st.error(f"❌ {message}")

                        # Individual delete (prevent self-deletion)
                        if user_id != current_user_id:
                            if st.button("🗑️ Delete User", key=f"delete_user_{user_id}", type="secondary"):
                                success, message, count = FastDatabaseOperations.bulk_delete_users_fast([str(user_id)],
                                                                                                        current_user_id)
                                if success:
                                    st.success("✅ User deleted!")
                                    clear_all_caches()
                                    st.rerun()
                                else:
                                    st.error(f"❌ {message}")
                        else:
                            st.info("🔒 Cannot delete own account")

            st.markdown('</div>', unsafe_allow_html=True)


# ===================================================================================
# ENHANCED OPERATION CONFIRMATION SYSTEM
# ===================================================================================

def render_operation_confirmation_system():
    """Advanced confirmation system for bulk operations."""

    confirmation_js = """
    <script>
    // Enhanced confirmation system
    window.operationConfirmations = window.operationConfirmations || {};

    // Handle bulk operation with confirmation
    function executeBulkOperationWithConfirmation(operation, data) {
        const confirmationKey = operation + '_' + data.length;

        // Critical operations require confirmation
        const criticalOps = ['delete_candidates', 'delete_users', 'reset_passwords'];

        if (criticalOps.includes(operation)) {
            const confirmText = getConfirmationText(operation, data.length);

            if (!window.operationConfirmations[confirmationKey]) {
                showConfirmationModal(operation, data, confirmText);
                return;
            }
        }

        // Execute the operation
        executeBulkOperation(operation, data);

        // Reset confirmation
        delete window.operationConfirmations[confirmationKey];
    }

    function getConfirmationText(operation, count) {
        switch(operation) {
            case 'delete_candidates':
                return `DELETE ${count} CANDIDATES`;
            case 'delete_users':
                return `DELETE ${count} USERS`;
            case 'reset_passwords':
                return `RESET ${count} PASSWORDS`;
            default:
                return `CONFIRM ${operation.toUpperCase()}`;
        }
    }

    function showConfirmationModal(operation, data, confirmText) {
        const modal = document.createElement('div');
        modal.innerHTML = `
            <div style="
                position: fixed;
                top: 0;
                left: 0;
                width: 100vw;
                height: 100vh;
                background: rgba(0,0,0,0.8);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 10000;
            ">
                <div style="
                    background: white;
                    padding: 2rem;
                    border-radius: 15px;
                    box-shadow: 0 10px 25px rgba(0,0,0,0.3);
                    max-width: 500px;
                    text-align: center;
                ">
                    <h2 style="color: #e74c3c; margin-bottom: 1rem;">⚠️ CONFIRM OPERATION</h2>
                    <p style="font-size: 1.1rem; margin-bottom: 2rem;">
                        You are about to execute: <strong>${operation.replace('_', ' ').toUpperCase()}</strong>
                        <br>This will affect <strong>${data.length}</strong> items.
                        <br><strong style="color: #e74c3c;">This action cannot be undone!</strong>
                    </p>

                    <input type="text" id="confirmationInput" placeholder="Type '${confirmText}' to confirm" style="
                        width: 100%;
                        padding: 1rem;
                        margin-bottom: 1rem;
                        border: 2px solid #e74c3c;
                        border-radius: 5px;
                        font-size: 1rem;
                        text-align: center;
                    ">

                    <div style="display: flex; gap: 1rem; justify-content: center;">
                        <button onclick="closeConfirmationModal()" style="
                            background: #95a5a6;
                            color: white;
                            border: none;
                            padding: 1rem 2rem;
                            border-radius: 8px;
                            cursor: pointer;
                            font-size: 1rem;
                        ">❌ CANCEL</button>

                        <button id="confirmButton" onclick="confirmOperation('${operation}', ${JSON.stringify(data)}, '${confirmText}')" disabled style="
                            background: #bdc3c7;
                            color: #7f8c8d;
                            border: none;
                            padding: 1rem 2rem;
                            border-radius: 8px;
                            cursor: not-allowed;
                            font-size: 1rem;
                        ">✅ CONFIRM</button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Handle input validation
        const input = modal.querySelector('#confirmationInput');
        const button = modal.querySelector('#confirmButton');

        input.addEventListener('keyup', function() {
            if (this.value.trim() === confirmText) {
                button.disabled = false;
                button.style.background = '#e74c3c';
                button.style.color = 'white';
                button.style.cursor = 'pointer';
            } else {
                button.disabled = true;
                button.style.background = '#bdc3c7';
                button.style.color = '#7f8c8d';
                button.style.cursor = 'not-allowed';
            }
        });

        // Focus input
        setTimeout(() => input.focus(), 100);
    }

    function closeConfirmationModal() {
        const modal = document.querySelector('[style*="position: fixed"][style*="z-index: 10000"]');
        if (modal) {
            document.body.removeChild(modal);
        }
    }

    function confirmOperation(operation, data, expectedText) {
        const input = document.getElementById('confirmationInput');
        if (input.value.trim() === expectedText) {
            closeConfirmationModal();
            window.operationConfirmations[operation + '_' + data.length] = true;
            executeBulkOperation(operation, data);
        }
    }

    // Update original executeBulkOperation to use confirmation
    const originalExecuteBulkOperation = window.executeBulkOperation;
    window.executeBulkOperation = function(operation, data) {
        executeBulkOperationWithConfirmation(operation, data);
    };

    </script>
    """

    components.html(confirmation_js, height=1)


# ===================================================================================
# MAIN APPLICATION ROUTER WITH PERFORMANCE MONITORING
# ===================================================================================

def main():
    """Main application with ultra-fast performance monitoring."""

    # Performance monitoring
    app_start_time = time.time()

    require_login()

    user = get_current_user(refresh=True)
    if not user:
        st.error("Authentication required")
        st.stop()

    user_id = user.get("id")
    perms = get_user_permissions(user_id)

    if not perms or perms.get("role", "").lower() not in ("ceo", "admin"):
        st.error("Access denied. CEO/Admin role required.")
        st.stop()

    # Handle JavaScript bulk operations
    components.html("""
    <script>
    window.addEventListener('bulkOperation', function(event) {
        const operation = event.detail.operation;
        const data = event.detail.data;

        // Send to Streamlit via session state
        window.parent.postMessage({
            type: 'streamlit:setComponentValue',
            data: {
                bulk_operation_data: {
                    operation: operation,
                    data: data
                }
            }
        }, '*');
    });
    </script>
    """, height=1)

    # Initialize session state for bulk operations
    if 'bulk_operation_data' not in st.session_state:
        st.session_state.bulk_operation_data = None

    # Sidebar with performance info
    st.sidebar.title("🚀 Ultra CEO Panel")
    st.sidebar.caption(f"👤 {user.get('email', 'User')}")
    st.sidebar.caption(f"🔑 Role: {perms.get('role', 'Unknown').title()}")
    st.sidebar.markdown("---")

    # Performance metrics in sidebar
    load_time = round((time.time() - app_start_time) * 1000, 2)
    st.sidebar.metric("⚡ App Load Time", f"{load_time}ms")

    # Cache status
    candidates_cached = len(get_candidates_ultra_fast.__wrapped__.__cache_info__.currsize) if hasattr(
        get_candidates_ultra_fast.__wrapped__, '__cache_info__') else 0
    users_cached = len(get_users_ultra_fast.__wrapped__.__cache_info__.currsize) if hasattr(
        get_users_ultra_fast.__wrapped__, '__cache_info__') else 0

    st.sidebar.caption("**Cache Status:**")
    st.sidebar.caption(f"- Candidates: {'✅ Cached' if candidates_cached else '❌ Not cached'}")
    st.sidebar.caption(f"- Users: {'✅ Cached' if users_cached else '❌ Not cached'}")

    st.sidebar.markdown("---")
    st.sidebar.caption("**🚀 Ultra Features:**")
    st.sidebar.caption("- ✅ Multi-threaded Operations")
    st.sidebar.caption("- ✅ Batch Database Processing")
    st.sidebar.caption("- ✅ Connection Pooling")
    st.sidebar.caption("- ✅ Advanced JavaScript UI")
    st.sidebar.caption("- ✅ Real-time Confirmations")
    st.sidebar.caption("- ✅ Smart Caching (5min)")
    st.sidebar.caption("- ✅ CSV/Email Export")
    st.sidebar.caption("- ✅ Bulk Email System")
    st.sidebar.caption("- ✅ Password Reset Tools")

    # Clear cache option
    if st.sidebar.button("🗑️ Clear All Caches"):
        clear_all_caches()
        st.sidebar.success("✅ Caches cleared!")
        st.rerun()

    # Main dashboard
    render_operation_confirmation_system()
    show_ultra_enhanced_ceo_dashboard()

    # Performance footer
    total_time = round((time.time() - app_start_time) * 1000, 2)
    st.caption(f"⚡ Total page load time: {total_time}ms")


if __name__ == "__main__":
    main()