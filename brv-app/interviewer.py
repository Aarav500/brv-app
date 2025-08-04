import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime, timedelta
import uuid

from mysql_db import get_all_candidates, get_candidate_by_id, update_candidate
from cloud_storage import download_cv

def interviewer_view():
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Candidate Profiles", "Schedule Interview", "My Interviews", "View CV by ID"])

    # Display resume link if available in session state
    if st.session_state.get("resume_url"):
        st.sidebar.markdown("### Your Resume")
        resume_url = st.session_state.resume_url

        # Check if it's a full URL or just a file ID
        if "drive.google.com" in resume_url:
            # It's already a full URL
            st.sidebar.markdown(f"[📄 View Resume]({resume_url})", unsafe_allow_html=True)
        else:
            # Assume it's a file ID
            st.sidebar.markdown(f"[📄 View Resume](https://drive.google.com/file/d/{resume_url}/view)", unsafe_allow_html=True)

    if page == "Candidate Profiles":
        interviewer_candidates_page()
    elif page == "Schedule Interview":
        interviewer_schedule_page()
    elif page == "My Interviews":
        interviewer_interviews_page()
    elif page == "View CV by ID":
        # Import here to avoid circular imports
        from interviewer_cv_view import interviewer_cv_view
        interviewer_cv_view()

