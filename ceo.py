# OPTIMIZED CEO Control Panel - Enhanced Bulk Operations + Threading + Connection Pooling
# =============================================================================

from __future__ import annotations
import os
from dotenv import load_dotenv
import base64
import json
from typing import Dict, Any, List, Optional, Tuple, Iterable
from datetime import datetime
import uuid
import mimetypes
import traceback
import re
import psycopg2
from psycopg2 import pool
from smtp_mailer import send_email
import streamlit as st
import streamlit.components.v1 as components
import asyncio
import concurrent.futures
import threading
from functools import partial
import time
from queue import Queue
import logging

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

load_dotenv()
# =============================================================================
# CONNECTION POOLING FOR BETTER PERFORMANCE
# =============================================================================

@st.cache_resource
def get_connection_pool():
    """Create a connection pool for better database performance."""
    try:
        # You'll need to adjust these connection parameters based on your db_postgres settings
        return psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            host=os.getenv('PGHOST', 'localhost'),
            port=int(os.getenv('PGPORT', 5432)),
            database=os.getenv('PGDATABASE', 'railway'),
            user=os.getenv('PGUSER', 'postgres'),
            password=os.getenv('PGPASSWORD')
        )
    except Exception as e:
        st.error(f"Failed to create connection pool: {e}")
        return None


def get_pooled_connection():
    """Get a connection from the pool, fallback to regular connection."""
    try:
        pool = get_connection_pool()
        if pool:
            return pool.getconn()
    except Exception:
        pass
    return get_conn()


def return_pooled_connection(conn):
    """Return connection to pool or close it."""
    try:
        pool = get_connection_pool()
        if pool and conn:
            pool.putconn(conn)
            return
    except Exception:
        pass
    if conn:
        conn.close()


# =============================================================================
# THREADED DATABASE OPERATIONS FOR BETTER PERFORMANCE
# =============================================================================

