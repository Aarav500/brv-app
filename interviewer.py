# interviewer.py
import json
from datetime import datetime, date, time
from typing import Dict, Any, List, Optional

import streamlit as st
from auth import get_current_user
from db_postgres import (
    get_all_candidates,
    search_candidates_by_name_or_email,
    get_interviews_for_candidate,
    create_interview,
    delete_candidate,
    get_user_permissions,
    get_all_users_with_permissions,
    set_user_permission,
    get_candidate_history,
    get_interviewer_performance_stats,
    get_candidate_cv_secure,
    get_conn
)


# -------------------- Performance Optimizations --------------------

@st.cache_data(ttl=30, show_spinner=False)
def _get_candidates_cached(search_query=""):
    """Cached candidate loading to avoid database reload after each action."""
    try:
        if search_query and search_query.strip():
            return search_candidates_by_name_or_email(search_query.strip())
        else:
            return search_candidates_by_name_or_email("")
    except Exception as e:
        st.error(f"Error loading candidates: {e}")
        return []


@st.cache_data(ttl=60, show_spinner=False)
def _get_users_cached():
    """Cached users loading for permission management."""
    try:
        return get_all_users_with_permissions()
    except Exception as e:
        st.error(f"Failed to load users: {e}")
        return []


def _clear_candidates_cache():
    """Clear candidates cache for refresh."""
    _get_candidates_cached.clear()


def _clear_users_cache():
    """Clear users cache for refresh."""
    _get_users_cached.clear()


# -------------------- Access Control Functions --------------------

def _check_user_permissions(user_id: int) -> Dict[str, Any]:
    """Check user permissions with strict enforcement."""
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


def _get_cv_with_proper_access(candidate_id: str, user_id: int) -> tuple:
    """Get CV with proper access control like in CEO panel."""
    try:
        perms = _check_user_permissions(user_id)
        if not perms.get("can_view_cvs", False):
            return None, None, "no_permission"

        cv_bytes, cv_name, reason = get_candidate_cv_secure(candidate_id, user_id)
        return cv_bytes, cv_name, reason
    except Exception as e:
        st.error(f"CV fetch error: {e}")
        return None, None, "error"


# -------------------- Receptionist Assessment Functions --------------------

def _get_receptionist_assessments(candidate_id: str) -> List[Dict[str, Any]]:
    """Get receptionist assessments for a candidate."""
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            # Check if receptionist_assessments table exists
            cur.execute("""
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                          AND table_name = 'receptionist_assessments'
                        """)
            if not cur.fetchone():
                return []

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

            assessments = []
            for row in cur.fetchall():
                assessments.append({
                    'id': row[0],
                    'created_at': row[1],
                    'speed_test': row[2],
                    'accuracy_test': row[3],
                    'work_commitment': row[4],
                    'english_understanding': row[5],
                    'comments': row[6]
                })

        conn.close()
        return assessments
    except Exception as e:
        st.warning(f"Could not load assessments: {e}")
        return []


