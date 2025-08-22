# interviewer.py
import json
from datetime import datetime, date, time
from typing import Dict, Any, List, Optional

import streamlit as st
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
)
from drive_and_cv_views import preview_cv_ui  # reuse CV UI


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
                # if parsing fails, keep original
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
    """Normalize form_data (which may already be a JSON string) to a flat dict for display."""
    if isinstance(form_data, str):
        try:
            form_data = json.loads(form_data)
        except Exception:
            return {"raw": form_data}
    if not isinstance(form_data, dict):
        return {"raw": str(form_data)}
    return form_data


def _structured_notes_ui(prefix: str) -> Dict[str, str]:
    """Organized Interview Questions UI with consistent formatting and placeholders.
    Adds a Rich Notes (Markdown) area for cleaner bullets and spacing.
    """
    notes: Dict[str, str] = {}
    st.markdown("### Interview Questions & Notes")

    col_a, col_b = st.columns(2)
    with col_a:
        notes["age"] = st.text_input("Age", key=f"{prefix}_age", placeholder="e.g., 25")
        notes["education"] = st.text_input("Education", key=f"{prefix}_education", placeholder="e.g., B.Sc. Computer Science")
        notes["attitude"] = st.text_area("Attitude", key=f"{prefix}_attitude", placeholder="Professional, proactive, etc.", height=80)
        notes["commitment"] = st.text_area("Commitment", key=f"{prefix}_commitment", placeholder="Notice period, long-term interest…", height=80)
        notes["profile_fit"] = st.text_area("Profile fit", key=f"{prefix}_profilefit", placeholder="Role alignment and strengths", height=80)
        notes["grasping"] = st.text_area("Grasping", key=f"{prefix}_grasping", placeholder="Learning speed, understanding", height=80)
    with col_b:
        notes["family_background"] = st.text_area("Family background", key=f"{prefix}_family", placeholder="Summary", height=80)
        notes["english"] = st.text_area("English understanding", key=f"{prefix}_english", placeholder="Fluency, comprehension", height=80)
        notes["experience_salary"] = st.text_area("Past work experience & salary", key=f"{prefix}_experience", placeholder="Years, domains, last CTC", height=80)
        notes["no_festival_leave"] = st.text_area("No leaves for festivals", key=f"{prefix}_festivals", placeholder="Acceptance / concerns", height=80)
        notes["own_pc"] = st.text_area("Own PC or laptop", key=f"{prefix}_ownpc", placeholder="Specs / Availability", height=80)
        notes["continuous_night"] = st.text_area("Continuous night shift", key=f"{prefix}_contnight", placeholder="Willingness / constraints", height=80)
        notes["rotational_night"] = st.text_area("Rotational night shift", key=f"{prefix}_rotnight", placeholder="Willingness / constraints", height=80)
        notes["project_fit"] = st.text_area("Suitable for which project", key=f"{prefix}_project", placeholder="Teams or projects", height=80)

    notes["other_notes"] = st.text_area("Other Notes", key=f"{prefix}_othernotes", placeholder="Any additional observations…", height=100)

    # Rich Markdown notes input for bullets and clean formatting
    notes["rich_notes_md"] = st.text_area(
        "Rich Notes (Markdown)",
        key=f"{prefix}_rich",
        placeholder="Use Markdown: - bullets, 1. numbered, **bold**, _italic_\nExample:\n- Strengths: ...\n- Concerns: ...",
        height=140,
    )

    return notes


def _history_timeline(candidate_id: str):
    """Render candidate history as a simple timeline using get_candidate_history() from DB."""
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


# -------------------- CEO/Admin permission manager (embedded small panel) --------------------

