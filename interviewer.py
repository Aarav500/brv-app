# interviewer.py
import streamlit as st
from db_postgres import get_all_candidates, get_candidate_by_id, get_conn
from psycopg2.extras import RealDictCursor
from datetime import datetime
import json


def create_interviews_table():
    """Create interviews table if it doesn't exist"""
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                        CREATE TABLE IF NOT EXISTS interviews
                        (
                            id
                            SERIAL
                            PRIMARY
                            KEY,
                            candidate_id
                            TEXT
                            NOT
                            NULL,
                            scheduled_at
                            TIMESTAMP,
                            interviewer
                            TEXT,
                            result
                            TEXT,
                            notes
                            TEXT,
                            created_at
                            TIMESTAMP
                            DEFAULT
                            now
                        (
                        ),
                            updated_at TIMESTAMP DEFAULT now
                        (
                        ),
                            FOREIGN KEY
                        (
                            candidate_id
                        ) REFERENCES candidates
                        (
                            candidate_id
                        )
                            );
                        """)
    conn.close()


def save_interview(candidate_id: str, scheduled_at: datetime, interviewer: str, result: str, notes: str):
    """Save interview record to database"""
    create_interviews_table()  # Ensure table exists
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                        INSERT INTO interviews (candidate_id, scheduled_at, interviewer, result, notes)
                        VALUES (%s, %s, %s, %s, %s) RETURNING id
                        """, (candidate_id, scheduled_at, interviewer, result or None, notes))
            interview_id = cur.fetchone()[0]
    conn.close()
    return interview_id


def get_interviews_for_candidate(candidate_id: str):
    """Get all interviews for a candidate"""
    create_interviews_table()  # Ensure table exists
    conn = get_conn()
    with conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                        SELECT *
                        FROM interviews
                        WHERE candidate_id = %s
                        ORDER BY created_at DESC
                        """, (candidate_id,))
            interviews = cur.fetchall()
    conn.close()
    return interviews


def search_candidates(query: str = ""):
    """Search candidates by name or email"""
    conn = get_conn()
    with conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if query.strip():
                cur.execute("""
                            SELECT *
                            FROM candidates
                            WHERE LOWER(name) LIKE LOWER(%s)
                               OR LOWER(email) LIKE LOWER(%s)
                            ORDER BY updated_at DESC LIMIT 50
                            """, (f"%{query}%", f"%{query}%"))
            else:
                cur.execute("""
                            SELECT *
                            FROM candidates
                            ORDER BY updated_at DESC LIMIT 50
                            """)
            results = cur.fetchall()
    conn.close()
    return results


def interviewer_view():
    st.header("Interviewer Dashboard")

    # Search section
    st.subheader("Find Candidates")
    search_query = st.text_input("Search by name or email", placeholder="Enter name or email...")

    # Get candidates
    try:
        if search_query.strip():
            candidates = search_candidates(search_query.strip())
            st.info(f"Found {len(candidates)} candidate(s) matching '{search_query}'")
        else:
            candidates = search_candidates()
            st.info(f"Showing {len(candidates)} most recent candidates")

        if not candidates:
            st.warning("No candidates found.")
            return

        # Display candidates
        for candidate in candidates:
            with st.expander(f"📋 {candidate['name']} ({candidate['candidate_id']})"):
                # Candidate information
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("### Candidate Details")
                    st.write(f"**Name:** {candidate['name']}")
                    st.write(f"**Email:** {candidate['email']}")
                    st.write(f"**Phone:** {candidate.get('phone', 'N/A')}")
                    st.write(f"**Created:** {candidate.get('created_at', 'N/A')}")

                    if candidate.get('resume_link'):
                        st.markdown(f"**Resume:** [View Resume]({candidate['resume_link']})")
                    else:
                        st.write("**Resume:** Not uploaded")

                with col2:
                    st.markdown("### Application Data")
                    if candidate.get('form_data'):
                        form_data = candidate['form_data']
                        if isinstance(form_data, str):
                            try:
                                form_data = json.loads(form_data)
                            except:
                                st.text("Invalid form data format")
                                form_data = {}

                        # Display key fields
                        if isinstance(form_data, dict):
                            skills = form_data.get('skills', 'Not specified')
                            experience = form_data.get('experience', 'Not specified')
                            st.write(f"**Skills:** {skills}")
                            st.write(f"**Experience:** {experience}")
                        else:
                            st.json(form_data)
                    else:
                        st.write("No application data available")

                st.markdown("---")

                # Interview section
                st.markdown("### Interview Management")

                # Show existing interviews
                existing_interviews = get_interviews_for_candidate(candidate['candidate_id'])
                if existing_interviews:
                    st.markdown("**Previous Interviews:**")
                    for interview in existing_interviews:
                        with st.container():
                            st.write(f"🗓️ **Scheduled:** {interview.get('scheduled_at', 'N/A')}")
                            st.write(f"👤 **Interviewer:** {interview.get('interviewer', 'N/A')}")
                            st.write(f"📝 **Result:** {interview.get('result', 'Pending')}")
                            if interview.get('notes'):
                                st.write(f"**Notes:** {interview['notes']}")
                            st.write(f"**Created:** {interview.get('created_at', 'N/A')}")
                            st.markdown("---")

                # New interview form
                st.markdown("**Schedule New Interview:**")

                col3, col4 = st.columns(2)

                with col3:
                    scheduled_date = st.date_input(
                        "Interview Date",
                        key=f"date_{candidate['candidate_id']}"
                    )
                    scheduled_time = st.time_input(
                        "Interview Time",
                        key=f"time_{candidate['candidate_id']}"
                    )
                    interviewer_name = st.text_input(
                        "Interviewer Name",
                        key=f"interviewer_{candidate['candidate_id']}",
                        placeholder="Enter interviewer name"
                    )

                with col4:
                    result = st.selectbox(
                        "Interview Result",
                        ["", "scheduled", "completed", "pass", "fail", "on_hold"],
                        key=f"result_{candidate['candidate_id']}"
                    )
                    notes = st.text_area(
                        "Interview Notes",
                        key=f"notes_{candidate['candidate_id']}",
                        placeholder="Enter interview notes, feedback, or observations..."
                    )

                # Save interview button
                if st.button("Save Interview", key=f"save_interview_{candidate['candidate_id']}"):
                    if scheduled_date and interviewer_name.strip():
                        try:
                            # Combine date and time
                            scheduled_datetime = datetime.combine(scheduled_date, scheduled_time)

                            # Save interview
                            interview_id = save_interview(
                                candidate['candidate_id'],
                                scheduled_datetime,
                                interviewer_name.strip(),
                                result if result else "scheduled",
                                notes.strip()
                            )

                            st.success(f"Interview saved successfully! (ID: {interview_id})")
                            st.rerun()

                        except Exception as e:
                            st.error(f"Error saving interview: {str(e)}")
                    else:
                        st.error("Please provide at least the interview date and interviewer name.")

    except Exception as e:
        st.error(f"Error loading candidates: {str(e)}")

    # Quick stats section
    st.markdown("---")
    st.subheader("Quick Actions")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Refresh Candidates"):
            st.rerun()

    with col2:
        if st.button("Clear Search"):
            # Clear search session state
            if f"search_query" in st.session_state:
                del st.session_state["search_query"]
            st.rerun()

    with col3:
        total_candidates = len(get_all_candidates())
        st.metric("Total Candidates", total_candidates)