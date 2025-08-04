import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import uuid

def schedule_interview_page():
    st.title("Schedule New Interview")

    # Fetch available interviewers
    conn = sqlite3.connect('data/brv_applicants.db')
    interviewers = pd.read_sql_query(
        "SELECT id, email FROM users WHERE role = 'interviewer'",
        conn
    )

    # Fetch applicants who don't have scheduled interviews
    applicants = pd.read_sql_query(
        """
        SELECT a.id, a.name, a.email 
        FROM applicants a
        WHERE a.status = 'new' OR a.status = 'in_process'
        """,
        conn
    )
    conn.close()

    if interviewers.empty:
        st.error("No interviewers available in the system.")
        return

    if applicants.empty:
        st.error("No applicants available for scheduling interviews.")
        return

    with st.form("schedule_interview_form"):
        # Select applicant
        applicant_options = [f"{row['name']} ({row['email']})" for _, row in applicants.iterrows()]
        selected_applicant = st.selectbox("Select Applicant", applicant_options)

        # Select interviewer
        interviewer_options = interviewers['email'].tolist()
        selected_interviewer = st.selectbox("Select Interviewer", interviewer_options)

        # Select date and time
        interview_date = st.date_input("Interview Date", datetime.now() + timedelta(days=1))
        interview_time = st.time_input("Interview Time", datetime.now().time())

        # Combine date and time
        interview_datetime = datetime.combine(interview_date, interview_time)

        # Additional notes
        notes = st.text_area("Notes (Optional)")

        submit = st.form_submit_button("Schedule Interview")

        if submit:
            # Get applicant and interviewer IDs
            applicant_name = selected_applicant.split(" (")[0]
            applicant_email = selected_applicant.split("(")[1].replace(")", "")

            conn = sqlite3.connect('data/brv_applicants.db')
            c = conn.cursor()

            # Get applicant ID
            c.execute("SELECT id FROM applicants WHERE name = ? AND email = ?", (applicant_name, applicant_email))
            applicant_id = c.fetchone()[0]

            # Get interviewer ID
            c.execute("SELECT id FROM users WHERE email = ? AND role = 'interviewer'", (selected_interviewer,))
            interviewer_id = c.fetchone()[0]

            # Create interview record
            interview_id = str(uuid.uuid4())
            c.execute(
                """
                INSERT INTO interviews 
                (id, applicant_id, interviewer_id, scheduled_time, notes, status) 
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (interview_id, applicant_id, interviewer_id, interview_datetime, notes, "scheduled")
            )

            # Update applicant status
            c.execute(
                "UPDATE applicants SET status = 'interview_scheduled', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (applicant_id,)
            )

            conn.commit()
            conn.close()

            st.success(f"Interview scheduled successfully for {applicant_name} with {selected_interviewer} on {interview_datetime.strftime('%Y-%m-%d %H:%M')}")

if __name__ == "__main__":
    st.set_page_config(
        page_title="Schedule Interview - BRV Applicant System",
        page_icon="📋",
        layout="wide"
    )
    schedule_interview_page()