def execute_in_thread(func, *args, **kwargs):
    """Execute database operation in thread for better performance."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future = executor.submit(func, *args, **kwargs)
        return future.result(timeout=30)  # 30 second timeout


# =============================================================================
# Performance Optimizations with Async/Threading and Better Caching
# =============================================================================

@st.cache_data(ttl=300, show_spinner=False)  # 5 minute cache for faster updates
def _get_candidates_fast():
    """Ultra-fast candidate loading with connection pooling and threading."""

    def _fetch_candidates():
        conn = None
        try:
            conn = get_pooled_connection()
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

                return candidates
        except Exception as e:
            st.error(f"Failed to load candidates: {e}")
            return []
        finally:
            if conn:
                return_pooled_connection(conn)

    try:
        return execute_in_thread(_fetch_candidates)
    except Exception as e:
        st.error(f"Threading error: {e}")
        return []


def _get_detailed_candidate_data(candidate_id: str) -> Dict[str, Any]:
    """Load detailed data for a specific candidate only when needed."""

    def _fetch_detailed():
        conn = None
        try:
            conn = get_pooled_connection()
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
                return {}
        except Exception as e:
            st.error(f"Failed to load detailed data: {e}")
            return {}
        finally:
            if conn:
                return_pooled_connection(conn)

    try:
        return execute_in_thread(_fetch_detailed)
    except Exception:
        return {}


@st.cache_data(ttl=300, show_spinner=False)
def _get_users_fast():
    """Fast user loading with threading."""

    def _fetch_users():
        try:
            return get_all_users_with_permissions()
        except Exception as e:
            st.error(f"Failed to load users: {e}")
            return []

    try:
        return execute_in_thread(_fetch_users)
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def _get_stats_fast():
    """Fast statistics loading."""

    def _fetch_stats():
        try:
            return get_candidate_statistics() or {}
        except Exception:
            return {}

    try:
        return execute_in_thread(_fetch_stats)
    except Exception:
        return {}


def _clear_all_caches():
    """Clear all caches for refresh."""
    _get_candidates_fast.clear()
    _get_stats_fast.clear()
    _get_users_fast.clear()


# =============================================================================
# ENHANCED ZERO REFRESH OPERATIONS - Complete JavaScript-based UI Management
# =============================================================================

def _render_enhanced_zero_refresh_manager():
    """Complete JavaScript-based selection management with zero refreshes and real-time feedback."""

    enhanced_js = """
    <div id="enhanced-zero-refresh-manager" style="display: none;"></div>

    <script>
    // Global selection state with persistence
    window.candidateSelections = window.candidateSelections || new Set();
    window.userSelections = window.userSelections || new Set();
    window.bulkOperationInProgress = false;

    // Enhanced update selection display with animations
    function updateSelectionDisplay() {
        const candidateCount = window.candidateSelections.size;
        const userCount = window.userSelections.size;

        // Update all selection count displays with animation
        document.querySelectorAll('.candidate-selection-count').forEach(el => {
            if (el.textContent !== candidateCount.toString()) {
                el.style.transition = 'all 0.3s ease';
                el.style.transform = 'scale(1.2)';
                el.textContent = candidateCount;
                setTimeout(() => {
                    el.style.transform = 'scale(1)';
                }, 300);
            }
        });

        document.querySelectorAll('.user-selection-count').forEach(el => {
            if (el.textContent !== userCount.toString()) {
                el.style.transition = 'all 0.3s ease';
                el.style.transform = 'scale(1.2)';
                el.textContent = userCount;
                setTimeout(() => {
                    el.style.transform = 'scale(1)';
                }, 300);
            }
        });

        // Show/hide bulk action bars with smooth transitions
        const candidateBulkBar = document.querySelector('.candidate-bulk-bar');
        const userBulkBar = document.querySelector('.user-bulk-bar');

        if (candidateBulkBar) {
            if (candidateCount > 0) {
                candidateBulkBar.style.display = 'flex';
                candidateBulkBar.style.background = `linear-gradient(90deg, #ff4444, #ff6666)`;
                candidateBulkBar.style.color = 'white';
                candidateBulkBar.style.transform = 'translateY(0)';
                candidateBulkBar.style.opacity = '1';
            } else {
                candidateBulkBar.style.transform = 'translateY(-10px)';
                candidateBulkBar.style.opacity = '0';
                setTimeout(() => {
                    if (window.candidateSelections.size === 0) {
                        candidateBulkBar.style.display = 'none';
                    }
                }, 300);
            }
        }

        if (userBulkBar) {
            if (userCount > 0) {
                userBulkBar.style.display = 'flex';
                userBulkBar.style.background = `linear-gradient(90deg, #4444ff, #6666ff)`;
                userBulkBar.style.color = 'white';
                userBulkBar.style.transform = 'translateY(0)';
                userBulkBar.style.opacity = '1';
            } else {
                userBulkBar.style.transform = 'translateY(-10px)';
                userBulkBar.style.opacity = '0';
                setTimeout(() => {
                    if (window.userSelections.size === 0) {
                        userBulkBar.style.display = 'none';
                    }
                }, 300);
            }
        }

        // Update browser title with selection count
        const originalTitle = document.title.split(' - ')[0];
        if (candidateCount > 0 || userCount > 0) {
            document.title = `${originalTitle} - ${candidateCount}C/${userCount}U selected`;
        } else {
            document.title = originalTitle;
        }

        saveSelectionState();
    }

    // Enhanced candidate selection with visual feedback
    function toggleCandidateSelection(candidateId, forceValue = null) {
        if (window.bulkOperationInProgress) return;

        const wasSelected = window.candidateSelections.has(candidateId);

        if (forceValue !== null) {
            if (forceValue) {
                window.candidateSelections.add(candidateId);
            } else {
                window.candidateSelections.delete(candidateId);
            }
        } else {
            if (wasSelected) {
                window.candidateSelections.delete(candidateId);
            } else {
                window.candidateSelections.add(candidateId);
            }
        }

        // Update checkbox state with animation
        const checkbox = document.getElementById('cb_candidate_' + candidateId);
        if (checkbox) {
            checkbox.checked = window.candidateSelections.has(candidateId);

            // Add visual feedback
            const container = checkbox.closest('.candidate-checkbox-container') || checkbox.parentElement;
            if (container) {
                container.style.transition = 'all 0.2s ease';
                if (window.candidateSelections.has(candidateId)) {
                    container.style.background = '#fff3cd';
                    container.style.borderRadius = '3px';
                } else {
                    container.style.background = 'transparent';
                }
            }
        }

        updateSelectionDisplay();

        // Show toast notification for first few selections
        if (window.candidateSelections.size <= 3) {
            showToast(
                window.candidateSelections.has(candidateId) ? 
                `✅ Candidate selected (${window.candidateSelections.size} total)` : 
                `❌ Candidate deselected (${window.candidateSelections.size} total)`
            );
        }
    }

    // Enhanced user selection with visual feedback  
    function toggleUserSelection(userId, forceValue = null) {
        if (window.bulkOperationInProgress) return;

        const wasSelected = window.userSelections.has(userId);

        if (forceValue !== null) {
            if (forceValue) {
                window.userSelections.add(userId);
            } else {
                window.userSelections.delete(userId);
            }
        } else {
            if (wasSelected) {
                window.userSelections.delete(userId);
            } else {
                window.userSelections.add(userId);
            }
        }

        // Update checkbox state with animation
        const checkbox = document.getElementById('cb_user_' + userId);
        if (checkbox) {
            checkbox.checked = window.userSelections.has(userId);

            // Add visual feedback
            const container = checkbox.closest('.user-checkbox-container') || checkbox.parentElement;
            if (container) {
                container.style.transition = 'all 0.2s ease';
                if (window.userSelections.has(userId)) {
                    container.style.background = '#e3f2fd';
                    container.style.borderRadius = '3px';
                } else {
                    container.style.background = 'transparent';
                }
            }
        }

        updateSelectionDisplay();

        // Show toast notification
        if (window.userSelections.size <= 3) {
            showToast(
                window.userSelections.has(userId) ? 
                `✅ User selected (${window.userSelections.size} total)` : 
                `❌ User deselected (${window.userSelections.size} total)`
            );
        }
    }

    // Enhanced bulk selection functions
    function selectAllCandidates(candidates) {
        if (window.bulkOperationInProgress) return;

        const previousCount = window.candidateSelections.size;
        candidates.forEach(id => window.candidateSelections.add(id));

        document.querySelectorAll('[id^="cb_candidate_"]').forEach(cb => {
            cb.checked = true;
            const container = cb.closest('.candidate-checkbox-container') || cb.parentElement;
            if (container) {
                container.style.background = '#fff3cd';
                container.style.borderRadius = '3px';
            }
        });

        updateSelectionDisplay();
        showToast(`✅ Selected ${candidates.length} candidates (${window.candidateSelections.size} total)`);
    }

    function clearAllCandidates() {
        if (window.bulkOperationInProgress) return;

        const count = window.candidateSelections.size;
        window.candidateSelections.clear();

        document.querySelectorAll('[id^="cb_candidate_"]').forEach(cb => {
            cb.checked = false;
            const container = cb.closest('.candidate-checkbox-container') || cb.parentElement;
            if (container) {
                container.style.background = 'transparent';
            }
        });

        updateSelectionDisplay();
        if (count > 0) {
            showToast(`❌ Cleared ${count} candidate selections`);
        }
    }

    function selectAllUsers(users) {
        if (window.bulkOperationInProgress) return;

        const previousCount = window.userSelections.size;
        users.forEach(id => window.userSelections.add(id));

        document.querySelectorAll('[id^="cb_user_"]').forEach(cb => {
            cb.checked = true;
            const container = cb.closest('.user-checkbox-container') || cb.parentElement;
            if (container) {
                container.style.background = '#e3f2fd';
                container.style.borderRadius = '3px';
            }
        });

        updateSelectionDisplay();
        showToast(`✅ Selected ${users.length} users (${window.userSelections.size} total)`);
    }

    function clearAllUsers() {
        if (window.bulkOperationInProgress) return;

        const count = window.userSelections.size;
        window.userSelections.clear();

        document.querySelectorAll('[id^="cb_user_"]').forEach(cb => {
            cb.checked = false;
            const container = cb.closest('.user-checkbox-container') || cb.parentElement;
            if (container) {
                container.style.background = 'transparent';
            }
        });

        updateSelectionDisplay();
        if (count > 0) {
            showToast(`❌ Cleared ${count} user selections`);
        }
    }

    // Enhanced bulk operations with progress feedback
    function executeBulkCandidateDelete() {
        const selectedIds = Array.from(window.candidateSelections);
        if (selectedIds.length === 0) return;

        window.bulkOperationInProgress = true;

        // Show loading state with progress
        const deleteBtn = document.getElementById('bulk-candidate-delete-btn');
        if (deleteBtn) {
            deleteBtn.innerHTML = '⏳ Deleting...';
            deleteBtn.disabled = true;
            deleteBtn.style.background = '#6c757d';
        }

        // Show progress toast
        showToast(`🔄 Deleting ${selectedIds.length} candidates...`, 'info', 0);

        // Send to Streamlit
        const event = new CustomEvent('bulkCandidateDelete', {
            detail: { candidateIds: selectedIds }
        });
        window.dispatchEvent(event);

        // Simulate progress for better UX
        let progress = 0;
        const progressInterval = setInterval(() => {
            progress += 10;
            if (deleteBtn) {
                deleteBtn.innerHTML = `⏳ Deleting... ${Math.min(progress, 90)}%`;
            }
            if (progress >= 100) {
                clearInterval(progressInterval);
            }
        }, 200);
    }

    function executeBulkUserDelete() {
        const selectedIds = Array.from(window.userSelections);
        if (selectedIds.length === 0) return;

        window.bulkOperationInProgress = true;

        // Show loading state
        const deleteBtn = document.getElementById('bulk-user-delete-btn');
        if (deleteBtn) {
            deleteBtn.innerHTML = '⏳ Deleting...';
            deleteBtn.disabled = true;
            deleteBtn.style.background = '#6c757d';
        }

        showToast(`🔄 Deleting ${selectedIds.length} users...`, 'info', 0);

        // Send to Streamlit
        const event = new CustomEvent('bulkUserDelete', {
            detail: { userIds: selectedIds }
        });
        window.dispatchEvent(event);
    }

    // Bulk permission operations
    function executeBulkPermissionUpdate(permission, value) {
        const selectedIds = Array.from(window.userSelections);
        if (selectedIds.length === 0) {
            showToast('❌ No users selected for permission update', 'error');
            return;
        }

        window.bulkOperationInProgress = true;

        showToast(`🔄 Updating ${permission} for ${selectedIds.length} users...`, 'info', 0);

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

    // Enhanced toast notification system
    function showToast(message, type = 'success', duration = 3000) {
        // Remove existing toasts
        const existingToasts = document.querySelectorAll('.enhanced-toast');
        existingToasts.forEach(toast => toast.remove());

        const toast = document.createElement('div');
        toast.className = 'enhanced-toast';

        const bgColor = {
            'success': '#28a745',
            'error': '#dc3545',
            'warning': '#ffc107',
            'info': '#17a2b8'
        }[type] || '#28a745';

        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${bgColor};
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 10000;
            font-weight: 500;
            max-width: 400px;
            word-wrap: break-word;
            transform: translateX(100%);
            transition: transform 0.3s ease;
        `;

        toast.textContent = message;
        document.body.appendChild(toast);

        // Animate in
        setTimeout(() => {
            toast.style.transform = 'translateX(0)';
        }, 10);

        // Auto remove
        if (duration > 0) {
            setTimeout(() => {
                toast.style.transform = 'translateX(100%)';
                setTimeout(() => {
                    if (toast.parentElement) {
                        toast.remove();
                    }
                }, 300);
            }, duration);
        }
    }

    // Enhanced state persistence
    function saveSelectionState() {
        try {
            localStorage.setItem('candidateSelections', JSON.stringify(Array.from(window.candidateSelections)));
            localStorage.setItem('userSelections', JSON.stringify(Array.from(window.userSelections)));
            localStorage.setItem('selectionTimestamp', Date.now().toString());
        } catch (e) {
            console.warn('Failed to save selection state:', e);
        }
    }

    function loadSelectionState() {
        try {
            const timestamp = localStorage.getItem('selectionTimestamp');
            const now = Date.now();

            // Clear selections older than 1 hour
            if (!timestamp || (now - parseInt(timestamp)) > 3600000) {
                localStorage.removeItem('candidateSelections');
                localStorage.removeItem('userSelections');
                return;
            }

            const candidateSelections = JSON.parse(localStorage.getItem('candidateSelections') || '[]');
            const userSelections = JSON.parse(localStorage.getItem('userSelections') || '[]');

            window.candidateSelections = new Set(candidateSelections);
            window.userSelections = new Set(userSelections);

            // Update UI
            candidateSelections.forEach(id => {
                const checkbox = document.getElementById('cb_candidate_' + id);
                if (checkbox) {
                    checkbox.checked = true;
                    const container = checkbox.closest('.candidate-checkbox-container') || checkbox.parentElement;
                    if (container) {
                        container.style.background = '#fff3cd';
                        container.style.borderRadius = '3px';
                    }
                }
            });

            userSelections.forEach(id => {
                const checkbox = document.getElementById('cb_user_' + id);
                if (checkbox) {
                    checkbox.checked = true;
                    const container = checkbox.closest('.user-checkbox-container') || checkbox.parentElement;
                    if (container) {
                        container.style.background = '#e3f2fd';
                        container.style.borderRadius = '3px';
                    }
                }
            });

            updateSelectionDisplay();

            if (candidateSelections.length > 0 || userSelections.length > 0) {
                showToast(`🔄 Restored ${candidateSelections.length} candidates and ${userSelections.length} users from previous session`);
            }
        } catch (e) {
            console.warn('Failed to load selection state:', e);
        }
    }

    // Reset bulk operation state
    function resetBulkOperationState() {
        window.bulkOperationInProgress = false;

        // Reset button states
        const candidateDeleteBtn = document.getElementById('bulk-candidate-delete-btn');
        if (candidateDeleteBtn) {
            candidateDeleteBtn.innerHTML = '🗑️ DELETE ALL';
            candidateDeleteBtn.disabled = false;
            candidateDeleteBtn.style.background = '#dc3545';
        }

        const userDeleteBtn = document.getElementById('bulk-user-delete-btn');
        if (userDeleteBtn) {
            userDeleteBtn.innerHTML = '🗑️ DELETE ALL';
            userDeleteBtn.disabled = false;
            userDeleteBtn.style.background = '#dc3545';
        }
    }

    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.key === 'a' && e.target.tagName !== 'INPUT') {
            e.preventDefault();
            const candidateIds = Array.from(document.querySelectorAll('[id^="cb_candidate_"]')).map(cb => cb.id.replace('cb_candidate_', ''));
            if (candidateIds.length > 0) {
                selectAllCandidates(candidateIds);
            }
        }

        if (e.key === 'Escape') {
            clearAllCandidates();
            clearAllUsers();
        }
    });

    // Initialize on page load
    document.addEventListener('DOMContentLoaded', function() {
        setTimeout(() => {
            loadSelectionState();
            updateSelectionDisplay();
        }, 100);
    });

    // Handle Streamlit component communication
    window.addEventListener('streamlit:componentReady', function() {
        setTimeout(() => {
            loadSelectionState();
            updateSelectionDisplay();
        }, 100);
    });

    // Periodic state save
    setInterval(saveSelectionState, 5000);

    </script>
    """

    components.html(enhanced_js, height=1)


def _render_enhanced_candidate_checkbox(candidate_id: str) -> None:
    """Render enhanced candidate checkbox with zero refresh and visual feedback."""

    checkbox_html = f"""
    <div class="candidate-checkbox-container" style="
        padding: 4px;
        transition: all 0.2s ease;
        border-radius: 3px;
    ">
        <input 
            type="checkbox" 
            id="cb_candidate_{candidate_id}" 
            onchange="toggleCandidateSelection('{candidate_id}')"
            style="
                width: 20px; 
                height: 20px; 
                cursor: pointer;
                accent-color: #ff4444;
                transform: scale(1.3);
                transition: all 0.1s ease;
            "
            onmouseover="this.style.transform='scale(1.4)'"
            onmouseout="this.style.transform='scale(1.3)'"
        />
    </div>
    """

    components.html(checkbox_html, height=30)


def _render_enhanced_user_checkbox(user_id: int) -> None:
    """Render enhanced user checkbox with zero refresh and visual feedback."""

    checkbox_html = f"""
    <div class="user-checkbox-container" style="
        padding: 4px;
        transition: all 0.2s ease;
        border-radius: 3px;
    ">
        <input 
            type="checkbox" 
            id="cb_user_{user_id}" 
            onchange="toggleUserSelection('{user_id}')"
            style="
                width: 20px; 
                height: 20px; 
                cursor: pointer;
                accent-color: #4444ff;
                transform: scale(1.3);
                transition: all 0.1s ease;
            "
            onmouseover="this.style.transform='scale(1.4)'"
            onmouseout="this.style.transform='scale(1.3)'"
        />
    </div>
    """

    components.html(checkbox_html, height=30)


def _render_enhanced_bulk_candidate_controls(candidates: List[Dict], perms: Dict[str, Any]):
    """Render enhanced bulk candidate controls with complete operations."""

    if not perms.get("can_delete_records"):
        return

    candidate_ids = [c.get('candidate_id', '') for c in candidates if c.get('candidate_id')]
    candidate_ids_js = json.dumps(candidate_ids)

    bulk_controls_html = f"""
    <!-- Enhanced bulk candidate action bar -->
    <div class="candidate-bulk-bar" style="
        background: linear-gradient(90deg, #f8f9fa, #e9ecef);
        color: #495057;
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1.5rem 0;
        box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
        display: none;
        justify-content: space-between;
        align-items: center;
        transition: all 0.3s ease;
        transform: translateY(-10px);
        opacity: 0;
        border-left: 5px solid #ff4444;
    ">
        <div style="display: flex; align-items: center; gap: 1rem;">
            <div style="
                background: #ff4444;
                color: white;
                width: 50px;
                height: 50px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 1.5rem;
            ">🗑️</div>
            <div>
                <h3 style="margin: 0; color: #ff4444;">
                    <span class="candidate-selection-count">0</span> Candidates Selected
                </h3>
                <p style="margin: 0; color: #6c757d; font-size: 0.9rem;">Ready for bulk operations</p>
            </div>
        </div>
        <div style="display: flex; gap: 1rem; align-items: center; flex-wrap: wrap;">
            <button onclick="showCandidateDeleteConfirmation()" style="
                background: linear-gradient(135deg, #ff4444, #cc0000);
                color: white;
                border: none;
                padding: 1rem 2rem;
                border-radius: 30px;
                cursor: pointer;
                font-weight: bold;
                font-size: 1.1rem;
                transition: all 0.2s ease;
                box-shadow: 0 4px 8px rgba(255, 68, 68, 0.3);
            " onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 6px 12px rgba(255, 68, 68, 0.4)'" 
               onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 8px rgba(255, 68, 68, 0.3)'">
                🗑️ DELETE SELECTED
            </button>

            <button onclick="executeBulkCandidatePermissionUpdate('can_edit', true)" style="
                background: linear-gradient(135deg, #28a745, #20c997);
                color: white;
                border: none;
                padding: 0.8rem 1.5rem;
                border-radius: 25px;
                cursor: pointer;
                font-weight: 600;
                transition: all 0.2s ease;
            " onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform='translateY(0)'">
                ✅ GRANT EDIT
            </button>

            <button onclick="executeBulkCandidatePermissionUpdate('can_edit', false)" style="
                background: linear-gradient(135deg, #ffc107, #e0a800);
                color: black;
                border: none;
                padding: 0.8rem 1.5rem;
                border-radius: 25px;
                cursor: pointer;
                font-weight: 600;
                transition: all 0.2s ease;
            " onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform='translateY(0)'">
                🔒 REVOKE EDIT
            </button>

            <button onclick="clearAllCandidates()" style="
                background: linear-gradient(135deg, #6c757d, #495057);
                color: white;
                border: none;
                padding: 0.8rem 1.5rem;
                border-radius: 25px;
                cursor: pointer;
                font-weight: 600;
                transition: all 0.2s ease;
            " onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform='translateY(0)'">
                ❌ CLEAR ALL
            </button>
        </div>
    </div>

    <!-- Enhanced bulk action quick buttons -->
    <div style="
        margin: 1.5rem 0; 
        display: flex; 
        gap: 1rem; 
        flex-wrap: wrap; 
        align-items: center;
        padding: 1rem;
        background: linear-gradient(135deg, #f8f9fa, #ffffff);
        border-radius: 10px;
        border: 1px solid #dee2e6;
    ">
        <button onclick="selectAllCandidates({candidate_ids_js})" style="
            background: linear-gradient(135deg, #28a745, #20c997);
            color: white;
            border: none;
            padding: 0.7rem 1.2rem;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.95rem;
            font-weight: 600;
            transition: all 0.2s ease;
            box-shadow: 0 2px 4px rgba(40, 167, 69, 0.3);
        " onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
            ☑️ SELECT ALL VISIBLE ({len(candidates)})
        </button>

        <button onclick="clearAllCandidates()" style="
            background: linear-gradient(135deg, #dc3545, #c82333);
            color: white;
            border: none;
            padding: 0.7rem 1.2rem;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.95rem;
            font-weight: 600;
            transition: all 0.2s ease;
            box-shadow: 0 2px 4px rgba(220, 53, 69, 0.3);
        " onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
            ❌ CLEAR ALL
        </button>

        <span style="
            background: linear-gradient(135deg, #fff3cd, #ffeaa7);
            padding: 0.7rem 1.2rem;
            border-radius: 8px;
            border: 1px solid #ffc107;
            font-size: 0.95rem;
            font-weight: 600;
            color: #856404;
            box-shadow: 0 2px 4px rgba(255, 193, 7, 0.2);
        ">📊 <span class="candidate-selection-count">0</span> selected</span>

        <div style="margin-left: auto; font-size: 0.85rem; color: #6c757d;">
            💡 <strong>Tip:</strong> Use Ctrl+A to select all, Esc to clear
        </div>
    </div>

    <!-- Enhanced zero-refresh confirmation dialog -->
    <div class="candidate-delete-confirmation" style="
        display: none;
        background: linear-gradient(135deg, #ffebee, #ffcdd2);
        border: 3px solid #f44336;
        border-radius: 15px;
        padding: 2.5rem;
        margin: 2rem 0;
        text-align: center;
        box-shadow: 0 10px 20px rgba(244, 67, 54, 0.2);
        position: relative;
        overflow: hidden;
    ">
        <!-- Animated background -->
        <div style="
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(45deg, transparent, rgba(244, 67, 54, 0.1), transparent);
            animation: shimmer 3s infinite;
        "></div>

        <div style="position: relative; z-index: 1;">
            <div style="font-size: 3rem; margin-bottom: 1rem;">⚠️</div>
            <h2 style="color: #c62828; margin: 1rem 0; font-size: 1.8rem;">
                CONFIRM BULK DELETE
            </h2>
            <div style="
                background: rgba(244, 67, 54, 0.1);
                padding: 1.5rem;
                border-radius: 10px;
                margin: 2rem 0;
                border-left: 5px solid #f44336;
            ">
                <p style="font-size: 1.2rem; color: #d32f2f; margin: 0;">
                    You are about to permanently delete <strong><span class="candidate-selection-count">0</span> candidates</strong>.
                    <br><strong style="color: #b71c1c;">This action cannot be undone!</strong>
                </p>
            </div>

            <div style="margin: 2rem 0;">
                <input type="text" id="candidate-delete-confirmation-input" 
                    placeholder="Type 'DELETE CANDIDATES' to confirm" 
                    style="
                        padding: 1.2rem;
                        font-size: 1.1rem;
                        border: 3px solid #f44336;
                        border-radius: 8px;
                        width: 350px;
                        text-align: center;
                        font-weight: 600;
                        transition: all 0.2s ease;
                    " 
                    onkeyup="checkCandidateDeleteConfirmation()"
                    onfocus="this.style.borderColor='#d32f2f'; this.style.boxShadow='0 0 0 3px rgba(244, 67, 54, 0.1)'"
                    onblur="this.style.borderColor='#f44336'; this.style.boxShadow='none'"
                />
            </div>

            <div style="display: flex; gap: 1.5rem; justify-content: center;">
                <button onclick="hideCandidateDeleteConfirmation()" style="
                    background: linear-gradient(135deg, #6c757d, #495057);
                    color: white;
                    border: none;
                    padding: 1.2rem 2.5rem;
                    border-radius: 8px;
                    cursor: pointer;
                    font-size: 1.1rem;
                    font-weight: 600;
                    transition: all 0.2s ease;
                " onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform='translateY(0)'">
                    ❌ CANCEL
                </button>

                <button id="bulk-candidate-delete-btn" onclick="executeBulkCandidateDelete()" disabled style="
                    background: #ccc;
                    color: #666;
                    border: none;
                    padding: 1.2rem 2.5rem;
                    border-radius: 8px;
                    cursor: not-allowed;
                    font-size: 1.1rem;
                    font-weight: 600;
                    transition: all 0.2s ease;
                ">🗑️ DELETE ALL</button>
            </div>
        </div>
    </div>

    <style>
    @keyframes shimmer {{
        0%% {{ transform: translateX(-100%%); }}
        100%% {{ transform: translateX(100%%); }}
    }}
    </style>

    <script>
    function checkCandidateDeleteConfirmation() {
        const input =
    document.getElementById('candidate-delete-confirmation-input');
    const
    button = document.getElementById('bulk-candidate-delete-btn');

    if (input.value.trim() === 'DELETE CANDIDATES') {
    button.disabled = false;
    button.style.background = 'linear-gradient(135deg, #dc3545, #c82333)';
    button.style.color = 'white';
    button.style.cursor = 'pointer';
    button.style.boxShadow = '0 4px 8px rgba(220, 53, 69, 0.3)';
    } else {
    button.disabled = true;
    button.style.background = '#ccc';
    button.style.color = '#666';
    button.style.cursor = 'not-allowed';
    button.style.boxShadow = 'none';
    } }

    function showCandidateDeleteConfirmation() {
    const dialog = document.querySelector('.candidate-delete-confirmation');
    if (dialog) {
    dialog.style.display = 'block';
    dialog.style.opacity = '0';
    dialog.style.transform = 'scale(0.9)';
    setTimeout(() = > {
    dialog.style.transition = 'all 0.3s ease';
    dialog.style.opacity = '1';
    dialog.style.transform = 'scale(1)';
    }, 10);
    } }

    function hideCandidateDeleteConfirmation() {
    const dialog = document.querySelector('.candidate-delete-confirmation');
    if (dialog) {
    dialog.style.opacity = '0';
    dialog.style.transform = 'scale(0.9)';
    setTimeout(() = > {
    dialog.style.display = 'none';
    }, 300);
    }

    const input = document.getElementById('candidate-delete-confirmation-input');
    if (input) input.value = '';
    checkCandidateDeleteConfirmation();
    }

    function executeBulkCandidatePermissionUpdate(permission, value) {
    const selectedIds = Array.from (window.candidateSelections);
    if (selectedIds.length == = 0) {
    showToast('❌ No candidates selected for permission update', 'error');
    return;
    }

    showToast(`🔄 Updating ${permission}
    for ${selectedIds.length} candidates...`, 'info', 0);

    // Send to Streamlit
    const event = new CustomEvent('bulkCandidatePermissionUpdate', {
    detail: {
        candidateIds: selectedIds,
        permission: permission,
        value: value
    }
    });
    window.dispatchEvent(event);
    }
    < / script >
        """
  
      components.html(bulk_controls_html, height=1)
  
  def _render_enhanced_bulk_user_controls(users: List[Dict], perms: Dict[str, Any]):
      """
    Render
    enhanced
    bulk
    user
    controls
    with complete operations."""

    if not perms.get("can_manage_users"):
        return

    user_ids = [str(u.get('id', '')) for u in users if u.get('id')]
    user_ids_js = json.dumps(user_ids)

    bulk_user_controls_html = f"""
    < !-- Enhanced bulk user action bar -->
    < div

    class ="user-bulk-bar" style="


background: linear - gradient(90
deg,  # f8f9fa, #e9ecef);
color:  # 495057;
padding: 1.5
rem;
border - radius: 15
px;
margin: 1.5
rem
0;
box - shadow: 0
8
px
16
px
rgba(0, 0, 0, 0.1);
display: none;
justify - content: space - between;
align - items: center;
transition: all
0.3
s
ease;
transform: translateY(-10
px);
opacity: 0;
border - left: 5
px
solid  # 4444ff;
">
< div
style = "display: flex; align-items: center; gap: 1rem;" >
        < div
style = "
background:  # 4444ff;
color: white;
width: 50
px;
height: 50
px;
border - radius: 50 %;
display: flex;
align - items: center;
justify - content: center;
font - size: 1.5
rem;
">👥</div>
< div >
< h3
style = "margin: 0; color: #4444ff;" >
        < span


class ="user-selection-count" > 0 < / span > Users Selected

< / h3 >
< p
style = "margin: 0; color: #6c757d; font-size: 0.9rem;" > Ready
for bulk user operations < / p >
< / div >
< / div >
< div
style = "display: flex; gap: 1rem; align-items: center; flex-wrap: wrap;" >
< button
onclick = "executeBulkPermissionUpdate('can_view_cvs', true)"
style = "
background: linear - gradient(135
deg,  # 28a745, #20c997);
color: white;
border: none;
padding: 0.8
rem
1.5
rem;
border - radius: 25
px;
cursor: pointer;
font - weight: 600;
font - size: 0.95
rem;
transition: all
0.2
s
ease;
" onmouseover="
this.style.transform = 'translateY(-2px)'" onmouseout="
this.style.transform = 'translateY(0)'">
✅ GRANT
CV
VIEW
< / button >

    < button
onclick = "executeBulkPermissionUpdate('can_delete_records', true)"
style = "
background: linear - gradient(135
deg,  # ffc107, #e0a800);
color: black;
border: none;
padding: 0.8
rem
1.5
rem;
border - radius: 25
px;
cursor: pointer;
font - weight: 600;
font - size: 0.95
rem;
transition: all
0.2
s
ease;
" onmouseover="
this.style.transform = 'translateY(-2px)'" onmouseout="
this.style.transform = 'translateY(0)'">
🗑️
GRANT
DELETE
< / button >

    < button
onclick = "executeBulkPermissionUpdate('can_view_cvs', false)"
style = "
background: linear - gradient(135
deg,  # fd7e14, #e55a00);
color: white;
border: none;
padding: 0.8
rem
1.5
rem;
border - radius: 25
px;
cursor: pointer;
font - weight: 600;
font - size: 0.95
rem;
transition: all
0.2
s
ease;
" onmouseover="
this.style.transform = 'translateY(-2px)'" onmouseout="
this.style.transform = 'translateY(0)'">
❌ REVOKE
CV
VIEW
< / button >

    < button
onclick = "showUserDeleteConfirmation()"
style = "
background: linear - gradient(135
deg,  # dc3545, #c82333);
color: white;
border: none;
padding: 1
rem
2
rem;
border - radius: 30
px;
cursor: pointer;
font - weight: bold;
font - size: 1.1
rem;
transition: all
0.2
s
ease;
box - shadow: 0
4
px
8
px
rgba(220, 53, 69, 0.3);
" onmouseover="
this.style.transform = 'translateY(-2px)';
this.style.boxShadow = '0 6px 12px rgba(220, 53, 69, 0.4)'"
onmouseout = "this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 8px rgba(220, 53, 69, 0.3)'" >
🗑️
DELETE
USERS
< / button >

    < button
onclick = "clearAllUsers()"
style = "
background: linear - gradient(135
deg,  # 6c757d, #495057);
color: white;
border: none;
padding: 0.8
rem
1.5
rem;
border - radius: 25
px;
cursor: pointer;
font - weight: 600;
transition: all
0.2
s
ease;
" onmouseover="
this.style.transform = 'translateY(-2px)'" onmouseout="
this.style.transform = 'translateY(0)'">
❌ CLEAR
  < / button >
      < / div >
          < / div >

              <!-- Enhanced
bulk
user
action
quick
buttons -->
< div
style = "
margin: 1.5
rem
0;
display: flex;
gap: 1
rem;
flex - wrap: wrap;
align - items: center;
padding: 1
rem;
background: linear - gradient(135
deg,  # e3f2fd, #ffffff);
border - radius: 10
px;
border: 1
px
solid  # 2196f3;
">
< button
onclick = "selectAllUsers({user_ids_js})"
style = "
background: linear - gradient(135
deg,  # 007bff, #0056b3);
color: white;
border: none;
padding: 0.7
rem
1.2
rem;
border - radius: 8
px;
cursor: pointer;
font - size: 0.95
rem;
font - weight: 600;
transition: all
0.2
s
ease;
box - shadow: 0
2
px
4
px
rgba(0, 123, 255, 0.3);
" onmouseover="
this.style.transform = 'scale(1.05)'" onmouseout="
this.style.transform = 'scale(1)'">
☑️
SELECT
ALL
USERS({len(users)})
< / button >

    < button
onclick = "clearAllUsers()"
style = "
background: linear - gradient(135
deg,  # 6c757d, #495057);
color: white;
border: none;
padding: 0.7
rem
1.2
rem;
border - radius: 8
px;
cursor: pointer;
font - size: 0.95
rem;
font - weight: 600;
transition: all
0.2
s
ease;
box - shadow: 0
2
px
4
px
rgba(108, 117, 125, 0.3);
" onmouseover="
this.style.transform = 'scale(1.05)'" onmouseout="
this.style.transform = 'scale(1)'">
❌ CLEAR
ALL
< / button >

    < span
style = "
background: linear - gradient(135
deg,  # e3f2fd, #bbdefb);
padding: 0.7
rem
1.2
rem;
border - radius: 8
px;
border: 1
px
solid  # 2196f3;
font - size: 0.95
rem;
font - weight: 600;
color:  # 1565c0;
box - shadow: 0
2
px
4
px
rgba(33, 150, 243, 0.2);
">👥 <span class="
user - selection - count
">0</span> selected</span>

< div
style = "margin-left: auto; font-size: 0.85rem; color: #6c757d;" >
💡 < strong > Tip: < / strong > Select
users
for bulk permission updates
< / div >
< / div >

< !-- Enhanced zero-refresh user delete confirmation dialog -->
< div


class ="user-delete-confirmation" style="


display: none;
background: linear - gradient(135
deg,  # e8f4fd, #bbdefb);
border: 3
px
solid  # 2196f3;
border - radius: 15
px;
padding: 2.5
rem;
margin: 2
rem
0;
text - align: center;
box - shadow: 0
10
px
20
px
rgba(33, 150, 243, 0.2);
position: relative;
overflow: hidden;
">
<!-- Animated
background -->
< div
style = "
position: absolute;
top: 0;
left: 0;
right: 0;
bottom: 0;
background: linear - gradient(45
deg, transparent, rgba(33, 150, 243, 0.1), transparent);
animation: shimmer
3
s
infinite;
"></div>

< div
style = "position: relative; z-index: 1;" >
        < div
style = "font-size: 3rem; margin-bottom: 1rem;" >⚠️ < / div >
                                                        < h2
style = "color: #1976d2; margin: 1rem 0; font-size: 1.8rem;" >
        CONFIRM
BULK
USER
DELETE
< / h2 >
    < div
style = "
background: rgba(33, 150, 243, 0.1);
padding: 1.5
rem;
border - radius: 10
px;
margin: 2
rem
0;
border - left: 5
px
solid  # 2196f3;
">
< p
style = "font-size: 1.2rem; color: #1565c0; margin: 0;" >
        You
are
about
to
permanently
delete < strong > < span


class ="user-selection-count" > 0 < / span > users < / strong >.

< br > < strong
style = "color: #0d47a1;" > This
will
remove
their
access
completely! < / strong >
< / p >
< / div >

< div
style = "margin: 2rem 0;" >
< input
type = "text"
id = "user-delete-confirmation-input"
placeholder = "Type 'DELETE USERS' to confirm"
style = "
padding: 1.2
rem;
font - size: 1.1
rem;
border: 3
px
solid  # 2196f3;
border - radius: 8
px;
width: 350
px;
text - align: center;
font - weight: 600;
transition: all
0.2
s
ease;
"
onkeyup = "checkUserDeleteConfirmation()"
onfocus = "this.style.borderColor='#1976d2'; this.style.boxShadow='0 0 0 3px rgba(33, 150, 243, 0.1)'"
onblur = "this.style.borderColor='#2196f3'; this.style.boxShadow='none'"
/ >
< / div >

< div
style = "display: flex; gap: 1.5rem; justify-content: center;" >
< button
onclick = "hideUserDeleteConfirmation()"
style = "
background: linear - gradient(135
deg,  # 6c757d, #495057);
color: white;
border: none;
padding: 1.2
rem
2.5
rem;
border - radius: 8
px;
cursor: pointer;
font - size: 1.1
rem;
font - weight: 600;
transition: all
0.2
s
ease;
" onmouseover="
this.style.transform = 'translateY(-2px)'" onmouseout="
this.style.transform = 'translateY(0)'">
❌ CANCEL
  < / button >

      < button
id = "bulk-user-delete-btn"
onclick = "executeBulkUserDelete()"
disabled
style = "
background:  # ccc;
color:  # 666;
border: none;
padding: 1.2
rem
2.5
rem;
border - radius: 8
px;
cursor: not -allowed;
font - size: 1.1
rem;
font - weight: 600;
transition: all
0.2
s
ease;
">🗑️ DELETE ALL</button>
< / div >
    < / div >
        < / div >

            < script >
            function
checkUserDeleteConfirmation()
{
    const
input = document.getElementById('user-delete-confirmation-input');
const
button = document.getElementById('bulk-user-delete-btn');

if (input.value.trim() === 'DELETE USERS')
{
    button.disabled = false;
button.style.background = 'linear-gradient(135deg, #dc3545, #c82333)';
button.style.color = 'white';
button.style.cursor = 'pointer';
button.style.boxShadow = '0 4px 8px rgba(220, 53, 69, 0.3)';
} else {
    button.disabled = true;
button.style.background = '#ccc';
button.style.color = '#666';
button.style.cursor = 'not-allowed';
button.style.boxShadow = 'none';
}
}

function
showUserDeleteConfirmation()
{
    const
dialog = document.querySelector('.user-delete-confirmation');
if (dialog)
{
    dialog.style.display = 'block';
dialog.style.opacity = '0';
dialog.style.transform = 'scale(0.9)';
setTimeout(() = > {
    dialog.style.transition = 'all 0.3s ease';
dialog.style.opacity = '1';
dialog.style.transform = 'scale(1)';
}, 10);
}
}

function
hideUserDeleteConfirmation()
{
    const
dialog = document.querySelector('.user-delete-confirmation');
if (dialog)
{
    dialog.style.opacity = '0';
dialog.style.transform = 'scale(0.9)';
setTimeout(() = > {
    dialog.style.display = 'none';
}, 300);
}

const
input = document.getElementById('user-delete-confirmation-input');
if (input)
input.value = '';
checkUserDeleteConfirmation();
}
< / script >
    """

  components.html(bulk_user_controls_html, height=1)

# =============================================================================
# Access Rights Check - Strict Permission Enforcement
# =============================================================================

def _check_user_permissions(user_id: int) -> Dict[str, Any]:
  """
Check
user
permissions
with STRICT enforcement and caching."""
    cache_key = f"user_perms_{user_id}"

    # Check if we have cached permissions (cache for 5 minutes)
    if hasattr(st.session_state, cache_key):
        cached_data, cached_time = st.session_state[cache_key]
        if time.time() - cached_time < 300:  # 5 minutes
            return cached_data

    try:
        def _fetch_permissions():
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

        result = execute_in_thread(_fetch_permissions)

        # Cache the result
        st.session_state[cache_key] = (result, time.time())
        return result

    except Exception as e:
        st.error(f"Permission check failed: {e}")
        return {"role": "user", "can_view_cvs": False, "can_delete_records": False, "can_manage_users": False}

# =============================================================================
# CV Access with Proper Rights Check
# =============================================================================

def _get_cv_with_proper_access(candidate_id: str, user_id: int) -> Tuple[Optional[bytes], Optional[str], str]:
    """Get CV with proper access control and threading."""
    def _fetch_cv():
        try:
            perms = _check_user_permissions(user_id)
            if not perms.get("can_view_cvs", False):
                return None, None, "no_permission"

            conn = get_pooled_connection()
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
return_pooled_connection(conn)

except Exception as e:
st.error(f"CV fetch error: {e}")
return None, None, "error"

try:
return execute_in_thread(_fetch_cv)
except Exception:
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
    """Get comprehensive interview history with proper formatting and threading."""
    def _fetch_history():
        history = []
        conn = None
        try:
            conn = get_pooled_connection()
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

except Exception as e:
st.error(f"Error connecting to database for history: {e}")
finally:
if conn:
return_pooled_connection(conn)

# Sort by created_at desc
history.sort(key=lambda x: x.get('created_at') or datetime.min, reverse=True)
return history

try:
return execute_in_thread(_fetch_history)
except Exception:
return []

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
< iframe
src="data:application/pdf;base64,{b64}"
width="100%"
height="500px"
style="border: 1px solid #ddd; border-radius: 5px;" >
< / iframe >
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
< iframe
src="{embed_url}"
width="100%"
height="500px"
style="border: 1px solid #ddd; border-radius: 5px;" >
< / iframe >
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
# ENHANCED BULK OPERATIONS Backend with Threading
# =============================================================================

def _handle_bulk_candidate_delete(candidate_ids: List[str], user_id: int) -> bool:
"""Handle bulk candidate deletion with proper error handling and threading."""
    def _bulk_delete():
        try:
            perms = _check_user_permissions(user_id)
            if not perms.get("can_delete_records", False):
                return False, "Access Denied: You need 'Delete Records' permission"

            # Call the delete function from db_postgres with list
            success, reason = delete_candidate(candidate_ids, user_id)
            return success, reason
        except Exception as e:
            return False, f"Delete error: {e}"

    try:
        success, reason = execute_in_thread(_bulk_delete)

        if success:
            st.success(f"✅ Successfully deleted {len(candidate_ids)} candidates!")
            _clear_all_caches()
            return True
        else:
            st.error(f"❌ Bulk delete failed: {reason}")
            return False

    except Exception as e:
        st.error(f"❌ Bulk delete error: {e}")
        return False

def _handle_bulk_user_delete(user_ids: List[str], current_user_id: int) -> bool:
    """Handle bulk user deletion with proper error handling and threading."""
    def _bulk_user_delete():
        try:
            perms = _check_user_permissions(current_user_id)
            if not perms.get("can_manage_users", False):
                return False, "Access Denied: You need 'Manage Users' permission"

            # Prevent self-deletion
            if str(current_user_id) in user_ids:
                return False, "Cannot delete your own account!"

            success_count = 0
            failed_count = 0

            conn = get_pooled_connection()
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
                            failed_count += 1

                    conn.commit()
                    return success_count, failed_count

            finally:
                return_pooled_connection(conn)

        except Exception as e:
            return False, f"Bulk user delete error: {e}"

    try:
        result = execute_in_thread(_bulk_user_delete)

        if isinstance(result, tuple) and len(result) == 2:
            success_count, failed_count = result

            if success_count > 0:
                st.success(f"✅ Successfully deleted {success_count} users!")
                _clear_all_caches()
            if failed_count > 0:
                st.error(f"❌ Failed to delete {failed_count} users")

            return success_count > 0
        else:
            success, reason = result
            if not success:
                st.error(f"❌ {reason}")
            return success

    except Exception as e:
        st.error(f"❌ Bulk user delete error: {e}")
        return False

def _handle_bulk_permission_update(user_ids: List[str], permission: str, value: bool, current_user_id: int) -> bool:
    """Handle bulk permission updates with threading."""
    def _bulk_permission_update():
        try:
            perms = _check_user_permissions(current_user_id)
            if not perms.get("can_manage_users", False):
                return False, "Access Denied: You need 'Manage Users' permission"

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
                    failed_count += 1

            return success_count, failed_count
        except Exception as e:
            return False, f"Bulk permission update error: {e}"

    try:
        result = execute_in_thread(_bulk_permission_update)

        if isinstance(result, tuple) and len(result) == 2:
            success_count, failed_count = result

            if success_count > 0:
                st.success(f"✅ Successfully updated {permission} for {success_count} users!")
                _clear_all_caches()
            if failed_count > 0:
                st.error(f"❌ Failed to update {failed_count} users")

            return success_count > 0
        else:
            success, reason = result
            if not success:
                st.error(f"❌ {reason}")
            return success

    except Exception as e:
        st.error(f"❌ Bulk permission update error: {e}")
        return False

def _handle_bulk_candidate_permission_update(candidate_ids: List[str], permission: str, value: bool, current_user_id: int) -> bool:
    """Handle bulk candidate permission updates with threading."""
    def _bulk_candidate_permission_update():
        try:
            perms = _check_user_permissions(current_user_id)
            if not perms.get("can_delete_records", False):  # Using delete permission for candidate management
                return False, "Access Denied: You need appropriate permissions"

            success_count = 0
            failed_count = 0

            for candidate_id in candidate_ids:
                try:
                    if permission == 'can_edit':
                        if set_candidate_permission(candidate_id, value):
                            success_count += 1
                        else:
                            failed_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    failed_count += 1

            return success_count, failed_count
        except Exception as e:
            return False, f"Bulk candidate permission update error: {e}"

    try:
        result = execute_in_thread(_bulk_candidate_permission_update)

        if isinstance(result, tuple) and len(result) == 2:
            success_count, failed_count = result

            if success_count > 0:
                st.success(f"✅ Successfully updated {permission} for {success_count} candidates!")
                _clear_all_caches()
            if failed_count > 0:
                st.error(f"❌ Failed to update {failed_count} candidates")

            return success_count > 0
        else:
            success, reason = result
            if not success:
                st.error(f"❌ {reason}")
            return success

    except Exception as e:
        st.error(f"❌ Bulk candidate permission update error: {e}")
        return False

# =============================================================================
# Enhanced User Management Panel with Complete Bulk Operations
# =============================================================================

def show_enhanced_user_management_panel():
    """Enhanced user management panel with complete bulk operations and zero refresh."""
    require_login()

    user = get_current_user(refresh=True)
    perms = _check_user_permissions(user.get("id"))

    if not perms.get("can_manage_users", False):
        st.error("🔒 Access denied. Admin privileges required.")
        st.stop()

    st.title("👥 Enhanced User Management Panel")
    st.caption("Manage system users with complete bulk operations and real-time feedback")

    # Render enhanced zero refresh manager
    _render_enhanced_zero_refresh_manager()

    # Load users with threading
    with st.spinner("Loading users..."):
        users = _get_users_fast()

    if not users:
        st.info("📭 No system users found.")
        return

    st.info(f"👥 Found {len(users)} system users")

    # Render enhanced bulk user controls
    _render_enhanced_bulk_user_controls(users, perms)

    # Enhanced bulk operation handling with JavaScript events
    if 'bulk_operation_result' not in st.session_state:
        st.session_state.bulk_operation_result = None

    # JavaScript event listeners for bulk operations
    bulk_js_handlers = """
< script >
// Bulk operation event handlers
window.addEventListener('bulkUserDelete', function(event) {
const userIds = event.detail.userIds;

// Show progress feedback
showToast(`🔄 Processing deletion of ${userIds.length} users...`, 'info', 0);

// Send to Streamlit backend
window.parent.postMessage({
type: 'streamlit:componentValue',
value: {
    action: 'bulk_user_delete',
    user_ids: userIds
}
}, '*');

// Reset
operation
state
after
delay
setTimeout(() = > {
    resetBulkOperationState();
}, 2000);
});

window.addEventListener('bulkPermissionUpdate', function(event)
{
    const
{userIds, permission, value} = event.detail;

showToast(`🔄 Updating ${permission}
for ${userIds.length} users...`, 'info', 0);

// Send to Streamlit backend
window.parent.postMessage({
type: 'streamlit:componentValue',
value: {
    action: 'bulk_permission_update',
    user_ids: userIds,
    permission: permission,
    value: value
}
}, '*');

setTimeout(() = > {
    resetBulkOperationState();
}, 2000);
});

window.addEventListener('bulkCandidateDelete', function(event)
{
    const
candidateIds = event.detail.candidateIds;

showToast(`🔄 Processing
deletion
of ${candidateIds.length}
candidates...
`, 'info', 0);

// Send
to
Streamlit
backend
window.parent.postMessage({
    type: 'streamlit:componentValue',
    value: {
        action: 'bulk_candidate_delete',
        candidate_ids: candidateIds
    }
}, '*');

setTimeout(() = > {
    resetBulkOperationState();
// Clear
selections
after
successful
delete
clearAllCandidates();
}, 2000);
});

window.addEventListener('bulkCandidatePermissionUpdate', function(event)
{
    const
{candidateIds, permission, value} = event.detail;

showToast(`🔄 Updating ${permission}
for ${candidateIds.length} candidates...`, 'info', 0);

// Send to Streamlit backend
window.parent.postMessage({
type: 'streamlit:componentValue',
value: {
    action: 'bulk_candidate_permission_update',
    candidate_ids: candidateIds,
    permission: permission,
    value: value
}
}, '*');

setTimeout(() = > {
    resetBulkOperationState();
}, 2000);
});
< / script >
    """

  components.html(bulk_js_handlers, height=1)

  # Handle bulk operations from JavaScript
  bulk_operation_data = st.experimental_get_query_params().get('bulk_operation')
  if bulk_operation_data and isinstance(bulk_operation_data, list):
      try:
          operation_data = json.loads(bulk_operation_data[0])
          action = operation_data.get('action')

          if action == 'bulk_user_delete':
              user_ids = operation_data.get('user_ids', [])
              if user_ids:
                  _handle_bulk_user_delete(user_ids, user.get("id"))

          elif action == 'bulk_permission_update':
              user_ids = operation_data.get('user_ids', [])
              permission = operation_data.get('permission')
              value = operation_data.get('value')
              if user_ids and permission:
                  _handle_bulk_permission_update(user_ids, permission, value, user.get("id"))

          elif action == 'bulk_candidate_delete':
              candidate_ids = operation_data.get('candidate_ids', [])
              if candidate_ids:
                  _handle_bulk_candidate_delete(candidate_ids, user.get("id"))

          elif action == 'bulk_candidate_permission_update':
              candidate_ids = operation_data.get('candidate_ids', [])
              permission = operation_data.get('permission')
              value = operation_data.get('value')
              if candidate_ids and permission:
                  _handle_bulk_candidate_permission_update(candidate_ids, permission, value, user.get("id"))

          # Clear the query parameter after processing
          st.experimental_set_query_params()

      except Exception as e:
          st.error(f"❌ Bulk operation error: {e}")

  # Enhanced user selection and management interface
  st.markdown("### 👥 User Selection & Management")

  # Quick stats and selection summary
  col1, col2, col3, col4 = st.columns(4)
  with col1:
      st.metric("Total Users", len(users))
  with col2:
      admin_count = len([u for u in users if u.get('role') == 'admin'])
      st.metric("Admins", admin_count)
  with col3:
      cv_enabled = len([u for u in users if u.get('can_view_cvs')])
      st.metric("Can View CVs", cv_enabled)
  with col4:
      delete_enabled = len([u for u in users if u.get('can_delete_records')])
      st.metric("Can Delete", delete_enabled)

  # Enhanced user list with better organization
  for idx, user_data in enumerate(users):
      user_id = user_data.get('id')
      user_email = user_data.get('email', 'No email')
      user_role = user_data.get('role', 'user')

      with st.container():
          # Create a styled container for each user
          user_container_style = f"""
    < div
style = "
background: linear - gradient(135
deg,  # f8f9fa, #ffffff);
border: 1
px
solid  # dee2e6;
border - radius: 12
px;
padding: 1
rem;
margin: 0.5
rem
0;
transition: all
0.2
s
ease;
box - shadow: 0
2
px
4
px
rgba(0, 0, 0, 0.1);
" onmouseover="
this.style.boxShadow = '0 4px 8px rgba(0,0,0,0.15)'" onmouseout="
this.style.boxShadow = '0 2px 4px rgba(0,0,0,0.1)'">
                       < / div >
                           """
                                                                                         
                                                                                                     sel_col, content_col = st.columns([0.1, 0.9])
                                                                                         
                                                                                                     with sel_col:
                                                                                                         # Enhanced checkbox for user selection
                                                                                                         _render_enhanced_user_checkbox(user_id)
                                                                                         
                                                                                                     with content_col:
                                                                                                         # User information header
                                                                                                         user_header_col, actions_col = st.columns([0.7, 0.3])
                                                                                         
                                                                                                         with user_header_col:
                                                                                                             # Role badge
                                                                                                             role_color = {
                                                                                                                 'ceo': '#dc3545',
                                                                                                                 'admin': '#28a745', 
                                                                                                                 'manager': '#ffc107',
                                                                                                                 'user': '#6c757d'
                                                                                                             }.get(user_role, '#6c757d')
                                                                                         
                                                                                                             st.markdown(f"""
                           < div
style = "margin-bottom: 0.5rem;" >
        < h4
style = "margin: 0; display: inline-block;" >👤 {user_email} < / h4 >
                                                                < span
style = "
background: {role_color};
color: white;
padding: 0.2
rem
0.6
rem;
border - radius: 15
px;
font - size: 0.8
rem;
font - weight: 600;
margin - left: 1
rem;
">{user_role.upper()}</span>
< / div >
    """, unsafe_allow_html=True)

with actions_col:
  # Quick action buttons
  action_col1, action_col2 = st.columns(2)

  with action_col1:
      if st.button("🔧", key=f"settings_{user_id}", help="Edit permissions"):
          st.session_state[f'show_permissions_{user_id}'] = not st.session_state.get(f'show_permissions_{user_id}', False)

  with action_col2:
      if st.button("📊", key=f"stats_{user_id}", help="View stats"):
          st.session_state[f'show_stats_{user_id}'] = not st.session_state.get(f'show_stats_{user_id}', False)

# User details in columns
detail_col1, detail_col2, detail_col3 = st.columns(3)

with detail_col1:
  st.markdown(f"""
    ** User
ID: ** {user_id}
       ** Created: ** {_format_datetime(user_data.get('created_at'))}
""")

with detail_col2:
cv_status = '✅ Enabled' if user_data.get('can_view_cvs') else '❌ Disabled'
delete_status = '✅ Enabled' if user_data.get('can_delete_records') else '❌ Disabled'
st.markdown(f"""
** View
CVs: ** {cv_status}
        ** Delete
Records: ** {delete_status}
""")

with detail_col3:
last_login = user_data.get('last_login')
login_display = _format_datetime(last_login) if last_login else "Never"
st.markdown(f"""
** Last
Login: ** {login_display}
          ** Status: ** {'🟢 Active' if user_data.get('is_active', True) else '🔴 Inactive'}
""")

# Expandable permission editor
if st.session_state.get(f'show_permissions_{user_id}', False):
st.markdown("---")
st.markdown("**🔧 Permission Editor**")

perm_col1, perm_col2, perm_col3 = st.columns(3)

with perm_col1:
    can_view_cvs = st.checkbox(
        "Can View CVs",
        value=bool(user_data.get('can_view_cvs', False)),
        key=f"cv_perm_{user_id}",
        help="Allow this user to view candidate CVs"
    )

with perm_col2:
    can_delete = st.checkbox(
        "Can Delete Records",
        value=bool(user_data.get('can_delete_records', False)),
        key=f"del_perm_{user_id}",
        help="Allow this user to delete candidate records"
    )

with perm_col3:
    if st.button("💾 Update Permissions", key=f"save_perm_{user_id}", type="primary"):
        new_perms = {
            "can_view_cvs": can_view_cvs,
            "can_delete_records": can_delete
        }

        try:
            def _update_single_user():
                return update_user_permissions(user_id, new_perms)

            if execute_in_thread(_update_single_user):
                st.success("✅ Permissions updated!")
                _clear_all_caches()
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Update failed")
        except Exception as e:
            st.error(f"Error updating permissions: {e}")

# Expandable stats view
if st.session_state.get(f'show_stats_{user_id}', False):
st.markdown("---")
st.markdown("**📊 User Statistics**")

# You can add more detailed user statistics here
stats_col1, stats_col2 = st.columns(2)

with stats_col1:
    st.info(f"Account Age: {_format_datetime(user_data.get('created_at'))}")

with stats_col2:
    st.info(f"Role: {user_role.title()}")

st.markdown("---")

# Bulk operation status display
if st.session_state.get('bulk_operation_result'):
result = st.session_state.bulk_operation_result
if result['success']:
st.success(f"✅ {result['message']}")
else:
st.error(f"❌ {result['message']}")

# Clear the result after displaying
st.session_state.bulk_operation_result = None

# =============================================================================
# Enhanced CEO Dashboard with Complete Zero Refresh Operations
# =============================================================================

def show_enhanced_ceo_panel():
"""
Enhanced
CEO
dashboard
with complete zero refresh bulk operations and threading."""
    require_login()

    user = get_current_user(refresh=True)
    if not user:
        st.error("Please log in again.")
        st.stop()

    user_id = user.get("id")
    perms = _check_user_permissions(user_id)

    # Allow access for CEO and admin roles
    if perms.get("role") not in ("ceo", "admin"):
        st.error("🔒 Access denied. CEO/Admin role required.")
        st.stop()

    st.title("🎯 Enhanced CEO Dashboard")
    st.caption(f"Welcome {user.get('email', 'User')} | Role: {perms.get('role', 'Unknown').title()}")

    # Render enhanced zero refresh manager
    _render_enhanced_zero_refresh_manager()

    # Enhanced quick stats with threading
    with st.spinner("Loading dashboard..."):
        stats = _get_stats_fast()

    # Enhanced statistics display
    stats_col1, stats_col2, stats_col3, stats_col4, stats_col5 = st.columns(5)

    with stats_col1:
        total_candidates = stats.get("total_candidates", 0)
        st.metric("📊 Total Candidates", total_candidates)

    with stats_col2:
        today_candidates = stats.get("candidates_today", 0)
        st.metric("📅 Today", today_candidates)

    with stats_col3:
        total_interviews = stats.get("total_interviews", 0)
        st.metric("🎤 Interviews", total_interviews)

    with stats_col4:
        total_assessments = stats.get("total_assessments", 0)
        st.metric("📋 Assessments", total_assessments)

    with stats_col5:
        # Calculate percentage of candidates with CVs
        cv_percentage = 0
        if total_candidates > 0:
            cv_count = stats.get("candidates_with_cv", 0)
            cv_percentage = round((cv_count / total_candidates) * 100, 1)
        st.metric("📄 CV Coverage", f"{cv_percentage}%")

    st.markdown("---")

    # Enhanced permission display
    st.sidebar.markdown("### 🔑 Your Permissions")
    permissions_status = [
        ("View CVs", perms.get('can_view_cvs')),
        ("Delete Records", perms.get('can_delete_records')),
        ("Manage Users", perms.get('can_manage_users'))
    ]

    for perm_name, has_perm in permissions_status:
        status_icon = "✅" if has_perm else "❌"
        status_text = "Enabled" if has_perm else "Disabled"
        st.sidebar.markdown(f"- **{perm_name}:** {status_icon} {status_text}")

    # Enhanced candidate management section
    st.header("👥 Advanced Candidate Management")

    # Enhanced controls with better layout
    ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4, ctrl_col5 = st.columns([3, 1, 1, 1, 1])

    with ctrl_col1:
        search_term = st.text_input("🔍 Search candidates",
                                   placeholder="Search by name, email, or ID...",
                                   key="enhanced_search")

    with ctrl_col2:
        show_no_cv = st.checkbox("📂 No CV only", key="filter_no_cv")

    with ctrl_col3:
        show_recent = st.checkbox("🆕 Recent only", key="filter_recent",
                                 help="Show candidates from last 7 days")

    with ctrl_col4:
        show_with_interviews = st.checkbox("🎤 With interviews", key="filter_interviews")

    with ctrl_col5:
        if st.button("🔄 Refresh", type="primary"):
            _clear_all_caches()
            st.rerun()

    # Load candidates with threading and progress indication
    with st.spinner("Loading candidates..."):
        candidates = _get_candidates_fast()

    if not candidates:
        st.warning("📭 No candidates found.")
        return

    # Enhanced filtering
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

        # Recent filter (last 7 days)
        if show_recent:
            created_at = candidate.get('created_at')
            if created_at:
                try:
                    if isinstance(created_at, str):
                        created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    else:
                        created_date = created_at

                    days_ago = (datetime.now().replace(tzinfo=created_date.tzinfo) - created_date).days
                    if days_ago > 7:
                        continue
                except:
                    continue

        # Interview filter (this would need to be implemented based on your data structure)
        if show_with_interviews:
            # Add interview filtering logic here if you have interview data readily available
            pass

        filtered_candidates.append(candidate)

    total_candidates = len(filtered_candidates)

    if total_candidates == 0:
        st.info("🔍 No candidates match your filters.")
        return

    # Enhanced bulk candidate controls
    _render_enhanced_bulk_candidate_controls(filtered_candidates, perms)

    # Enhanced selection summary
    selection_col1, selection_col2, selection_col3 = st.columns(3)

    with selection_col1:
        st.info(f"📊 **{total_candidates}** candidates match filters")

    with selection_col2:
        cv_count = len([c for c in filtered_candidates if c.get('has_cv_file') or c.get('has_resume_link')])
        st.info(f"📄 **{cv_count}** have CV/resume")

    with selection_col3:
        editable_count = len([c for c in filtered_candidates if c.get('can_edit')])
        st.info(f"✏️ **{editable_count}** can edit application")

    # Enhanced pagination with better controls
    items_per_page = st.selectbox("Items per page", [5, 10, 25, 50, 100], index=1, key="items_per_page")
    total_pages = (total_candidates + items_per_page - 1) // items_per_page

    if total_pages > 1:
        # Enhanced pagination controls
        page_col1, page_col2, page_col3 = st.columns([1, 2, 1])

        with page_col1:
            if st.button("⬅️ Previous", disabled=(st.session_state.get('current_page', 1) <= 1)):
                st.session_state.current_page = max(1, st.session_state.get('current_page', 1) - 1)
                st.rerun()

        with page_col2:
            page = st.selectbox("📄 Page", range(1, total_pages + 1),
                               index=st.session_state.get('current_page', 1) - 1,
                               key="page_select")
            st.session_state.current_page = page

        with page_col3:
            if st.button("Next ➡️", disabled=(st.session_state.get('current_page', 1) >= total_pages)):
                st.session_state.current_page = min(total_pages, st.session_state.get('current_page', 1) + 1)
                st.rerun()

        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_candidates = filtered_candidates[start_idx:end_idx]
        st.caption(f"Showing {start_idx + 1}-{min(end_idx, total_candidates)} of {total_candidates}")
    else:
        page_candidates = filtered_candidates

    # Enhanced candidate display with better organization
    for idx, candidate in enumerate(page_candidates):
        candidate_id = candidate.get('candidate_id', '')
        candidate_name = candidate.get('name', 'Unnamed')

        # Create enhanced container for each candidate
        with st.container():
            sel_col, content_col = st.columns([0.08, 0.92])

            with sel_col:
                if perms.get("can_delete_records"):
                    # Enhanced checkbox for candidate selection
                    _render_enhanced_candidate_checkbox(candidate_id)
                else:
                    st.write("")

            with content_col:
                # Enhanced candidate header with more information
                candidate_header = f"👤 {candidate_name} ({candidate_id})"

                # Add status indicators to header
                status_indicators = []
                if candidate.get('has_cv_file') or candidate.get('has_resume_link'):
                    status_indicators.append("📄 CV")
                if candidate.get('can_edit'):
                    status_indicators.append("✏️ Editable")

                if status_indicators:
                    candidate_header += f" • {' • '.join(status_indicators)}"

                with st.expander(candidate_header, expanded=False):
                    main_col, action_col = st.columns([3, 1])

                    with main_col:
                        # Enhanced personal details with better organization
                        _render_personal_details_organized(candidate)

                        # Enhanced CV section with proper access control
                        _render_cv_section_fixed(
                            candidate_id,
                            user_id,
                            candidate.get('has_cv_file', False),
                            candidate.get('has_resume_link', False)
                        )

                        # Enhanced interview history with comprehensive formatting
                        history = _get_interview_history_comprehensive(candidate_id)
                        _render_interview_history_comprehensive(history)

                    with action_col:
                        st.markdown("### ⚙️ Quick Actions")
                        st.caption(f"ID: {candidate_id}")

                        # Enhanced action buttons with better styling
                        current_can_edit = candidate.get('can_edit', False)
                        toggle_label = "🔓 Grant Edit" if not current_can_edit else "🔒 Revoke Edit"
                        button_type = "secondary" if current_can_edit else "primary"

                        if st.button(toggle_label, key=f"toggle_{candidate_id}", type=button_type):
                            try:
                                def _toggle_permission():
                                    return set_candidate_permission(candidate_id, not current_can_edit)

                                success = execute_in_thread(_toggle_permission)
                                if success:
                                    st.success("✅ Updated edit permission")
                                    _clear_all_caches()
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to update permission")
                            except Exception as e:
                                st.error(f"Error: {e}")

                        # Enhanced permission status display
                        if current_can_edit:
                            st.success("✏️ Can edit application")
                        else:
                            st.info("🔒 Cannot edit application")

                        # Enhanced individual delete section
                        if perms.get("can_delete_records"):
                            st.markdown("---")
                            st.markdown("**🗑️ Delete Options**")

                            individual_delete_key = f"individual_delete_{candidate_id}"

                            if st.session_state.get(individual_delete_key, False):
                                st.warning("⚠️ Confirm deletion?")
                                del_col1, del_col2 = st.columns(2)

                                with del_col1:
                                    if st.button("✅ Yes", key=f"confirm_individual_{candidate_id}", type="primary"):
                                        if _handle_bulk_candidate_delete([candidate_id], user_id):
                                            st.session_state[individual_delete_key] = False
                                            time.sleep(1)
                                            st.rerun()

                                with del_col2:
                                    if st.button("❌ No", key=f"cancel_individual_{candidate_id}"):
                                        st.session_state[individual_delete_key] = False
                                        st.rerun()
                            else:
                                if st.button("🗑️ Delete", key=f"delete_individual_{candidate_id}",
                                             type="secondary", help="Delete this candidate permanently"):
                                    st.session_state[individual_delete_key] = True
                                    st.rerun()

                        # Enhanced metadata display
                        st.markdown("---")
                        st.markdown("**📋 Metadata**")

                        # Creation and update info
                        created_info = _format_datetime(candidate.get('created_at'))
                        updated_info = _format_datetime(candidate.get('updated_at'))

                        st.caption(f"📅 Created: {created_info}")
                        st.caption(f"🕐 Updated: {updated_info}")

                        # CV status with more detail
                        cv_details = []
                        if candidate.get('has_cv_file'):
                            cv_details.append("📄 File uploaded")
                        if candidate.get('has_resume_link'):
                            cv_details.append("🔗 Link provided")

                        if cv_details:
                            for detail in cv_details:
                                st.caption(detail)
                        else:
                            st.caption("📂 No CV/resume")

    # Enhanced summary footer
    if filtered_candidates:
        st.markdown("---")
        summary_col1, summary_col2, summary_col3 = st.columns(3)

        with summary_col1:
            st.info(f"📊 Showing {len(page_candidates)} of {total_candidates} candidates")

        with summary_col2:
            if total_pages > 1:
                st.info(f"📄 Page {page} of {total_pages}")
            else:
                st.info("📄 Single page view")

        with summary_col3:
            # Show selection count if bulk operations are available
            if perms.get("can_delete_records"):
                st.success("✅ Bulk operations available")
            else:
                st.info("ℹ️ View-only mode")

# =============================================================================
# Main Router with Enhanced Navigation
# =============================================================================

def main():
    """Main application router with enhanced zero refresh capabilities and threading."""
    require_login()

    user = get_current_user(refresh=True)
    if not user:
        st.error("🔒 Authentication required")
        st.stop()

    perms = _check_user_permissions(user.get("id"))
    role = perms.get("role", "user")

    if role not in ("ceo", "admin"):
        st.error("🔒 Access denied. CEO/Admin role required.")
        st.stop()

    # Enhanced sidebar navigation with better styling
    st.sidebar.markdown("""
< div style="
background: linear - gradient(135
deg,  # 667eea 0%, #764ba2 100%);
color: white;
padding: 1.5
rem;
border - radius: 10
px;
margin - bottom: 1
rem;
text - align: center;
">
< h2
style = "margin: 0; font-size: 1.5rem;" >🎯 CEO
Control
Panel < / h2 >
          < p
style = "margin: 0.5rem 0 0 0; opacity: 0.9;" > Enhanced
Operations < / p >
               < / div >
                   """, unsafe_allow_html=True)
                                                                                                                                 
                                                                                                                                     # User info section
                                                                                                                                     st.sidebar.markdown(f"""
                   < div
style = "
background:  # f8f9fa;
padding: 1
rem;
border - radius: 8
px;
border - left: 4
px
solid  # 28a745;
margin - bottom: 1
rem;
">
< strong >👤 {user.get('email', 'User')} < / strong > < br >
                                            < span
style = "color: #6c757d;" >🔑 Role: {role.title()} < / span >
                                                      < / div > \
                                                          """, unsafe_allow_html=True)
                                                                                           
                                                                                               # Enhanced navigation pages
                                                                                               pages = {
                                                                                                   "📊 Enhanced Dashboard": show_enhanced_ceo_panel,
                                                                                                   "👥 User Management": show_enhanced_user_management_panel
                                                                                               }
                                                                                           
                                                                                               selected_page = st.sidebar.radio("Navigate to:", list(pages.keys()), key="main_navigation")
                                                                                           
                                                                                               # Enhanced features showcase
                                                                                               st.sidebar.markdown("---")
                                                                                               st.sidebar.markdown("### ⚡ **ENHANCED** Features")
                                                                                           
                                                                                               feature_list = [
                                                                                                   "✅ Zero Refresh Operations",
                                                                                                   "✅ Threaded Database Ops",
                                                                                                   "✅ Connection Pooling", 
                                                                                                   "✅ Bulk Candidate Delete",
                                                                                                   "✅ Bulk User Management",
                                                                                                   "✅ Smart Selection System",
                                                                                                   "✅ Real-time JavaScript UI",
                                                                                                   "✅ Enhanced Caching (5min)",
                                                                                                   "✅ Progress Feedback",
                                                                                                   "✅ Keyboard Shortcuts",
                                                                                                   "✅ Auto State Persistence",
                                                                                                   "✅ Toast Notifications"
                                                                                               ]
                                                                                           
                                                                                               for feature in feature_list:
                                                                                                   st.sidebar.caption(feature)
                                                                                           
                                                                                               # Performance metrics
                                                                                               st.sidebar.markdown("---")
                                                                                               st.sidebar.markdown("### 📈 Performance")
                                                                                           
                                                                                               # Simple performance indicators
                                                                                               load_start = time.time()
                                                                                           
                                                                                               try:
                                                                                                   # Test database connectivity
                                                                                                   conn = get_pooled_connection()
                                                                                                   if conn:
                                                                                                       return_pooled_connection(conn)
                                                                                                       db_status = "🟢 Connected"
                                                                                                   else:
                                                                                                       db_status = "🟡 Limited"
                                                                                               except:
                                                                                                   db_status = "🔴 Error"
                                                                                           
                                                                                               load_time = round((time.time() - load_start) * 1000, 1)
                                                                                           
                                                                                               st.sidebar.caption(f"🗄️ Database: {db_status}")
                                                                                               st.sidebar.caption(f"⚡ Load Time: {load_time}ms")
                                                                                           
                                                                                               # Cache status
                                                                                               if hasattr(st.session_state, 'cache_hits'):
                                                                                                   st.sidebar.caption(f"🎯 Cache Hits: {st.session_state.cache_hits}")
                                                                                           
                                                                                               # Quick actions section
                                                                                               st.sidebar.markdown("---")
                                                                                               st.sidebar.markdown("### ⚡ Quick Actions")
                                                                                           
                                                                                               if st.sidebar.button("🔄 Clear All Caches", help="Clear all cached data"):
                                                                                                   _clear_all_caches()
                                                                                                   st.sidebar.success("✅ Caches cleared!")
                                                                                                   time.sleep(1)
                                                                                                   st.rerun()
                                                                                           
                                                                                               if st.sidebar.button("📊 Refresh Stats", help="Reload statistics"):
                                                                                                   _get_stats_fast.clear()
                                                                                                   st.sidebar.success("✅ Stats refreshed!")
                                                                                                   time.sleep(1)
                                                                                                   st.rerun()
                                                                                           
                                                                                               # System information
                                                                                               st.sidebar.markdown("---")
                                                                                               st.sidebar.markdown("### ℹ️ System Info")
                                                                                               st.sidebar.caption(f"🐍 Python: {threading.active_count()} threads")
                                                                                               st.sidebar.caption(f"⏰ Server Time: {datetime.now().strftime('%H:%M:%S')}")
                                                                                           
                                                                                               # Run selected page with error handling
                                                                                               try:
                                                                                                   with st.spinner(f"Loading {selected_page}..."):
                                                                                                       pages[selected_page]()
                                                                                               except Exception as e:
                                                                                                   st.error(f"❌ Page error: {e}")
                                                                                                   st.exception(e)
                                                                                           
                                                                                                   # Provide recovery options
                                                                                                   st.markdown("---")
                                                                                                   st.markdown("### 🔧 Recovery Options")
                                                                                           
                                                                                                   recovery_col1, recovery_col2, recovery_col3 = st.columns(3)
                                                                                           
                                                                                                   with recovery_col1:
                                                                                                       if st.button("🔄 Reload Page"):
                                                                                                           st.rerun()
                                                                                           
                                                                                                   with recovery_col2:
                                                                                                       if st.button("🗑️ Clear Session"):
                                                                                                           st.session_state.clear()
                                                                                                           st.rerun()
                                                                                           
                                                                                                   with recovery_col3:
                                                                                                       if st.button("🏠 Go Home"):
                                                                                                           st.session_state.clear()
                                                                                                           st.experimental_set_query_params()
                                                                                                           st.rerun()
                                                                                           
                                                                                           if __name__ == "__main__":
                                                                                               # Initialize session state variables
                                                                                               if 'selected_candidate_ids' not in st.session_state:
                                                                                                   st.session_state.selected_candidate_ids = set()
                                                                                               if 'selected_user_ids' not in st.session_state:
                                                                                                   st.session_state.selected_user_ids = set()
                                                                                               if 'cache_hits' not in st.session_state:
                                                                                                   st.session_state.cache_hits = 0
                                                                                               if 'current_page' not in st.session_state:
                                                                                                   st.session_state.current_page = 1
                                                                                           
                                                                                               # Run the main application
                                                                                               try:
                                                                                                   main()
                                                                                               except Exception as e:
                                                                                                   st.error(f"❌ Application Error: {e}")
                                                                                                   st.markdown("### 🔧 Emergency Recovery")
                                                                                                   if st.button("🚨 Full Reset", type="primary"):
                                                                                                       st.session_state.clear()
                                                                                                       st.experimental_set_query_params()
                                                                                                       st.rerun()