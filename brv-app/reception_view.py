import streamlit as st
import pandas as pd
import os
from datetime import datetime

from oracle_candidates import get_candidate_by_id, get_candidate_by_name_and_id, get_all_candidates, search_candidates
from candidate_view import edit_candidate_form
from cloud_storage import download_cv

def reception_view():
    """
    Main view for receptionists to manage candidates
    """
    st.title("Receptionist Dashboard")
    
    # Create tabs for different receptionist functions
    tab1, tab2, tab3 = st.tabs(["Edit Candidate", "View Candidates", "New Walk-in"])
    
    # Tab 1: Edit Candidate Form
    with tab1:
        edit_candidate_access()
    
    # Tab 2: View All Candidates
    with tab2:
        view_all_candidates()
    
    # Tab 3: New Walk-in Candidate
    with tab3:
        new_walkin_candidate()

def edit_candidate_access():
    """
    Allow receptionist to access candidate edit form using Candidate ID + Name
    """
    st.header("Edit Candidate Application")
    st.write("Enter the Candidate ID and Name to access their application form.")
    
    # Create a form for entering Candidate ID and Name
    with st.form("candidate_access_form"):
        candidate_id = st.number_input("Candidate ID*", min_value=1, step=1)
        candidate_name = st.text_input("Candidate Name*", placeholder="Full name as entered in the application")
        
        submit_button = st.form_submit_button("Access Application")
        
        if submit_button:
            # Validate required fields
            if not candidate_id or not candidate_name:
                st.error("Please enter both Candidate ID and Name")
                return
            
            # Try to get the candidate by ID and name
            candidate = get_candidate_by_name_and_id(candidate_id, candidate_name)
            
            if candidate:
                # Store the candidate data in session state for editing
                st.session_state.editing_candidate = candidate
                st.success(f"Found candidate: {candidate['name']} (ID: {candidate['id']})")
                st.rerun()  # Rerun to show the edit form
            else:
                st.error("No candidate found with the provided ID and Name. Please check and try again.")
    
    # If we have a candidate to edit in session state, show the edit form
    if 'editing_candidate' in st.session_state:
        # Show a button to cancel editing
        if st.button("Cancel Editing"):
            del st.session_state.editing_candidate
            st.rerun()
        
        # Show the edit form
        success = edit_candidate_form(st.session_state.editing_candidate)
        
        # If the form was submitted successfully, clear the session state
        if success:
            del st.session_state.editing_candidate
            st.rerun()

def view_all_candidates():
    """
    Display a table of all candidates with filtering options
    """
    st.header("All Candidates")
    
    # Get all candidates from Oracle database
    candidates = get_all_candidates()
    
    if not candidates:
        st.info("No candidates found.")
        return
    
    # Convert to DataFrame for easier display and filtering
    df = pd.DataFrame(candidates)
    
    # Add filters
    st.subheader("Filters")
    col1, col2 = st.columns(2)
    
    with col1:
        # Filter by interview status
        status_options = ["All"] + sorted(df["interview_status"].unique().tolist())
        selected_status = st.selectbox("Interview Status", status_options)
    
    with col2:
        # Filter by CV status
        cv_options = ["All"] + sorted(df["cv_status"].unique().tolist())
        selected_cv = st.selectbox("CV Status", cv_options)
    
    # Apply filters
    filtered_df = df.copy()
    if selected_status != "All":
        filtered_df = filtered_df[filtered_df["interview_status"] == selected_status]
    if selected_cv != "All":
        filtered_df = filtered_df[filtered_df["cv_status"] == selected_cv]
    
    # Search by name or email
    search_term = st.text_input("Search by Name or Email")
    if search_term:
        # Use the search_candidates function from oracle_candidates.py
        search_results = search_candidates(search_term)
        if search_results:
            filtered_df = pd.DataFrame(search_results)
        else:
            filtered_df = pd.DataFrame()
    
    # Display the filtered DataFrame
    if not filtered_df.empty:
        # Select columns to display
        display_columns = ["id", "name", "email", "interview_status", "cv_status"]
        st.dataframe(filtered_df[display_columns], use_container_width=True)
        
        st.write(f"Showing {len(filtered_df)} of {len(df)} candidates")
        
        # Allow selecting a candidate to view details
        selected_candidate_id = st.selectbox(
            "Select a candidate to view details",
            options=filtered_df["id"].tolist(),
            format_func=lambda x: f"{filtered_df[filtered_df['id'] == x]['name'].iloc[0]} (ID: {x})"
        )
        
        if selected_candidate_id:
            view_candidate_details(selected_candidate_id)
    else:
        st.info("No candidates match the selected filters.")

def view_candidate_details(candidate_id):
    """
    Display detailed information about a selected candidate
    
    Args:
        candidate_id (int): The ID of the candidate to display
    """
    # Get the candidate data
    candidate = get_candidate_by_id(candidate_id)
    
    if not candidate:
        st.error(f"Candidate with ID {candidate_id} not found.")
        return
    
    # Display candidate details
    st.subheader(f"Candidate Details: {candidate['name']}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**ID:**", candidate['id'])
        st.write("**Name:**", candidate['name'])
        st.write("**Email:**", candidate['email'])
        st.write("**Phone:**", candidate.get('phone', 'Not provided'))
    
    with col2:
        st.write("**Interview Status:**", candidate['interview_status'])
        st.write("**CV Status:**", candidate['cv_status'])
        st.write("**Created By:**", candidate.get('created_by', 'Unknown'))
        st.write("**Last Updated:**", candidate.get('updated_at', 'Unknown'))
    
    # Display skills and experience
    st.subheader("Skills and Experience")
    st.write("**Skills:**", candidate.get('skills', 'Not provided'))
    
    if candidate.get('experience'):
        st.write("**Experience:**")
        st.write(candidate['experience'])
    
    if candidate.get('education'):
        st.write("**Education:**")
        st.write(candidate['education'])
    
    # Display CV if available
    if candidate.get('resume_url') and candidate['cv_status'] == 'Uploaded':
        st.subheader("CV")
        st.write(f"CV URL: {candidate['resume_url']}")
        
        # In a real implementation, we would add a button to download the CV
        if st.button("Download CV"):
            cv_content = download_cv(candidate['resume_url'])
            # This would normally download the file, but for now we just show a success message
            st.success("CV downloaded successfully (simulated)")
    
    # Option to edit the candidate
    if st.button("Edit Candidate"):
        st.session_state.editing_candidate = candidate
        st.rerun()

def new_walkin_candidate():
    """
    Allow receptionist to create a new walk-in candidate application
    """
    st.header("New Walk-in Candidate")
    st.write("Use this form to create a new application for a walk-in candidate.")
    
    # Add a button to show the candidate form
    if 'show_walkin_form' not in st.session_state:
        st.session_state.show_walkin_form = False
    
    if not st.session_state.show_walkin_form:
        if st.button("Create New Walk-in Application"):
            st.session_state.show_walkin_form = True
            st.rerun()
    else:
        if st.button("Cancel"):
            st.session_state.show_walkin_form = False
            st.rerun()
        
        # Import and show the candidate form
        from candidate_view import candidate_form_view
        candidate_form_view()
        
        # Reset the form state when done
        if 'candidate_form_data' in st.session_state and st.session_state.candidate_form_data.get('name') == '':
            st.session_state.show_walkin_form = False