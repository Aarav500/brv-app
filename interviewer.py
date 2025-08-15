# interviewer.py
import streamlit as st
from db_postgres import (
    get_all_candidates, get_candidate_by_id,
    search_candidates_by_name_or_email, create_interview,
    get_interviews_for_candidate
)
from datetime import datetime
import json

st.text_area("Interview Questions Notes", key="questions_notes")
st.text_area("Additional Notes", key="additional_notes")

cv_path = os.path.join(os.getenv("LOCAL_STORAGE_PATH"), f"{candidate_id}.pdf")
if os.path.exists(cv_path):
    st.download_button("Download CV", open(cv_path, "rb"), file_name=f"{candidate_id}.pdf")

def interviewer_view():
    st.header("Interviewer Dashboard")

    # Search section
    st.subheader("Find Candidates")
    search_query = st.text_input("Search by name or email", placeholder="Enter name or email...")

    # Get candidates
    try:
        if search_query.strip():
            candidates = search_candidates_by_name_or_email(search_query.strip())
            st.info(f"Found {len(candidates)} candidate(s) matching '{search_query}'")
        else:
            candidates = search_candidates_by_name_or_email("")  # Get recent candidates
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

                        interviews = get_all_interviews()
                        st.table(interviews)

                        # Display key fields
                        if isinstance(form_data, dict):
                            skills = form_data.get('skills', 'Not specified')
                            experience = form_data.get('experience', 'Not specified')
                            education = form_data.get('education', 'Not specified')
                            st.write(f"**Skills:** {skills}")
                            st.write(f"**Experience:** {experience}")
                            st.write(f"**Education:** {education}")
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
                            interview_id = create_interview(
                                candidate['candidate_id'],
                                scheduled_datetime,
                                interviewer_name.strip(),
                                result if result else "scheduled",
                                notes.strip()
                            )

                            if interview_id:
                                st.success(f"Interview saved successfully! (ID: {interview_id})")
                                st.rerun()
                            else:
                                st.error("Failed to save interview")

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