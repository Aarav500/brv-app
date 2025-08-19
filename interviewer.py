# interviewer.py
import json
from datetime import datetime, date, time
from typing import Dict, Any

import streamlit as st
from db_postgres import (
    get_all_candidates,
    search_candidates_by_name_or_email,
    get_interviews_for_candidate,
    create_interview,
    get_candidate_cv,  # still used
    delete_candidate_by_actor,
)
from drive_and_cv_views import preview_cv_ui  # ✅ new reusable CV UI


# --------- helpers

def _status_badge(scheduled_at: str | datetime | None, result: str | None) -> str:
    """Return a small colored status badge for interview rows."""
    try:
        now = datetime.utcnow()
        if isinstance(scheduled_at, str):
            try:
                scheduled_at = datetime.fromisoformat(scheduled_at.replace("Z", ""))
            except Exception:
                pass
        is_future = scheduled_at and scheduled_at > now
        result = (result or "").lower().strip()

        if result in {"pass", "fail", "completed"}:
            return "✅ **done**"
        if is_future:
            return "🔴 **upcoming**"
        return "🟢 **done**"
    except Exception:
        return "ℹ️"


def _as_readable_form(form_data: Any) -> Dict[str, Any]:
    """Normalize form_data (which may already be JSON string) to a flat dict for display."""
    if isinstance(form_data, str):
        try:
            form_data = json.loads(form_data)
        except Exception:
            return {"raw": form_data}
    if not isinstance(form_data, dict):
        return {"raw": str(form_data)}
    return form_data


def _structured_notes_ui(prefix: str) -> Dict[str, str]:
    """Organized Interview Questions UI."""
    notes = {}

    st.markdown("### Interview Questions & Notes")

    # --- Personal Info ---
    with st.expander("👤 Personal Info", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            notes["age"] = st.text_input("Age", key=f"{prefix}_age")
            notes["education"] = st.text_input("Education", key=f"{prefix}_education")
        with col2:
            notes["family_background"] = st.text_area("Family background", key=f"{prefix}_family")

    # --- Skills & Understanding ---
    with st.expander("💡 Skills & Understanding", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            notes["english"] = st.text_area("English understanding", key=f"{prefix}_english")
            notes["experience_salary"] = st.text_area("Past work experience & salary", key=f"{prefix}_experience")
        with col2:
            notes["attitude"] = st.text_area("Attitude", key=f"{prefix}_attitude")
            notes["commitment"] = st.text_area("Commitment", key=f"{prefix}_commitment")

    # --- Work Conditions ---
    with st.expander("🕒 Work Conditions", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            notes["no_festival_leave"] = st.selectbox(
                "No leaves for festivals", ["", "Yes", "No"], key=f"{prefix}_festivals"
            )
            notes["own_pc"] = st.selectbox(
                "Own PC or laptop", ["", "Yes", "No"], key=f"{prefix}_ownpc"
            )
        with col2:
            notes["continuous_night"] = st.selectbox(
                "Continuous night shift", ["", "Ok", "Not ok"], key=f"{prefix}_contnight"
            )
            notes["rotational_night"] = st.selectbox(
                "Rotational night shift", ["", "Ok", "Not ok"], key=f"{prefix}_rotnight"
            )

    # --- Fit & Assignment ---
    with st.expander("✅ Fit & Assignment", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            notes["profile_fit"] = st.text_area("Profile fit", key=f"{prefix}_profilefit")
        with col2:
            notes["project_fit"] = st.text_area("Suitable for which project", key=f"{prefix}_project")
        notes["grasping"] = st.text_area("Grasping", key=f"{prefix}_grasping")
        notes["other_notes"] = st.text_area("Other Notes", key=f"{prefix}_othernotes")

    return notes


# --------- main view

def interviewer_view():
    st.header("📝 Interviewer Dashboard")

    # Search
    search_query = st.text_input(
        "Search candidates (name / email / id / phone / skills)", placeholder="Start typing…"
    )

    # Fetch candidates
    try:
        if search_query.strip():
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

    for cand in candidates:
        cid = cand.get("candidate_id") or cand.get("id") or ""
        cname = cand.get("name") or cand.get("candidate_name") or "Candidate"
        with st.expander(f"📋 {cname} — {cid}", expanded=False):
            # Layout: left = basics/resume, right = app & interviews
            left, right = st.columns([1, 1])

            with left:
                st.subheader("Basic Info")
                st.write(f"**Name:** {cname}")
                st.write(f"**Email:** {cand.get('email', cand.get('candidate_email', '—'))}")
                st.write(f"**Phone:** {cand.get('phone', '—')}")
                st.write(f"**Created:** {cand.get('created_at', '—')}")

                # CV preview/Download
                st.markdown("#### Resume")
                preview_cv_ui(cid)

                # Candidate deletion
                current_user = st.session_state.get("user")
                if current_user and current_user.get("can_delete_records", False):
                    if st.button("🗑️ Delete Candidate", key=f"delcand_{cid}"):
                        user_id = current_user.get("id")
                        if user_id and delete_candidate_by_actor(cid, user_id):
                            st.success("Candidate deleted successfully.")
                            st.rerun()
                        else:
                            st.error("Failed to delete candidate.")

            with right:
                st.subheader("Application Data")
                form_dict = _as_readable_form(cand.get("form_data"))
                if form_dict:
                    keys = sorted(form_dict.keys())
                    for i in range(0, len(keys), 2):
                        c1, c2 = st.columns(2)
                        k1 = keys[i]
                        v1 = form_dict.get(k1)
                        with c1:
                            st.caption(k1.replace("_", " ").title())
                            st.write(v1 if v1 not in (None, "") else "—")
                        if i + 1 < len(keys):
                            k2 = keys[i + 1]
                            v2 = form_dict.get(k2)
                            with c2:
                                st.caption(k2.replace("_", " ").title())
                                st.write(v2 if v2 not in (None, "") else "—")

                st.markdown("---")
                st.subheader("Interviews")

                # Existing interviews
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
                            st.write(f"**When:** {sch} &nbsp;&nbsp; **Status:** {badge}")
                            st.write(f"**Interviewer:** {row.get('interviewer', '—')}")
                            if row.get("notes"):
                                try:
                                    j = json.loads(row["notes"])
                                    with st.expander("Notes", expanded=False):
                                        for k, v in j.items():
                                            st.write(f"- **{k.replace('_',' ').title()}**: {v}")
                                except Exception:
                                    st.write(f"**Notes:** {row['notes']}")
                            st.divider()
                else:
                    st.caption("No previous interviews found.")

                # New Interview
                st.markdown("### ➕ Schedule / Record Interview")
                c3, c4 = st.columns(2)
                with c3:
                    d: date = st.date_input("Interview Date", key=f"d_{cid}")
                    t: time = st.time_input("Interview Time", key=f"t_{cid}")
                    interviewer_name = st.text_input("Interviewer Name", key=f"iv_{cid}")
                with c4:
                    result = st.selectbox(
                        "Result",
                        ["scheduled", "completed", "pass", "fail", "on_hold"],
                        index=0,
                        key=f"res_{cid}",
                    )
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

    # Footer actions
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
            pass
        st.metric("Total Candidates", total)
    with cols[2]:
        st.caption("Tip: Search accepts name, email, id, phone, and skills.")