def _permissions_manager_ui():
    """Small inline UI that lets CEO/admin adjust interviewer-related permissions.
    Note: Only core DB-backed permissions are persisted: can_view_cvs, can_delete_records, can_grant_delete.
    """
    st.subheader("🔑 Manage Interviewer Permissions (Admin)")
    try:
        users = get_all_users_with_permissions()
    except Exception as e:
        st.error(f"Failed to load users: {e}")
        return

    if not users:
        st.info("No users found.")
        return

    # UI fields (some are informational only and not stored in DB directly)
    PERMISSION_FIELDS = [
        "can_view_cv",                 # maps to users.can_view_cvs
        "can_schedule_interviews",    # UI only (not stored)
        "can_view_interview_feedback",# UI only (not stored)
        "can_edit_interview_feedback",# UI only (not stored)
        "can_delete_candidate",       # maps to users.can_delete_records
        "can_grant_delete",           # maps to users.can_grant_delete
    ]

    for user in users:
        with st.expander(f"👤 {user.get('email')} — {user.get('role')}", expanded=False):
            updated_ui: Dict[str, bool] = {}
            for field in PERMISSION_FIELDS:
                # derive current value from DB where applicable
                if field == "can_view_cv":
                    current = bool(user.get("can_view_cvs", False))
                elif field == "can_delete_candidate":
                    current = bool(user.get("can_delete_records", False))
                else:
                    current = bool(user.get(field, False))
                updated_ui[field] = st.checkbox(
                    field.replace("_", " ").title(),
                    value=current,
                    key=f"{user['id']}_{field}"
                )

            if st.button(f"💾 Save Permissions for {user.get('email')}", key=f"save_perm_{user['id']}"):
                try:
                    # Map UI fields to DB-backed flags
                    ok = set_user_permission(
                        user["id"],
                        can_view=bool(updated_ui.get("can_view_cv", False)),
                        can_delete=bool(updated_ui.get("can_delete_candidate", False)),
                        can_grant_delete=bool(updated_ui.get("can_grant_delete", False)),
                    )
                    if ok:
                        st.success("Permissions updated.")
                        st.rerun()
                    else:
                        st.error("Failed to update permissions.")
                except Exception as e:
                    st.error(f"Error: {e}")


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

    # validate session user
    current_user = st.session_state.get("user")
    if not current_user:
        st.error("No active user session. Please log in.")
        return

    # load permissions for current user (granular)
    try:
        user_perms = get_user_permissions(current_user.get("id")) or {}
    except Exception:
        user_perms = {}

    # If CEO or admin, show quick permission manager
    role = (current_user.get("role") or "").lower()
    if role in ("ceo", "admin"):
        st.markdown("---")
        _permissions_manager_ui()
        st.markdown("---")

    # Search area
    search_query = st.text_input("Search candidates (name / email / id / phone / skills)",
                                 placeholder="Start typing…")

    # Fetch candidates (search or recent)
    try:
        if search_query and search_query.strip():
            candidates = search_candidates_by_name_or_email(search_query.strip())
            st.info(f"Found {len(candidates)} candidate(s) for “{search_query}”.")
        else:
            candidates = search_candidates_by_name_or_email("")  # recent list
            st.info(f"Showing {len(candidates)} most recent candidate(s).")
    except Exception as e:
        st.error(f"Error loading candidates: {e}")
        return

    if not candidates:
        st.warning("No candidates available.")
        return

    # iterate candidates
    for cand in candidates:
        cid = cand.get("candidate_id") or cand.get("id") or ""
        cname = cand.get("name") or cand.get("candidate_name") or "Candidate"

        with st.expander(f"📋 {cname} — {cid}", expanded=False):
            left, right = st.columns([1, 1])

            # Left column: basic info + delete action
            with left:
                st.subheader("Basic Info")
                st.write(f"**Name:** {cname}")
                st.write(f"**Email:** {cand.get('email', '—')}")
                st.write(f"**Phone:** {cand.get('phone', '—')}")
                st.write(f"**Created:** {cand.get('created_at', '—')}")

                # Delete candidate (Admin/CEO only)
                ui_can_delete = (role in ("admin", "ceo"))
                if ui_can_delete:
                    if st.button("🗑️ Delete Candidate", key=f"delcand_{cid}"):
                        user_id = current_user.get("id")
                        try:
                            if user_id and delete_candidate(cid, user_id):
                                st.success("Candidate deleted successfully.")
                                st.rerun()
                            else:
                                st.error("Failed to delete candidate (permission or DB error).")
                        except Exception as e:
                            st.error(f"Error deleting candidate: {e}")
                else:
                    st.caption("🚫 You do not have permission to delete candidates.")

            # Right column: application form data
            with right:
                st.subheader("Application Data")
                form_dict = _as_readable_form(cand.get("form_data"))
                if form_dict:
                    for k, v in (form_dict or {}).items():
                        st.write(f"- **{k.replace('_', ' ').title()}**: {v if v else '—'}")
                else:
                    st.caption("No application data available.")

            # CV preview (full width)
            st.markdown("---")
            st.subheader("📄 Resume Preview")
            if bool(user_perms.get("can_view_cvs", False)) or (role in ("admin", "ceo")):
                try:
                    preview_cv_ui(cid)
                    # download handled inside preview_cv_ui
                except Exception as e:
                    st.error(f"Error showing CV: {e}")
            else:
                st.warning("🚫 You don't have permission to view CVs.")

            # History timeline
            st.markdown("---")
            _history_timeline(cid)

            # Interviews list
            st.markdown("---")
            st.subheader("Interviews")

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
                                # Pretty, consistent 2-column display with friendly labels
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
                                    "age","education","family_background","english","experience_salary",
                                    "attitude","commitment","no_festival_leave","own_pc",
                                    "continuous_night","rotational_night","profile_fit","project_fit",
                                    "grasping","other_notes"
                                ]
                                with st.expander("Notes", expanded=False):
                                    # Rich Markdown section (if provided)
                                    try:
                                        rich_md = j.get("rich_notes_md")
                                    except Exception:
                                        rich_md = None
                                    if rich_md:
                                        st.markdown("#### Rich Notes")
                                        st.markdown(str(rich_md))
                                        st.markdown("---")
                                    colL, colR = st.columns(2)
                                    for idx, key in enumerate(ORDER):
                                        val = j.get(key, "")
                                        if val:
                                            label = LABELS.get(key, key.replace('_',' ').title())
                                            if idx % 2 == 0:
                                                with colL:
                                                    st.markdown(f"**{label}:**  ")
                                                    st.markdown(str(val).replace("\n","  \n"))
                                            else:
                                                with colR:
                                                    st.markdown(f"**{label}:**  ")
                                                    st.markdown(str(val).replace("\n","  \n"))
                            except Exception:
                                # Fallback for plain text notes
                                with st.expander("Notes", expanded=False):
                                    st.markdown(str(notes).replace("\n","  \n"))
                        st.divider()
            else:
                st.caption("No previous interviews found.")

            # Schedule/record interview (permission guarded)
            st.markdown("### ➕ Schedule / Record Interview")
            if bool(user_perms.get("can_schedule_interviews", False)):
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
                            st.success(f"Interview saved (ID: {iid}).")
                            st.rerun()
                        else:
                            st.error("Failed to save interview.")
                    except Exception as e:
                        st.error(f"Error saving interview: {e}")
            else:
                st.caption("🚫 You don't have permission to schedule interviews.")

    # Footer: quick actions and stats
    st.divider()
    cols = st.columns(3)
    with cols[0]:
        if st.button("Refresh"):
            st.rerun()

    with cols[1]:
        total = 0
        try:
            total = len(get_all_candidates())
        except Exception:
            total = 0
        st.metric("Total Candidates", total)

    with cols[2]:
        # interviewer performance summary (if DB helper exists)
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

    st.caption("Tip: Search accepts name, email, id, phone, and skills.")


# Expose a simple entrypoint for frameworks that import this module
if __name__ == "__main__":
    # This block is only for local quick testing (won't run under Streamlit's typical usage).
    st.set_page_config(page_title="Interviewer Dashboard", layout="wide")
    interviewer_view()
