import streamlit as st
import os
from utils import get_cv_by_candidate_id
from utils_update import get_google_sheet_row_by_candidate_id, log_cv_view_in_firestore
from resume_handler import display_resume, display_resume_from_url, is_google_drive_link, extract_file_id
import streamlit.components.v1 as components

def display_cv_by_candidate_id(candidate_id, candidate_name="Candidate"):
    """
    Display a CV based on the Candidate ID.
    
    Args:
        candidate_id (str): The candidate ID to search for
        candidate_name (str, optional): The name of the candidate for display purposes
        
    Returns:
        bool: True if CV was found and displayed, False otherwise
    """
    if not candidate_id:
        st.warning("No Candidate ID provided.")
        return False
    
    # Get the CV path using the utility function
    cv_path = get_cv_by_candidate_id(candidate_id)
    
    if cv_path:
        st.success(f"CV found for Candidate ID: {candidate_id}")
        
        # Display the CV
        display_resume(cv_path, candidate_name)
        
        # Add download button
        if os.path.exists(cv_path):
            with open(cv_path, "rb") as f:
                st.download_button(
                    label="Download CV",
                    data=f,
                    file_name=f"CV_{candidate_id}.pdf",
                    mime="application/pdf"
                )
        
        return True
    else:
        st.warning(f"CV not found for Candidate ID: {candidate_id}")
        return False

def cv_uploader_with_candidate_id(candidate_id=None):
    """
    Upload a CV and rename it based on the Candidate ID.
    
    Args:
        candidate_id (str, optional): The candidate ID to use for the filename.
            If not provided, a text input will be shown to enter it.
            
    Returns:
        bool: True if CV was uploaded successfully, False otherwise
    """
    # If candidate_id is not provided, show a text input to enter it
    if not candidate_id:
        candidate_id = st.text_input("Enter Candidate ID")
        
    if not candidate_id:
        st.warning("Please enter a Candidate ID.")
        return False
    
    # File uploader
    uploaded_file = st.file_uploader("Upload CV (PDF only)", type=["pdf"])
    
    if uploaded_file:
        # Create directory if it doesn't exist
        os.makedirs("cvs", exist_ok=True)
        
        # Standardized filename format: CV_<CandidateID>.pdf
        save_path = f"cvs/CV_{candidate_id}.pdf"
        
        # Save the file
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
            
        st.success(f"CV uploaded successfully for Candidate ID: {candidate_id}")
        
        # Display the uploaded CV
        display_resume(save_path, f"Candidate {candidate_id}")
        
        return True
    
    return False

def display_cv_from_sheet_by_candidate_id(candidate_id, interviewer_email=None, candidate_name=None):
    """
    Display a CV based on the Candidate ID by looking it up in the Google Sheet.
    This function:
    1. Fetches the row from the Google Sheet using the Candidate ID
    2. Extracts the 'Upload your Resume' link
    3. Displays the CV using the link
    4. Logs the CV view access in Firestore
    
    Args:
        candidate_id (str): The candidate ID to search for
        interviewer_email (str, optional): The email of the interviewer viewing the CV (for logging)
        candidate_name (str, optional): The name of the candidate for display purposes
        
    Returns:
        bool: True if CV was found and displayed, False otherwise
    """
    if not candidate_id:
        st.warning("No Candidate ID provided.")
        return False
    
    # Fetch the row from the Google Sheet
    with st.spinner(f"Looking up Candidate ID: {candidate_id}..."):
        success, result = get_google_sheet_row_by_candidate_id(candidate_id)
    
    if not success:
        st.error(f"Error: {result}")
        return False
    
    # Get the candidate name if not provided
    if not candidate_name and "Full Name( First-middle-last)" in result:
        candidate_name = result["Full Name( First-middle-last)"]
    elif not candidate_name:
        candidate_name = f"Candidate {candidate_id}"
    
    # Get the resume URL
    resume_url = result.get("Upload your Resume", "")
    
    if not resume_url:
        st.warning(f"No resume URL found for Candidate ID: {candidate_id}")
        return False
    
    # Display the CV
    st.success(f"CV found for Candidate ID: {candidate_id}")
    
    # Check if it's a Google Drive link
    if is_google_drive_link(resume_url):
        # Display the CV using the Google Drive link
        display_resume_from_url(resume_url, candidate_name)
        
        # Log the CV view access in Firestore if interviewer_email is provided
        if interviewer_email:
            try:
                log_success, log_message = log_cv_view_in_firestore(candidate_id, interviewer_email, resume_url)
                if not log_success:
                    st.warning(f"Failed to log CV view: {log_message}")
            except Exception as e:
                st.warning(f"Error logging CV view: {str(e)}")
        
        return True
    else:
        st.warning(f"Resume URL is not a valid Google Drive link: {resume_url}")
        
        # Try to display it anyway as a fallback
        try:
            display_resume_from_url(resume_url, candidate_name)
            
            # Log the CV view access in Firestore if interviewer_email is provided
            if interviewer_email:
                try:
                    log_success, log_message = log_cv_view_in_firestore(candidate_id, interviewer_email, resume_url)
                    if not log_success:
                        st.warning(f"Failed to log CV view: {log_message}")
                except Exception as e:
                    st.warning(f"Error logging CV view: {str(e)}")
            
            return True
        except Exception as e:
            st.error(f"Error displaying CV: {str(e)}")
            return False