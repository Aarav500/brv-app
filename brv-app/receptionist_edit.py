import streamlit as st
import pandas as pd
import os
from mysql_db import get_candidate_by_id, update_candidate
from resume_handler import display_resume_from_url, is_google_drive_link

def receptionist_edit_view():
    """
    Receptionist view for editing candidate data by Candidate ID.
    This view allows the receptionist to:
    1. Enter a Candidate ID
    2. View the candidate's information from the Google Sheet
    3. Edit fields including 'Upload your Resume'
    4. Update the Google Sheet
    """
    st.title("📝 Edit Candidate Information")
    
    # Candidate ID input
    st.subheader("Enter Candidate ID")
    candidate_id = st.text_input("Candidate ID", key="candidate_id_input")
    
    if not candidate_id:
        st.warning("Please enter a Candidate ID to continue.")
        return
    
    # Fetch candidate data from MySQL database
    with st.spinner("Fetching candidate data..."):
        try:
            # Convert candidate_id to integer
            candidate_id_int = int(candidate_id)
            result = get_candidate_by_id(candidate_id_int)
            success = result is not None
        except ValueError:
            success = False
            result = "Invalid Candidate ID. Please enter a numeric ID."
    
    if not success:
        st.error(f"Error: Candidate not found or {result}")
        return
    
    # Display and edit candidate information
    st.subheader("Candidate Information")
    
    # Create a form for editing
    with st.form(key="edit_candidate_form"):
        # Display basic information (non-editable)
        st.write("### Basic Information")
        
        # Display creation timestamp if available
        if "created_at" in result:
            st.info(f"**Submission Time:** {result['created_at']}")
        
        if "email" in result:
            st.info(f"**Email:** {result['email']}")
        
        if "name" in result:
            st.info(f"**Name:** {result['name']}")
        
        # Editable fields
        st.write("### Editable Fields")
        
        # Resume URL
        current_resume_url = result.get("resume_url", "")
        resume_url = st.text_input("Resume URL", value=current_resume_url)
        
        # Display current resume if available
        if current_resume_url:
            st.write("### Current Resume")
            if is_google_drive_link(current_resume_url):
                display_resume_from_url(current_resume_url, result.get("name", "Candidate"))
            else:
                st.warning("Current resume URL is not a valid Google Drive link.")
        
        # Additional fields that might be useful to edit
        phone = st.text_input("Phone Number", value=result.get("phone", ""))
        
        # Skills and experience fields
        skills = st.text_area("Skills", value=result.get("skills", ""))
        experience = st.text_area("Experience", value=result.get("experience", ""))
        education = st.text_area("Education", value=result.get("education", ""))
        
        # Add more editable fields as needed
        
        # Submit button
        submit_button = st.form_submit_button(label="Update Candidate Information")
    
    # Handle form submission
    if submit_button:
        # Prepare updates
        updates = {
            "resume_url": resume_url,
            "phone": phone,
            "skills": skills,
            "experience": experience,
            "education": education
        }
        
        # Remove unchanged fields
        updates = {k: v for k, v in updates.items() if v != result.get(k, "")}
        
        if not updates:
            st.warning("No changes detected. Nothing to update.")
            return
        
        # Update candidate in MySQL database
        with st.spinner("Updating candidate information..."):
            try:
                # Convert candidate_id to integer
                candidate_id_int = int(candidate_id)
                update_success = update_candidate(candidate_id_int, updates)
                update_message = "Candidate information updated successfully"
            except ValueError:
                update_success = False
                update_message = "Invalid Candidate ID. Please enter a numeric ID."
        
        if update_success:
            st.success(f"Successfully updated candidate information: {update_message}")
            
            # Refresh the data
            try:
                # Convert candidate_id to integer
                candidate_id_int = int(candidate_id)
                result = get_candidate_by_id(candidate_id_int)
                success = result is not None
                if success:
                    st.info("Refreshed candidate data.")
            except ValueError:
                success = False
            
            # Display updated resume if available
            if resume_url and resume_url != current_resume_url:
                st.write("### Updated Resume")
                if is_google_drive_link(resume_url):
                    display_resume_from_url(resume_url, result.get("Full Name( First-middle-last)", "Candidate"))
                else:
                    st.warning("Updated resume URL is not a valid Google Drive link.")
        else:
            st.error(f"Error updating candidate information: {update_message}")

def add_to_receptionist_view():
    """
    Add the edit view to the main receptionist view.
    This function should be called from receptionist.py.
    """
    # Update the receptionist_view function in receptionist.py to include this option
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["New Applicant", "View Profiles", "Candidate ID Panel", "Edit Candidate"])
    
    # Show the selected page
    if page == "Edit Candidate":
        receptionist_edit_view()
    # Other pages are handled by the original receptionist_view function

# For testing purposes
if __name__ == "__main__":
    receptionist_edit_view()