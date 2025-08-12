import streamlit as st
import asyncio
import pandas as pd
from datetime import datetime
from postgres_db import get_connection  # Your asyncpg connection helper

# Fetch list of candidates without scheduled interview
async def fetch_candidates():
    query = """
        SELECT id, name, email
        FROM candidates
        WHERE status != 'Interview Scheduled'
        ORDER BY created_at DESC
    """
    async with get_connection() as conn:
        rows = await conn.fetch(query)
    return [dict(r) for r in rows]

# Fetch list of interviewers (users table with role='interviewer')
async def fetch_interviewers():
    query = """
        SELECT id, name, email
        FROM users
        WHERE role = 'interviewer'
        ORDER BY name
    """
    async with get_connection() as conn:
        rows = await conn.fetch(query)
    return [dict(r) for r in rows]

# Insert a new interview record and update candidate status
async def schedule_interview(candidate_id, interviewer_id, interview_date):
    async with get_connection() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO interviews (candidate_id, interviewer_id, interview_date, status, created_at)
                VALUES ($1, $2, $3, 'Scheduled', NOW())
                """,
                candidate_id, interviewer_id, interview_date
            )
            await conn.execute(
                """
                UPDATE candidates
                SET status = 'Interview Scheduled'
                WHERE id = $1
                """,
                candidate_id
            )

def main():
    st.title("📅 Schedule Interview")

    # Role-based access control
    if st.session_state.get("user_role") not in ["ceo", "interviewer"]:
        st.error("You do not have permission to access this page.")
        return

    # Load data
    with st.spinner("Loading data..."):
        candidates = asyncio.run(fetch_candidates())
        interviewers = asyncio.run(fetch_interviewers())

    if not candidates:
        st.info("No candidates available for scheduling.")
        return

    # Form
    candidate_names = [f"{c['name']} ({c['email']})" for c in candidates]
    interviewer_names = [f"{i['name']} ({i['email']})" for i in interviewers]

    with st.form("schedule_form"):
        selected_candidate = st.selectbox("Select Candidate", candidate_names)
        selected_interviewer = st.selectbox("Select Interviewer", interviewer_names)
        interview_date = st.date_input("Interview Date", datetime.today())
        submit = st.form_submit_button("Schedule Interview")

        if submit:
            cand_id = candidates[candidate_names.index(selected_candidate)]['id']
            int_id = interviewers[interviewer_names.index(selected_interviewer)]['id']

            asyncio.run(schedule_interview(cand_id, int_id, interview_date))
            st.success("✅ Interview scheduled successfully!")

if __name__ == "__main__":
    main()
