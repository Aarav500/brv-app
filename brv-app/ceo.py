import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime

from oracle_candidates import get_all_candidates, get_candidate_by_id, get_all_users

def ceo_view():
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Dashboard", "All Candidates", "Interview Results", "User Management"])

    if page == "Dashboard":
        ceo_dashboard_page()
    elif page == "All Candidates":
        ceo_candidates_page()
    elif page == "Interview Results":
        ceo_results_page()
    elif page == "User Management":
        ceo_users_page()

def ceo_dashboard_page():
    st.title("📊 CEO Dashboard - BRV")
    
    # Get all candidates from Oracle database
    candidates = get_all_candidates()
    
    if not candidates:
        st.warning("No candidate data available.")
        return
    
    # Create DataFrame for display
    df = pd.DataFrame(candidates)
    
    # Show metrics
    total = len(df)
    passed = len(df[df["interview_status"] == "Pass"]) if "interview_status" in df.columns else 0
    failed = len(df[df["interview_status"] == "Fail"]) if "interview_status" in df.columns else 0
    hold = len(df[df["interview_status"] == "Hold"]) if "interview_status" in df.columns else 0
    scheduled = len(df[df["interview_status"] == "Scheduled"]) if "interview_status" in df.columns else 0
    not_scheduled = len(df[df["interview_status"] == "Not Scheduled"]) if "interview_status" in df.columns else 0
    
    st.subheader("📈 Summary")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Candidates", total)
    col2.metric("Interviews Scheduled", scheduled)
    col3.metric("Not Yet Scheduled", not_scheduled)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Passed", passed)
    col2.metric("Failed", failed)
    col3.metric("On Hold", hold)
    
    # CV statistics
    cv_uploaded = len(df[df["cv_status"] == "Uploaded"]) if "cv_status" in df.columns else 0
    cv_not_uploaded = len(df[df["cv_status"] == "Not Uploaded"]) if "cv_status" in df.columns else 0
    
    st.subheader("📄 CV Status")
    col1, col2 = st.columns(2)
    col1.metric("CV Uploaded", cv_uploaded)
    col2.metric("CV Not Uploaded", cv_not_uploaded)
    
    # Optional Filter
    st.subheader("🔍 Filter")
    status_filter = st.selectbox("Filter by status", ["All", "Pass", "Fail", "Hold", "Scheduled", "Not Scheduled"])
    
    # Create display DataFrame with selected columns
    display_columns = ["id", "name", "email", "phone", "interview_status", "cv_status", "interviewer_name"]
    df_display = df[display_columns] if all(col in df.columns for col in display_columns) else df
    
    if status_filter != "All" and "interview_status" in df.columns:
        df_display = df_display[df_display["interview_status"] == status_filter]
    
    # Display table
    st.subheader("📋 Candidate Table")
    st.dataframe(df_display, use_container_width=True)
    
    # Optional export
    csv = df_display.to_csv(index=False).encode('utf-8')
    st.download_button("📤 Download CSV", csv, "candidates.csv", "text/csv")

def ceo_candidates_page():
    st.title("All Candidates")
    
    # Fetch all candidates
    candidates = get_all_candidates()
    
    if not candidates:
        st.info("No candidates registered yet.")
        return
    
    # Convert to DataFrame for display
    df = pd.DataFrame(candidates)
    
    # Filters
    if not df.empty and 'interview_status' in df.columns:
        status_options = df['interview_status'].unique().tolist()
        status_filter = st.multiselect(
            "Filter by Status",
            options=status_options,
            default=status_options
        )
        
        filtered_df = df[df['interview_status'].isin(status_filter)]
        st.dataframe(filtered_df)
        
        # Select candidate to view details
        if not filtered_df.empty:
            selected_candidate = st.selectbox(
                "Select Candidate to View Details", 
                [f"ID {row['id']} - {row['name']}" for _, row in filtered_df.iterrows()]
            )
            
            if selected_candidate:
                # Extract ID from selection
                candidate_id = int(selected_candidate.split(" - ")[0].replace("ID ", ""))
                
                # Get candidate details
                candidate = get_candidate_by_id(candidate_id)
                
                if candidate:
                    # Display candidate details
                    st.subheader(f"Candidate: {candidate['name']}")
                    
                    # Basic info
                    st.write("### Basic Information")
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
                    
                    # Skills and experience
                    st.write("### Skills and Experience")
                    st.write(f"**Skills:** {candidate.get('skills', 'Not provided')}")
                    
                    if candidate.get('experience'):
                        st.write("**Experience:**")
                        st.write(candidate['experience'])
                    
                    if candidate.get('education'):
                        st.write("**Education:**")
                        st.write(candidate['education'])
                    
                    # Display CV if available
                    if candidate.get('resume_url') or candidate.get('cv_url'):
                        st.write("### Resume")
                        resume_url = candidate.get('resume_url') or candidate.get('cv_url')
                        st.write(f"CV URL: {resume_url}")
                        
                        # In a real implementation, we would add a button to download the CV
                        if st.button("Download CV"):
                            from cloud_storage import download_cv
                            cv_content = download_cv(resume_url)
                            # This would normally download the file, but for now we just show a success message
                            st.success("CV downloaded successfully (simulated)")
                    
                    # Display interview details if available
                    if candidate.get('interview_status') != 'Not Scheduled':
                        st.write("### Interview Details")
                        st.write(f"**Status:** {candidate.get('interview_status', 'Not Scheduled')}")
                        st.write(f"**Interviewer:** {candidate.get('interviewer_name', 'Not assigned')}")
                        
                        if candidate.get('interview_date'):
                            st.write(f"**Interview Date:** {candidate.get('interview_date')}")
                        
                        if candidate.get('interview_feedback'):
                            st.write("**Feedback:**")
                            try:
                                # Try to parse as JSON
                                feedback_data = json.loads(candidate.get('interview_feedback'))
                                for key, value in feedback_data.items():
                                    st.write(f"**{key.replace('_', ' ').title()}:** {value}")
                            except:
                                # Display as plain text
                                st.write(candidate.get('interview_feedback'))
    else:
        st.info("No candidate data available.")