def _render_assessment_summary(assessments: List[Dict[str, Any]]) -> bool:
    """Render assessment summary and return eligibility status."""
    if not assessments:
        st.error("❌ **NOT ELIGIBLE FOR INTERVIEW** - No receptionist assessment completed")
        st.info("📋 Candidate must complete receptionist assessment before interview")
        return False

    latest = assessments[0]  # Most recent assessment

    st.success("✅ **ELIGIBLE FOR INTERVIEW** - Receptionist assessment completed")

    with st.expander("📊 Latest Receptionist Assessment Results", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            st.metric("Speed Test", f"{latest['speed_test']}/100")
            st.metric("Work Commitment", latest['work_commitment'])

        with col2:
            st.metric("Accuracy Test", f"{latest['accuracy_test']}/100")
            st.metric("English Understanding", latest['english_understanding'])

        if latest['comments']:
            st.markdown("**Comments:**")
            st.write(latest['comments'])

        st.caption(f"Assessed on: {latest['created_at']}")

    if len(assessments) > 1:
        st.caption(f"📈 Total assessments: {len(assessments)} (showing latest)")

    return True


# -------------------- CV Preview Functions (Same as CEO) --------------------

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


def _render_cv_section_with_access(candidate_id: str, user_id: int, candidate_data: Dict[str, Any]):
    """Render CV section with proper access control (same as CEO panel)."""
    st.markdown("### 📄 CV & Documents")

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
                import base64
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
        resume_link = candidate_data.get("resume_link")
        if resume_link:
            st.markdown(f"🔗 **Resume Link:** [Open CV]({resume_link})")
        else:
            st.info("📂 No CV uploaded")
    else:
        st.error("❌ Error accessing CV")


# -------------------- Helpers --------------------

def _status_badge(scheduled_at: Optional[str | datetime], result: Optional[str]) -> str:
    """Return a small status badge for interview rows."""
    try:
        now = datetime.utcnow()
        sch = scheduled_at
        if isinstance(sch, str):
            try:
                sch = datetime.fromisoformat(sch.replace("Z", ""))
            except Exception:
                sch = None
        is_future = bool(sch and sch > now)
        result_norm = (result or "").lower().strip()

        if result_norm in {"pass", "passed", "success"}:
            return "✅ Passed"
        if result_norm in {"fail", "failed"}:
            return "❌ Failed"
        if result_norm in {"completed", "complete"}:
            return "✅ Completed"
        if is_future:
            return "🔴 Upcoming"
        if result_norm in {"scheduled", ""}:
            return "🟡 Scheduled"
        return "ℹ️"
    except Exception:
        return "ℹ️"


def _as_readable_form(form_data: Any) -> Dict[str, Any]:
    """Normalize form_data to a flat dict for display."""
    if isinstance(form_data, str):
        try:
            form_data = json.loads(form_data)
        except Exception:
            return {"raw": form_data}
    if not isinstance(form_data, dict):
        return {"raw": str(form_data)}
    return form_data


def _structured_notes_ui(prefix: str) -> Dict[str, str]:
    """Improved Interview Notes UI with Markdown formatting for readability."""
    notes: Dict[str, str] = {}

    st.markdown("### 📝 Interview Questions & Notes")

    notes["summary"] = st.text_area(
        "Overall Summary",
        key=f"{prefix}_summary",
        placeholder="Write key points in Markdown (use - for bullets, **bold** for highlights)...",
        height=200,
    )

    # Optional additional structured fields
    notes["attitude"] = st.text_area(
        "Attitude (optional)", key=f"{prefix}_attitude",
        placeholder="Professional, proactive, etc.", height=80
    )
    notes["experience_salary"] = st.text_area(
        "Experience / Salary (optional)", key=f"{prefix}_experience",
        placeholder="Years / domains / last CTC", height=80
    )

    # Ensure renderer shows the nice Markdown block
    notes["rich_notes_md"] = notes.get("summary", "")

    st.markdown("---")
    st.info("💡 Use Markdown in the 'Overall Summary' box: `- bullets`, `**bold**`, `_italic_` to keep notes clean.")
    return notes


def _history_timeline(candidate_id: str):
    """Render candidate history as a simple timeline."""
    st.markdown("### 📜 Application History")
    try:
        history_rows = get_candidate_history(candidate_id)
    except Exception as e:
        st.warning(f"Could not load history: {e}")
        history_rows = []

    if not history_rows:
        st.caption("No history available.")
        return

    for row in history_rows:
        ts = row.get("created_at") or row.get("timestamp") or ""
        event = row.get("event") or "Updated"
        detail = row.get("detail") or ""
        icon = "🟢"
        ev_lower = event.lower()
        if "create" in ev_lower:
            icon = "🟢"
        elif "update" in ev_lower:
            icon = "✏️"
        elif "cv" in ev_lower:
            icon = "📎"
        elif "delete" in ev_lower:
            icon = "🗑️"
        st.write(f"{icon} {ts} — **{event}** {detail}")


# -------------------- Permission Manager --------------------

def _permissions_manager_ui():
    """Permission management UI for CEO/Admin."""
    st.subheader("🔑 Manage User Permissions (Admin)")

    users = _get_users_cached()
    if not users:
        st.info("No users found.")
        return

    PERMISSION_FIELDS = [
        ("can_view_cvs", "Can View CVs"),
        ("can_delete_records", "Can Delete Records"),
        ("can_grant_delete", "Can Grant Delete Permission"),
    ]

    for user in users:
        with st.expander(f"👤 {user.get('email')} — {user.get('role')}", expanded=False):
            updated_perms = {}

            col1, col2, col3 = st.columns(3)

            with col1:
                updated_perms["can_view_cvs"] = st.checkbox(
                    "Can View CVs",
                    value=bool(user.get("can_view_cvs", False)),
                    key=f"{user['id']}_can_view_cvs"
                )

            with col2:
                updated_perms["can_delete_records"] = st.checkbox(
                    "Can Delete Records",
                    value=bool(user.get("can_delete_records", False)),
                    key=f"{user['id']}_can_delete_records"
                )

            with col3:
                updated_perms["can_grant_delete"] = st.checkbox(
                    "Can Grant Delete",
                    value=bool(user.get("can_grant_delete", False)),
                    key=f"{user['id']}_can_grant_delete"
                )

            if st.button(f"💾 Save Permissions for {user.get('email')}", key=f"save_perm_{user['id']}"):
                try:
                    ok = set_user_permission(
                        user["id"],
                        can_view=updated_perms["can_view_cvs"],
                        can_delete=updated_perms["can_delete_records"],
                        can_grant_delete=updated_perms["can_grant_delete"],
                    )
                    if ok:
                        st.success("✅ Permissions updated.")
                        _clear_users_cache()
                        st.rerun()
                    else:
                        st.error("❌ Failed to update permissions.")
                except Exception as e:
                    st.error(f"Error: {e}")

            # Show current permissions
            st.markdown("**Current Status:**")
            st.markdown(f"- View CVs: {'✅' if user.get('can_view_cvs') else '❌'}")
            st.markdown(f"- Delete Records: {'✅' if user.get('can_delete_records') else '❌'}")
            st.markdown(f"- Grant Delete: {'✅' if user.get('can_grant_delete') else '❌'}")


# -------------------- Main Interviewer view --------------------

def interviewer_view():
    st.header("📝 Interviewer Dashboard")

    # Minimal typography tweaks for cleaner notes display
    st.markdown(
        """
        <style>
        .markdown-text p { line-height: 1.4; }
        .markdown-text ul { margin-top: 0.25rem; }
        .markdown-text li { margin: 0.15rem 0; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Validate session user
    current_user = get_current_user()
    if not current_user:
        st.error("No active user session. Please log in.")
        return

    user_id = current_user.get("id")
    perms = _check_user_permissions(user_id)
    role = perms.get("role", "user")

    # Show permissions in sidebar
    st.sidebar.markdown("### 🔑 Your Permissions")
    st.sidebar.markdown(f"- **Role:** {role.title()}")
    st.sidebar.markdown(f"- **View CVs:** {'✅ Enabled' if perms.get('can_view_cvs') else '❌ Disabled'}")
    st.sidebar.markdown(f"- **Delete Records:** {'✅ Enabled' if perms.get('can_delete_records') else '❌ Disabled'}")
    st.sidebar.markdown(f"- **Manage Users:** {'✅ Enabled' if perms.get('can_manage_users') else '❌ Disabled'}")

    # Permission manager for CEO/Admin
    if perms.get("can_manage_users"):
        st.markdown("---")
        _permissions_manager_ui()
        st.markdown("---")

    # Search area with refresh button
    col1, col2 = st.columns([4, 1])
    with col1:
        search_query = st.text_input(
            "Search candidates (name / email / id / phone / skills)",
            placeholder="Start typing…",
            key="interviewer_search"
        )
    with col2:
        if st.button("🔄 Refresh", key="refresh_candidates"):
            _clear_candidates_cache()
            st.rerun()

    # Fetch candidates (cached for performance)
    candidates = _get_candidates_cached(search_query)

    if search_query and search_query.strip():
        st.info(f"Found {len(candidates)} candidate(s) for "
        {search_query}
        ".")
        else:
        st.info(f"Showing {len(candidates)} most recent candidate(s).")

    if not candidates:
        st.warning("No candidates available.")
        return

    # Iterate candidates
    for cand in candidates:
        cid = cand.get("candidate_id") or cand.get("id") or ""
        cname = cand.get("name") or cand.get("candidate_name") or "Candidate"

        with st.expander(f"📋 {cname} — {cid}", expanded=False):
            left, right = st.columns([1, 1])

            # Left column: basic info + actions
            with left:
                st.subheader("Basic Info")
                st.write(f"**Name:** {cname}")
                st.write(f"**Email:** {cand.get('email', '—')}")
                st.write(f"**Phone:** {cand.get('phone', '—')}")
                st.write(f"**Created:** {cand.get('created_at', '—')}")

                # Delete candidate (permission-based)
                if perms.get("can_delete_records"):
                    st.markdown("---")
                    if st.button("🗑️ Delete Candidate", key=f"delcand_{cid}"):
                        try:
                            success, reason = delete_candidate(cid, user_id)
                            if success:
                                st.success("✅ Candidate deleted successfully.")
                                _clear_candidates_cache()
                                st.rerun()
                            else:
                                st.error(f"❌ Delete failed: {reason}")
                        except Exception as e:
                            st.error(f"Error deleting candidate: {e}")
                else:
                    st.caption("🚫 You don't have permission to delete records.")

            # Right column: application form data
            with right:
                st.subheader("Application Data")
                form_dict = _as_readable_form(cand.get("form_data"))
                if form_dict:
                    for k, v in (form_dict or {}).items():
                        st.write(f"- **{k.replace('_', ' ').title()}**: {v if v else '—'}")
                else:
                    st.caption("No application data available.")

            # Receptionist Assessment Status (Critical for Interview Eligibility)
            st.markdown("---")
            st.subheader("📊 Assessment Status")
            assessments = _get_receptionist_assessments(cid)
            is_eligible = _render_assessment_summary(assessments)

            # CV preview (full width; permission-aware)
            st.markdown("---")
            _render_cv_section_with_access(cid, user_id, cand)

            # History timeline
            st.markdown("---")
            _history_timeline(cid)

            # Interviews list
            st.markdown("---")
            st.subheader("🎤 Interview History")

            try:
                existing = get_interviews_for_candidate(cid)
            except Exception as e:
                existing = []
                st.warning(f"Could not load interviews: {e}")

            if existing:
                for row in existing:
                    sch = row.get("scheduled_at")
                    result = row.get("result")
                    badge = _status_badge(sch, result)
                    with st.container():
                        st.write(f"**When:** {sch}  &nbsp;&nbsp; **Status:** {badge}")
                        st.write(f"**Interviewer:** {row.get('interviewer', '—')}")
                        notes = row.get("notes")
                        if notes:
                            try:
                                j = json.loads(notes)
                                LABELS = {
                                    "age": "Age",
                                    "education": "Education",
                                    "family_background": "Family Background",
                                    "english": "English Understanding",
                                    "experience_salary": "Experience & Salary",
                                    "attitude": "Attitude",
                                    "commitment": "Commitment",
                                    "no_festival_leave": "No Festival Leave",
                                    "own_pc": "Own PC/Laptop",
                                    "continuous_night": "Continuous Night Shift",
                                    "rotational_night": "Rotational Night Shift",
                                    "profile_fit": "Profile Fit",
                                    "project_fit": "Project Fit",
                                    "grasping": "Grasping",
                                    "other_notes": "Other Notes",
                                }
                                ORDER = [
                                    "age", "education", "family_background", "english", "experience_salary",
                                    "attitude", "commitment", "no_festival_leave", "own_pc",
                                    "continuous_night", "rotational_night", "profile_fit", "project_fit",
                                    "grasping", "other_notes"
                                ]

                                created_at_val = row.get("created_at")
                                ts_str = str(created_at_val or sch or "")
                                interviewer_name = row.get("interviewer", "—")
                                exp_label = f"Notes — {interviewer_name} • {ts_str}" if (
                                            interviewer_name or ts_str) else "Notes"

                                with st.expander(exp_label, expanded=False):
                                    # Rich Markdown section
                                    rich_md = j.get("rich_notes_md")
                                    if rich_md:
                                        st.markdown("#### Rich Notes")
                                        st.markdown(str(rich_md))
                                        st.markdown("---")

                                    colL, colR = st.columns(2)
                                    for idx, key in enumerate(ORDER):
                                        val = j.get(key, "")
                                        if val:
                                            label = LABELS.get(key, key.replace('_', ' ').title())
                                            if idx % 2 == 0:
                                                with colL:
                                                    st.markdown(f"**{label}:**  ")
                                                    st.markdown(str(val).replace("\n", "  \n"))
                                            else:
                                                with colR:
                                                    st.markdown(f"**{label}:**  ")
                                                    st.markdown(str(val).replace("\n", "  \n"))
                            except Exception:
                                # Fallback for plain text notes
                                created_at_val = row.get("created_at")
                                ts_str = str(created_at_val or sch or "")
                                interviewer_name = row.get("interviewer", "—")
                                exp_label = f"Notes — {interviewer_name} • {ts_str}" if (
                                            interviewer_name or ts_str) else "Notes"
                                with st.expander(exp_label, expanded=False):
                                    st.markdown(str(notes).replace("\n", "  \n"))
                        st.divider()
            else:
                st.caption("No previous interviews found.")

            # Schedule/record interview (only if eligible and has permissions)
            st.markdown("### ➕ Schedule / Record Interview")

            can_schedule = (
                    perms.get("can_view_cvs", False) or
                    role in ("interviewer", "admin", "ceo")
            )

            if not is_eligible:
                st.error("❌ Cannot schedule interview - Receptionist assessment required first")
            elif not can_schedule:
                st.warning("🚫 You don't have permission to schedule interviews.")
            else:
                d: date = st.date_input("Interview Date", key=f"d_{cid}")
                t: time = st.time_input("Interview Time", key=f"t_{cid}")
                interviewer_name = st.text_input("Interviewer Name", key=f"iv_{cid}")
                result = st.text_input("Result (scheduled/completed/pass/fail/on_hold)", key=f"res_{cid}")

                structured = _structured_notes_ui(prefix=f"notes_{cid}")

                if st.button("Save Interview", key=f"save_{cid}"):
                    try:
                        scheduled_dt = datetime.combine(d, t)
                        notes_json = json.dumps(structured, ensure_ascii=False)
                        iid = create_interview(
                            cid,
                            scheduled_dt,
                            interviewer_name.strip(),
                            result.strip() if result else "scheduled",
                            notes_json,
                        )
                        if iid:
                            st.success(f"✅ Interview saved (ID: {iid}).")
                            _clear_candidates_cache()
                            st.rerun()
                        else:
                            st.error("❌ Failed to save interview.")
                    except Exception as e:
                        st.error(f"Error saving interview: {e}")

    # Footer: quick actions and stats
    st.divider()
    cols = st.columns(3)
    with cols[0]:
        if st.button("🔄 Refresh All Data"):
            _clear_candidates_cache()
            _clear_users_cache()
            st.rerun()

    with cols[1]:
        total = len(_get_candidates_cached(""))
        st.metric("Total Candidates", total)

    with cols[2]:
        try:
            stats = get_interviewer_performance_stats(current_user.get("id"))
            if stats:
                success_rate = stats.get("success_rate")
                scheduled = stats.get("scheduled", 0)
                completed = stats.get("completed", 0)
                st.metric("Success Rate", f"{success_rate}%")
                st.caption(f"Scheduled: {scheduled}  •  Completed: {completed}")
            else:
                st.caption("No interviewer stats available.")
        except Exception:
            st.caption("Interviewer stats not available.")

    st.caption("💡 Tip: Candidates need receptionist assessment before interviews can be scheduled.")


# Expose entrypoint
if __name__ == "__main__":
    st.set_page_config(page_title="Interviewer Dashboard", layout="wide")
    interviewer_view()