def interviewer_candidates_page():
    st.title("👨‍💼 Interviewer Panel - BRV")
    st.header("📋 Candidate Profiles")

    candidates = get_all_candidates()

    if not candidates:
        st.warning("No candidates found.")
        return

    candidate_options = [f"ID {c['id']} - {c['name']}" for c in candidates]
    selected = st.selectbox("Select a candidate to view profile", candidate_options)

    if selected:
        selected_id = int(selected.split(" - ")[0].replace("ID ", ""))
        selected_candidate = next((c for c in candidates if c['id'] == selected_id), None)

        if selected_candidate:
            st.subheader(f"Profile: {selected_candidate['name']}")

            # Display candidate information
            st.write("### Candidate Information")
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**ID:** {selected_candidate['id']}")
                st.write(f"**Name:** {selected_candidate['name']}")
                st.write(f"**Email:** {selected_candidate['email']}")
                st.write(f"**Phone:** {selected_candidate.get('phone', 'Not provided')}")
            
            with col2:
                st.write(f"**Interview Status:** {selected_candidate.get('interview_status', 'Not Scheduled')}")
                st.write(f"**CV Status:** {selected_candidate.get('cv_status', 'Not Uploaded')}")
                st.write(f"**Created By:** {selected_candidate.get('created_by', 'Unknown')}")
                st.write(f"**Last Updated:** {selected_candidate.get('updated_at', 'Unknown')}")
            
            # Display skills and experience
            st.write("### Skills and Experience")
            st.write(f"**Skills:** {selected_candidate.get('skills', 'Not provided')}")
            
            if selected_candidate.get('experience'):
                st.write("**Experience:**")
                st.write(selected_candidate['experience'])
            
            if selected_candidate.get('education'):
                st.write("**Education:**")
                st.write(selected_candidate['education'])

            # Show resume using resume_handler
            from resume_handler import display_resume, display_resume_from_url

            resume_url = selected_candidate.get('resume_url') or selected_candidate.get('cv_url')
            candidate_name = selected_candidate['name']

            if resume_url:
                display_resume_from_url(resume_url, candidate_name)
            else:
                st.warning("⚠️ No resume available for this candidate.")

            # Interview feedback form
            st.write("### Interview Feedback")
            interviewer_name = st.text_input("Your Name")
            feedback = st.text_area("Interview Notes / Feedback")
            result = st.selectbox("Final Decision", ["Pass", "Fail", "Hold"])

            if st.button("✅ Submit Feedback"):
                if not interviewer_name or not feedback:
                    st.warning("Please fill in all feedback fields.")
                    return

                # Update candidate with interview feedback
                update_data = {
                    'interview_status': result,
                    'interview_feedback': feedback,
                    'interviewer_name': interviewer_name,
                    'interview_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                success = update_candidate(selected_candidate['id'], update_data)
                
                if success:
                    st.success("Interview feedback submitted successfully!")
                    st.rerun()
                else:
                    st.error("Failed to submit interview feedback. Please try again.")

def interviewer_schedule_page():
    st.title("Schedule New Interview")

    # Fetch candidates who don't have interviews scheduled
    candidates = get_all_candidates()
    pending_candidates = [c for c in candidates if c.get('interview_status', 'Not Scheduled') == 'Not Scheduled']

    if not pending_candidates:
        st.warning("No candidates available for scheduling interviews.")
        return

    # Get current user as interviewer
    interviewer_email = st.session_state.email
    interviewer_id = st.session_state.user_id

    with st.form("schedule_interview_form"):
        # Select candidate
        candidate_options = [f"ID {c['id']} - {c['name']}" for c in pending_candidates]
        selected_candidate = st.selectbox("Select Candidate", candidate_options)

        # Select date and time
        interview_date = st.date_input("Interview Date", datetime.now() + timedelta(days=1))
        interview_time = st.time_input("Interview Time", datetime.now().time())

        # Combine date and time
        interview_datetime = datetime.combine(interview_date, interview_time)

        # Additional notes
        notes = st.text_area("Notes (Optional)")

        submit = st.form_submit_button("Schedule Interview")

        if submit:
            # Get candidate ID
            candidate_id = int(selected_candidate.split(" - ")[0].replace("ID ", ""))

            # Create interview record by updating candidate
            update_data = {
                'interview_status': 'Scheduled',
                'interview_scheduled_time': interview_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                'interview_notes': notes,
                'interviewer_id': interviewer_id,
                'interviewer_email': interviewer_email
            }
            
            success = update_candidate(candidate_id, update_data)
            
            if success:
                # Get candidate name
                candidate_name = next((c['name'] for c in pending_candidates if c['id'] == candidate_id), "Unknown")
                
                st.success(f"Interview scheduled successfully for {candidate_name} with {interviewer_email} on {interview_datetime.strftime('%Y-%m-%d %H:%M')}")
                st.rerun()
            else:
                st.error("Failed to schedule interview. Please try again.")

def interviewer_interviews_page():
    st.title("My Interviews")

    # Tabs for scheduled and past interviews
    tab1, tab2 = st.tabs(["Scheduled Interviews", "Past Interviews"])

    # Get current user ID
    interviewer_id = st.session_state.user_id
    interviewer_email = st.session_state.email

    # Get all candidates
    all_candidates = get_all_candidates()

    with tab1:
        # Filter for scheduled interviews assigned to this interviewer
        scheduled_interviews = [
            c for c in all_candidates 
            if c.get('interview_status') == 'Scheduled' and 
               c.get('interviewer_id') == interviewer_id
        ]

        if scheduled_interviews:
            # Create a list of dictionaries for the DataFrame
            interviews_list = []
            for candidate in scheduled_interviews:
                # Format date
                scheduled_time = candidate.get('interview_scheduled_time')
                if scheduled_time:
                    try:
                        scheduled_time = datetime.strptime(scheduled_time, "%Y-%m-%d %H:%M:%S")
                        formatted_time = scheduled_time.strftime("%Y-%m-%d %H:%M")
                    except:
                        formatted_time = scheduled_time
                else:
                    formatted_time = "Not scheduled"

                interviews_list.append({
                    "ID": candidate['id'],
                    "Candidate": candidate['name'],
                    "Scheduled Time": formatted_time,
                    "Status": candidate.get('interview_status', 'Not Scheduled')
                })

            # Display as DataFrame
            df = pd.DataFrame(interviews_list)
            st.dataframe(df)

            # Select interview to conduct
            if interviews_list:
                selected_id = st.selectbox("Select Interview to Conduct", 
                                         [f"{i['ID']} - {i['Candidate']}" for i in interviews_list])

                if selected_id:
                    # Extract ID from selection
                    candidate_id = int(selected_id.split(" - ")[0])

                    # Get candidate details
                    candidate = get_candidate_by_id(candidate_id)

                    if candidate:
                        st.subheader(f"Interview with {candidate['name']}")

                        # Display candidate info
                        st.write("### Candidate Information")
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**ID:** {candidate['id']}")
                            st.write(f"**Name:** {candidate['name']}")
                            st.write(f"**Email:** {candidate['email']}")
                            st.write(f"**Phone:** {candidate.get('phone', 'Not provided')}")
                        
                        with col2:
                            st.write(f"**Interview Status:** {candidate.get('interview_status', 'Not Scheduled')}")
                            st.write(f"**CV Status:** {candidate.get('cv_status', 'Not Uploaded')}")
                            st.write(f"**Created By:** {candidate.get('created_by', 'Unknown')}")
                            st.write(f"**Last Updated:** {candidate.get('updated_at', 'Unknown')}")
                        
                        # Display skills and experience
                        st.write("### Skills and Experience")
                        st.write(f"**Skills:** {candidate.get('skills', 'Not provided')}")
                        
                        if candidate.get('experience'):
                            st.write("**Experience:**")
                            st.write(candidate['experience'])
                        
                        if candidate.get('education'):
                            st.write("**Education:**")
                            st.write(candidate['education'])

                        # Show resume if available
                        resume_url = candidate.get('resume_url') or candidate.get('cv_url')
                        if resume_url:
                            from resume_handler import display_resume_from_url
                            display_resume_from_url(resume_url, candidate['name'])
                        else:
                            st.warning("⚠️ No resume available for this candidate.")

                        # First Interview Evaluation Form
                        st.header("📝 First Interview Evaluation")

                        with st.form("first_interview_form"):
                            age = st.text_input("Age")

                            no_festival_leaves = st.radio("Open to Working During Festivals?", ["Yes", "No"])
                            attitude = st.selectbox("Attitude", ["Positive", "Neutral", "Negative"])
                            project_fit = st.text_input("Suitable for Which Project?")
                            education = st.text_input("Education")
                            family_background = st.text_area("Family Background")

                            work_experience = st.text_area("Past Work Experience and Past Salary")
                            owns_pc = st.radio("Own PC or Laptop?", ["Yes", "No"])

                            night_shift_continuous = st.radio("Willing for Continuous Night Shift?", ["Yes", "No"])
                            night_shift_rotational = st.radio("Willing for Rotational Night Shift?", ["Yes", "No"])

                            profile_fit = st.selectbox("Profile Fit", ["Yes", "No", "Maybe"])
                            grasping = st.selectbox("Grasping Ability", ["Excellent", "Good", "Average", "Poor"])

                            additional_comments = st.text_area("Additional Comments (Optional)")

                            result = st.selectbox("Final Decision", ["Pass", "Fail", "Hold"])

                            submit = st.form_submit_button("Save Interview Feedback")

                            if submit:
                                # Prepare feedback data
                                feedback_data = {
                                    "age": age,
                                    "no_festival_leaves": no_festival_leaves,
                                    "attitude": attitude,
                                    "project_fit": project_fit,
                                    "education": education,
                                    "family_background": family_background,
                                    "work_experience": work_experience,
                                    "owns_pc": owns_pc,
                                    "night_shift_continuous": night_shift_continuous,
                                    "night_shift_rotational": night_shift_rotational,
                                    "profile_fit": profile_fit,
                                    "grasping": grasping,
                                    "comments": additional_comments
                                }

                                # Save interview feedback
                                feedback = f"First interview completed. Decision: {result}. See detailed evaluation in interview_feedback field."
                                
                                # Update candidate with interview feedback
                                update_data = {
                                    'interview_status': result,
                                    'interview_feedback': json.dumps(feedback_data),
                                    'interview_result': result,
                                    'interviewer_name': interviewer_email,
                                    'interview_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                }
                                
                                success = update_candidate(candidate_id, update_data)
                                
                                if success:
                                    st.success("✅ First interview feedback saved successfully!")
                                    st.rerun()
                                else:
                                    st.error("Failed to save interview feedback. Please try again.")
        else:
            st.info("No scheduled interviews.")

    with tab2:
        # Filter for completed interviews conducted by this interviewer
        completed_interviews = [
            c for c in all_candidates 
            if c.get('interview_status') in ['Pass', 'Fail', 'Hold'] and 
               c.get('interviewer_id') == interviewer_id
        ]

        if completed_interviews:
            # Create a list of dictionaries for the DataFrame
            interviews_list = []
            for candidate in completed_interviews:
                # Format date
                interview_date = candidate.get('interview_date')
                if interview_date:
                    try:
                        interview_date = datetime.strptime(interview_date, "%Y-%m-%d %H:%M:%S")
                        formatted_date = interview_date.strftime("%Y-%m-%d %H:%M")
                    except:
                        formatted_date = interview_date
                else:
                    formatted_date = "Unknown"

                interviews_list.append({
                    "ID": candidate['id'],
                    "Candidate": candidate['name'],
                    "Interview Date": formatted_date,
                    "Result": candidate.get('interview_result', 'Unknown'),
                    "Feedback": candidate.get('interview_feedback', '')[:50] + "..." if candidate.get('interview_feedback') and len(candidate.get('interview_feedback', '')) > 50 else candidate.get('interview_feedback', '')
                })

            # Display as DataFrame
            df = pd.DataFrame(interviews_list)
            st.dataframe(df)

            # Option to view full feedback
            if interviews_list:
                selected_id = st.selectbox("Select Interview to View Details", 
                                         [f"{i['ID']} - {i['Candidate']}" for i in interviews_list],
                                         key="past_interviews")

                if selected_id:
                    # Extract ID from selection
                    candidate_id = int(selected_id.split(" - ")[0])

                    # Get candidate details
                    candidate = get_candidate_by_id(candidate_id)

                    if candidate:
                        st.subheader(f"Interview with {candidate['name']}")
                        st.write(f"**Interview Date:** {candidate.get('interview_date', 'Unknown')}")
                        st.write(f"**Result:** {candidate.get('interview_result', 'Unknown')}")
                        st.write(f"**Feedback:**")
                        st.write(candidate.get('interview_feedback', 'No feedback recorded'))
        else:
            st.info("No past interviews.")

# For testing the interviewer view directly
if __name__ == "__main__":
    import os
    import json

    st.set_page_config(
        page_title="Interviewer View - BRV Applicant System",
        page_icon="📋",
        layout="wide"
    )

    # Initialize session state for testing
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = True
    if 'user_id' not in st.session_state:
        st.session_state.user_id = 1
    if 'email' not in st.session_state:
        st.session_state.email = "interviewer@bluematrixit.com"
    if 'user_role' not in st.session_state:
        st.session_state.user_role = "interviewer"

    interviewer_view()