def ceo_results_page():
    st.title("Interview Results")
    
    # Fetch all candidates with interviews
    candidates = get_all_candidates()
    
    if not candidates:
        st.info("No candidates registered yet.")
        return
    
    # Filter for candidates with interviews
    interviews = [c for c in candidates if c.get('interview_status') != 'Not Scheduled']
    
    if not interviews:
        st.info("No interviews conducted yet.")
        return
    
    # Convert to DataFrame for display
    df = pd.DataFrame(interviews)
    
    # Filters
    if not df.empty:
        # Status filter
        if 'interview_status' in df.columns:
            status_options = df['interview_status'].unique().tolist()
            status_filter = st.multiselect(
                "Filter by Status",
                options=status_options,
                default=status_options
            )
            df = df[df['interview_status'].isin(status_filter)]
        
        # Display filtered DataFrame
        display_columns = ["id", "name", "email", "interview_status", "interviewer_name", "interview_date"]
        display_df = df[display_columns] if all(col in df.columns for col in display_columns) else df
        st.dataframe(display_df)
        
        # Select interview to view details
        if not df.empty:
            selected_interview = st.selectbox(
                "Select Interview to View Details", 
                [f"ID {row['id']} - {row['name']}" for _, row in df.iterrows()]
            )
            
            if selected_interview:
                # Extract ID from selection
                candidate_id = int(selected_interview.split(" - ")[0].replace("ID ", ""))
                
                # Get candidate details
                candidate = get_candidate_by_id(candidate_id)
                
                if candidate:
                    # Display interview details
                    st.subheader(f"Interview Details: {candidate['name']}")
                    st.write(f"**Interviewer:** {candidate.get('interviewer_name', 'Not assigned')}")
                    st.write(f"**Interview Date:** {candidate.get('interview_date', 'Unknown')}")
                    st.write(f"**Status:** {candidate.get('interview_status', 'Unknown')}")
                    st.write(f"**Result:** {candidate.get('interview_result', candidate.get('interview_status', 'Unknown'))}")
                    
                    # Display feedback
                    st.write("**Feedback:**")
                    if candidate.get('interview_feedback'):
                        try:
                            # Try to parse as JSON
                            feedback_data = json.loads(candidate.get('interview_feedback'))
                            for key, value in feedback_data.items():
                                st.write(f"**{key.replace('_', ' ').title()}:** {value}")
                        except:
                            # Display as plain text
                            st.write(candidate.get('interview_feedback'))
                    else:
                        st.write("No feedback recorded")
                    
                    # Display candidate details
                    st.subheader("Candidate Information")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**ID:** {candidate['id']}")
                        st.write(f"**Name:** {candidate['name']}")
                        st.write(f"**Email:** {candidate['email']}")
                        st.write(f"**Phone:** {candidate.get('phone', 'Not provided')}")
                    
                    with col2:
                        st.write(f"**CV Status:** {candidate.get('cv_status', 'Not Uploaded')}")
                        st.write(f"**Created By:** {candidate.get('created_by', 'Unknown')}")
                        st.write(f"**Last Updated:** {candidate.get('updated_at', 'Unknown')}")
    else:
        st.info("No interview data available after filtering.")

def ceo_users_page():
    st.title("User Management")
    
    # Fetch all users
    users = get_all_users()
    
    if not users:
        st.info("No users found.")
        return
    
    # Convert to DataFrame for display
    df = pd.DataFrame(users)
    
    # Display users table
    st.subheader("All Users")
    display_columns = ["id", "email", "role", "created_at"]
    display_df = df[display_columns] if all(col in df.columns for col in display_columns) else df
    st.dataframe(display_df)
    
    # User statistics
    if 'role' in df.columns:
        role_counts = df['role'].value_counts()
        
        st.subheader("User Statistics")
        col1, col2, col3 = st.columns(3)
        
        col1.metric("Total Users", len(df))
        col2.metric("CEOs", role_counts.get('ceo', 0))
        col3.metric("Interviewers", role_counts.get('interviewer', 0))
        
        col1, col2 = st.columns(2)
        col1.metric("Receptionists", role_counts.get('receptionist', 0))
        col2.metric("Other Roles", len(df) - role_counts.get('ceo', 0) - role_counts.get('interviewer', 0) - role_counts.get('receptionist', 0))

# For testing the CEO view directly
if __name__ == "__main__":
    import os
    
    st.set_page_config(
        page_title="CEO View - BRV Applicant System",
        page_icon="📋",
        layout="wide"
    )
    
    # Initialize session state for testing
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = True
    if 'user_id' not in st.session_state:
        st.session_state.user_id = 1
    if 'email' not in st.session_state:
        st.session_state.email = "ceo@bluematrixit.com"
    if 'user_role' not in st.session_state:
        st.session_state.user_role = "ceo"
    
    ceo_view()