import streamlit as st
import pandas as pd
from firebase_candidates import get_candidate_by_email, update_candidate
from utils import fetch_google_form_responses
from resume_handler import display_resume_from_url, is_google_drive_link

def edit_candidate_profile(candidate_email):
    """
    Edit a candidate's profile based on their email.
    
    Args:
        candidate_email (str): The email of the candidate to edit
    """
    st.title("Edit Candidate Profile")
    
    # Fetch candidate data from Firestore
    candidate_data = get_candidate_by_email(candidate_email)
    
    if not candidate_data:
        st.error(f"No candidate found with email: {candidate_email}")
        return
    
    # Fetch Google Form data to get the original form fields
    google_sheet_data = fetch_google_form_responses()
    
    # Find the candidate's row in the Google Sheet data
    candidate_row = None
    email_column = None
    
    # Find the email column
    for col in google_sheet_data.columns:
        if 'email' in col.lower():
            email_column = col
            break
    
    if email_column:
        # Find the candidate's row
        candidate_rows = google_sheet_data[google_sheet_data[email_column] == candidate_email]
        if not candidate_rows.empty:
            candidate_row = candidate_rows.iloc[0].to_dict()
    
    # If we couldn't find the candidate in Google Sheet, use Firestore data
    if not candidate_row:
        form_data = candidate_data.get('form_data', {})
        if isinstance(form_data, str):
            import json
            try:
                form_data = json.loads(form_data)
            except:
                form_data = {}
        candidate_row = form_data
    
    # Debug output
    print("======= Candidate Data Loading =======")
    print("Email:", candidate_email)
    print("Data Source:", "Google Sheet" if candidate_row else "Firestore")
    print("Available Fields:")
    for k, v in (candidate_row or {}).items():
        print(f" - {k}: {v}")
    print("===================================")
    
    # Display and edit basic info
    st.subheader("Basic Info")
    
    # Get candidate name from form data or Firestore
    candidate_name = ""
    for name_field in ["Full Name( First-middle-last)", "Full Name", "Name", "full_name"]:
        if name_field in candidate_row:
            candidate_name = candidate_row[name_field]
            break
    
    # Make name editable
    new_name = st.text_input("Candidate Name", value=candidate_name, key="name")
    
    # Display email (non-editable)
    st.text_input("Candidate Email", value=candidate_email, disabled=True)
    
    # Display CV Status
    resume_link = None
    for resume_field in ["Upload your Resume", "Resume Link", "resume_link"]:
        if resume_field in candidate_row and candidate_row[resume_field]:
            resume_link = candidate_row[resume_field]
            break
    
    if not resume_link and "resume_link" in candidate_data:
        resume_link = candidate_data["resume_link"]
    
    cv_status = "Uploaded ✅" if resume_link else "Missing ❌"
    st.text(f"CV Status: {cv_status}")
    
    # Display Interview Status (non-editable, synced with Interview tab)
    interview_status = candidate_data.get("status", "Not Set")
    st.text(f"Interview Status (Synced): {interview_status}")
    
    # Display Google Form fields in exact order
    st.subheader("Form Details")
    
    # Get all form fields excluding non-editable ones
    non_editable_fields = ["Timestamp", "Email Address", "Email", "email", "Interview Notes"]
    editable_fields = {}
    
    # If we have Google Sheet data, use its order
    if candidate_row:
        for field, value in candidate_row.items():
            if field not in non_editable_fields:
                editable_fields[field] = value
    
    # Create form inputs for each field
    updated_fields = {}
    for field, value in editable_fields.items():
        # Skip the name field as we already have it above
        if field in ["Full Name( First-middle-last)", "Full Name", "Name", "full_name"]:
            continue
        
        # Skip the resume field as we'll handle it separately
        if field in ["Upload your Resume", "Resume Link", "resume_link"]:
            continue
        
        # Create text input for each field
        updated_value = st.text_input(field, value=str(value) if value is not None else "", key=field)
        updated_fields[field] = updated_value
    
    # Handle resume link separately
    st.subheader("Resume")
    new_resume_link = st.text_input("Resume Link", value=resume_link if resume_link else "", key="resume")
    
    # Option to upload a new resume if missing
    if not resume_link or not new_resume_link:
        st.write("No resume uploaded. You can upload one now:")
        uploaded_file = st.file_uploader("Upload Resume", type=["pdf", "docx", "doc"])
        
        if uploaded_file:
            # Here you would implement the logic to save the file to Google Drive
            # and get a link. For now, we'll just acknowledge the upload.
            st.success("Resume uploaded successfully! (Note: In a real implementation, this would save to Google Drive)")
            new_resume_link = f"https://drive.google.com/file/d/example/{uploaded_file.name}"
    
    # Display resume preview if available
    if new_resume_link and is_google_drive_link(new_resume_link):
        st.subheader("Resume Preview")
        display_resume_from_url(new_resume_link, new_name)
    
    # Save button
    if st.button("Save Changes"):
        # Prepare updated data
        updated_data = {}
        
        # Update name in the appropriate field
        for name_field in ["Full Name( First-middle-last)", "Full Name", "Name", "full_name"]:
            if name_field in candidate_row:
                updated_fields[name_field] = new_name
                break
        
        # Update resume link
        if new_resume_link != resume_link:
            updated_data["resume_link"] = new_resume_link
        
        # Update form data
        updated_data["form_data"] = {**candidate_row, **updated_fields}
        
        # Debug output
        print("======= Candidate Updated =======")
        print("Email:", candidate_email)
        print("Updated Fields:")
        for k, v in updated_fields.items():
            if k in candidate_row and str(candidate_row[k]) != str(v):
                print(f" - {k}: {v} (was: {candidate_row[k]})")
        if new_resume_link != resume_link:
            print(f" - Resume Link: {new_resume_link}")
        print("=================================")
        
        # Update candidate in Firestore
        candidate_id = candidate_data.get("id")
        if candidate_id:
            success = update_candidate(candidate_id, hr_data=updated_data, resume_link=new_resume_link)
            if success:
                st.success("Candidate data updated successfully!")
            else:
                st.error("Failed to update candidate data.")
        else:
            st.error("Candidate ID not found. Cannot update.")

def edit_profile():
    """
    Main function for the Edit Profile View.
    """
    st.title("Edit Candidate Profile")
    
    # Fetch all candidates from Google Sheet
    google_sheet_data = fetch_google_form_responses()
    
    # Find the email column
    email_column = None
    for col in google_sheet_data.columns:
        if 'email' in col.lower():
            email_column = col
            break
    
    if not email_column:
        st.error("Could not find email column in Google Sheet data.")
        return
    
    # Get list of candidate emails
    candidate_emails = google_sheet_data[email_column].tolist()
    
    # Let user select a candidate by email
    selected_email = st.selectbox("Select Candidate", candidate_emails)
    
    if selected_email:
        edit_candidate_profile(selected_email)

# For testing
if __name__ == "__main__":
    edit_profile()