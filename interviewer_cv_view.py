import streamlit as st
import os
from cv_display import display_cv_from_sheet_by_candidate_id
from utils_update import get_google_sheet_row_by_candidate_id

def interviewer_cv_view():
    """
    Interviewer view for displaying CVs by Candidate ID.
    This view allows the interviewer to:
    1. Enter a Candidate ID
    2. View the candidate's information from the Google Sheet
    3. View the candidate's CV
    """
    st.title("👁️ Candidate CV Viewer")
    
    # Get interviewer email from session state or ask for it
    if "interviewer_email" not in st.session_state:
        st.session_state.interviewer_email = st.text_input("Your Email (for logging purposes)")
    
    interviewer_email = st.session_state.interviewer_email
    
    # Candidate ID input
    st.subheader("Enter Candidate ID")
    candidate_id = st.text_input("Candidate ID", key="interviewer_candidate_id_input")
    
    if not candidate_id:
        st.warning("Please enter a Candidate ID to view the CV.")
        return
    
    # Display candidate information and CV
    if st.button("View CV"):
        # Fetch candidate data from Google Sheet
        with st.spinner("Fetching candidate data..."):
            success, result = get_google_sheet_row_by_candidate_id(candidate_id)
        
        if not success:
            st.error(f"Error: {result}")
            return
        
        # Display candidate information
        st.subheader("Candidate Information")
        
        # Create a clean display of candidate information
        info_cols = st.columns(2)
        
        with info_cols[0]:
            st.write("### Basic Details")
            
            if "Full Name( First-middle-last)" in result:
                st.info(f"**Name:** {result['Full Name( First-middle-last)']}")
            
            if "Email Address" in result:
                st.info(f"**Email:** {result['Email Address']}")
            
            if "Phone number" in result:
                st.info(f"**Phone:** {result['Phone number']}")
        
        with info_cols[1]:
            st.write("### Additional Information")
            
            if "Highest Qualification" in result:
                st.info(f"**Qualification:** {result['Highest Qualification']}")
            
            if "Work Experience " in result:
                st.info(f"**Experience:** {result['Work Experience ']}")
            
            if "Referral " in result:
                st.info(f"**Referral:** {result['Referral ']}")
        
        # Display CV
        st.subheader("Candidate CV")
        
        # Get candidate name for display
        candidate_name = result.get("Full Name( First-middle-last)", f"Candidate {candidate_id}")
        
        # Display the CV using the function from cv_display.py
        display_cv_from_sheet_by_candidate_id(candidate_id, interviewer_email, candidate_name)

def add_to_interviewer_view():
    """
    Add the CV view to the main interviewer view.
    This function should be called from interviewer.py.
    """
    # Update the interviewer_view function in interviewer.py to include this option
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Schedule", "View Candidates", "View CV by ID"])
    
    # Show the selected page
    if page == "View CV by ID":
        interviewer_cv_view()
    # Other pages are handled by the original interviewer_view function

# For testing purposes
if __name__ == "__main__":
    interviewer_cv_view()