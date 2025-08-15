# interviewer.py
import os
import json
import base64
from datetime import datetime, date, time

import streamlit as st
from db_postgres import (
    get_all_candidates,
    search_candidates_by_name_or_email,
    get_candidate_by_id,
    create_interview,
    get_interviews_for_candidate,
)
from typing import Dict, Any


# --------- helpers

def _status_badge(scheduled_at: str | datetime | None, result: str | None) -> str:
    """Return a small colored status badge for interview rows."""
    try:
        now = datetime.utcnow()
        if isinstance(scheduled_at, str):
            # tolerate both "YYYY-mm-dd HH:MM:SS" and ISO timestamps
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
        return "🟢 **done**"  # past without explicit result
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


def _embed_pdf_from_local(path: str, height: int = 620):
    """Inline-embed a local PDF (base64) + keep a download button."""
    if not os.path.exists(path):
        st.warning("Local CV file not found.")
        return
    with open(path, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    data_url = f"data:application/pdf;base64,{b64}"
    st.components.v1.iframe(data_url, height=height)
    st.download_button("Download CV", data, file_name=os.path.basename(path))


def _embed_pdf_from_url(url: str, height: int = 620):
    """Inline-embed Google Drive/HTTP link + provide a simple link."""
    # Handle common Google Drive share links -> preview links
    if "drive.google.com" in url and "view" in url:
        # convert .../view?usp=sharing -> .../preview
        url = url.split("/view")[0] + "/preview"
    st.components.v1.iframe(url, height=height)
    st.link_button("Open in new tab", url)


def _structured_notes_ui(prefix: str) -> Dict[str, str]:
    """14 categorized notes fields."""
    st.markdown("### Interview Questions & Notes")
    cols = st.columns(2)
    with cols[0]:
        age = st.text_input("1. Age", key=f"{prefix}_age")
        english = st.text_area("2. English understanding", key=f"{prefix}_english")
        commitment = st.text_area("3. Commitment", key=f"{prefix}_commitment")
        festivals = st.text_area("4. No leaves for festivals", key=f"{prefix}_festivals")
        attitude = st.text_area("5. Attitude", key=f"{prefix}_attitude")
        project = st.text_input("6. Suitable for which project", key=f"{prefix}_project")
        education = st.text_input("7. Education", key=f"{prefix}_education")
    with cols[1]:
        family = st.text_area("8. Family background", key=f"{prefix}_family")
        experience = st.text_area("9. Past work experience & salary", key=f"{prefix}_experience")
        own_pc = st.selectbox("10. Own PC or laptop", ["", "yes", "no"], key=f"{prefix}_ownpc")
        cont_night = st.selectbox("11. Continuous night shift", ["", "ok", "not ok"], key=f"{prefix}_contnight")
        rot_night = st.selectbox("12. Rotational night shift", ["", "ok", "not ok"], key=f"{prefix}_rotnight")
        profile_fit = st.text_area("13. Profile fit", key=f"{prefix}_profilefit")
        grasping = st.text_area("14. Grasping", key=f"{prefix}_grasping")

    return {
        "age": age,
        "english": english,
        "commitment": commitment,
        "no_festival_leave": festivals,
        "attitude": attitude,
        "project_fit": project,
        "education": education,
        "family_background": family,
        "experience_salary": experience,
        "own_pc": own_pc,
        "continuous_night": cont_night,
        "rotational_night": rot_night,
        "profile_fit": profile_fit,
        "grasping": grasping,
    }


# --------- main view

def interviewer_view():
    st.header("Interviewer Dashboard")

    # Search
    search_query = st.text_input("Search candidates (name / email / id / phone / skills)", placeholder="Start typing…")

    # Fetch candidates
    try:
        if search_query.strip():
            candidates = search_candidates_by_name_or_email(search_query.strip())
            st.info(f"Found {len(candidates)} candidate(s) for “{search_query}”.")
        else:
            # fall back to most recent list
            candidates = search_candidates_by_name_or_email("")  # implementation returns recent list
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
            # Left: basics + resume; Right: application data
            left, right = st.columns([1, 1])

            with left:
                st.subheader("Basic Info")
                st.write(f"**Name:** {cname}")
                st.write(f"**Email:** {cand.get('email', cand.get('candidate_email', '—'))}")
                st.write(f"**Phone:** {cand.get('phone', '—')}")
                st.write(f"**Created:** {cand.get('created_at', '—')}")

                # CV preview/Download
                st.markdown("#### Resume")
                resume_link = cand.get("resume_link")
                local_cv_dir = os.getenv("LOCAL_STORAGE_PATH") or "/app/CV"
                local_path = os.path.join(local_cv_dir, f"{cid}.pdf")

                try:
                    if resume_link:
                        _embed_pdf_from_url(resume_link)
                    elif os.path.exists(local_path):
                        _embed_pdf_from_local(local_path)
                    else:
                        st.info("No resume found.")
                except Exception as e:
                    st.warning(f"Unable to preview resume: {e}")

            with right:
                st.subheader("Application Data")
                form_dict = _as_readable_form(cand.get("form_data"))
                if form_dict:
                    # Show as nice two-column label:value
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
                st.markdown("### Schedule / Record Interview")
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
