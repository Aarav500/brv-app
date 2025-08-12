import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from mysql_db import get_db_connection
from cloud_storage import download_cv
import json

# ---------- DB helpers ----------
def _fetchall(query, params=()):
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall()
            return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()

def _fetchone(query, params=()):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
    finally:
        conn.close()

def _execute(query, params=()):
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            conn.commit()
            return True
    except Exception as e:
        st.error(f"DB error: {e}")
        return False
    finally:
        conn.close()

# ---------- Business ----------
def get_all_candidates():
    query = """
        SELECT candidate_id::text AS id, full_name AS name, email, phone, resume_link, interview_status,
               timestamp
        FROM candidates
        ORDER BY timestamp DESC
    """
    return _fetchall(query)

def get_candidate_by_id(candidate_id):
    return _fetchone("SELECT * FROM candidates WHERE candidate_id = %s", (candidate_id,))

def schedule_interview(candidate_id, interviewer_id, scheduled_time, notes=None):
    # Insert into interviews table and update candidate interview_status
    interview_id = str(uuid.uuid4()) if "uuid" in globals() else None
    q1 = """
        INSERT INTO interviews (interview_id, candidate_id, interviewer_id, scheduled_time, feedback, status, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
    """
    q2 = "UPDATE candidates SET interview_status = %s WHERE candidate_id = %s"
    ok1 = _execute(q1, (interview_id, candidate_id, interviewer_id, scheduled_time, notes, "Scheduled"))
    ok2 = _execute(q2, ("Scheduled", candidate_id))
    return ok1 and ok2

def save_interview_feedback(candidate_id, interviewer_name, feedback, result):
    # For simplicity update candidates table fields (interview_status/interview_feedback)
    q = "UPDATE candidates SET interview_status = %s, resume_link = resume_link WHERE candidate_id = %s"
    # we will store feedback in interviews table if exists; else in candidates (as interview_feedback JSON)
    ok = _execute("UPDATE candidates SET interview_status = %s, timestamp = NOW() WHERE candidate_id = %s", (result, candidate_id))
    # append feedback to an interviews table or store as interview_feedback in candidates
    _execute("UPDATE candidates SET interview_feedback = %s WHERE candidate_id = %s", (feedback, candidate_id))
    return ok

# ---------- Streamlit UI ----------
def interviewer_view():
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Candidate Profiles", "Schedule Interview", "My Interviews", "View CV by ID"])

    if page == "Candidate Profiles":
        interviewer_candidates_page()
    elif page == "Schedule Interview":
        interviewer_schedule_page()
    elif page == "My Interviews":
        interviewer_interviews_page()
    elif page == "View CV by ID":
        st.info("Use the Candidate Profiles page to view CVs by candidate.")

def interviewer_candidates_page():
    st.title("Candidate Profiles")
    candidates = get_all_candidates()
    if not candidates:
        st.warning("No candidates available.")
        return
    options = [f"ID {c['id']} - {c['name']}" for c in candidates]
    sel = st.selectbox("Select candidate", options)
    if sel:
        cid = sel.split(" - ")[0].replace("ID ","")
        c = get_candidate_by_id(cid)
        if not c:
            st.error("Candidate not found")
            return
        st.subheader(c.get("full_name") or c.get("name"))
        st.write(f"Email: {c.get('email')}")
        st.write(f"Phone: {c.get('phone')}")
        st.write(f"Interview status: {c.get('interview_status')}")
        if c.get("resume_link"):
            if st.button("Download Resume"):
                try:
                    content = download_cv(c["resume_link"])
                    st.success("Downloaded (simulated) — implement actual download in cloud_storage.download_cv")
                except Exception as e:
                    st.error(f"Failed to download: {e}")

        st.write("### Interview Feedback")
        interviewer_name = st.text_input("Your name")
        feedback = st.text_area("Feedback")
        result = st.selectbox("Decision", ["Pass","Fail","Hold"])
        if st.button("Submit Feedback"):
            if not interviewer_name or not feedback:
                st.warning("Fill name and feedback")
            else:
                ok = save_interview_feedback(cid, interviewer_name, feedback, result)
                if ok:
                    st.success("Feedback saved")
                else:
                    st.error("Failed to save feedback")

def interviewer_schedule_page():
    st.title("Schedule Interview")
    candidates = get_all_candidates()
    pending = [c for c in candidates if (c.get("interview_status") or "") != "Scheduled"]
    if not pending:
        st.info("No candidates to schedule")
        return
    cand_opts = [f"ID {c['id']} - {c['name']}" for c in pending]
    selected = st.selectbox("Select candidate", cand_opts)
    interviewers = _fetchall("SELECT user_id::text AS id, email, username FROM users WHERE role = %s", ("interviewer",))
    interviewer_opts = [f"{u['username']} ({u['email']})" for u in interviewers]
    selected_int = st.selectbox("Select interviewer", interviewer_opts)
    date = st.date_input("Date", datetime.now().date() + timedelta(days=1))
    time = st.time_input("Time", datetime.now().time())
    notes = st.text_area("Notes")
    if st.button("Schedule"):
        cid = selected.split(" - ")[0].replace("ID ","")
        int_idx = interviewer_opts.index(selected_int)
        interviewer_id = interviewers[int_idx]["id"]
        dt = datetime.combine(date, time)
        ok = schedule_interview(cid, interviewer_id, dt, notes)
        if ok:
            st.success("Interview scheduled")
        else:
            st.error("Failed to schedule")

def interviewer_interviews_page():
    st.title("My Interviews")
    uid = st.session_state.get("user_id")
    if not uid:
        st.warning("Not logged in")
        return
    # find scheduled interviews assigned to this interviewer
    rows = _fetchall("SELECT i.interview_id, c.full_name, i.scheduled_time, i.status FROM interviews i JOIN candidates c ON i.candidate_id = c.candidate_id WHERE i.interviewer_id = %s ORDER BY i.scheduled_time DESC", (uid,))
    if not rows:
        st.info("No interviews")
        return
    df = pd.DataFrame(rows)
    st.dataframe(df)
