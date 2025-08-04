import streamlit as st
import os
from datetime import datetime
import pandas as pd

from cloud_storage import upload_cv
from resume_linker import save_temp_cv
from mysql_db import create_candidate, update_candidate, get_candidate_by_id, get_candidate_by_user_id
from candidate_auth import candidate_auth_view

def candidate_form_view():
    """
    Main view for candidates to fill out the application form and upload their CV
    """
    # Check if the user is authenticated as a candidate
    if st.session_state.get('authenticated') and st.session_state.get('user_role') == 'candidate':
        # Show the authenticated candidate view
        authenticated_candidate_view()
    else:
        # Show the login/registration view or new application form
        unauthenticated_candidate_view()

def authenticated_candidate_view():
    """
    View for authenticated candidates to see and edit their application
    """
    st.title("Your BRV Application")
    
    # Get candidate data from session state or database
    candidate_id = st.session_state.get('candidate_id')
    if not candidate_id:
        # Try to get candidate data from user_id
        user_id = st.session_state.get('user_id')
        if user_id:
            candidate = get_candidate_by_user_id(user_id)
            if candidate:
                candidate_id = candidate.get('id')
                st.session_state.candidate_id = candidate_id
    
    if not candidate_id:
        st.error("Could not find your candidate profile. Please contact support.")
        return
    
    # Get candidate data from database
    candidate = get_candidate_by_id(candidate_id)
    if not candidate:
        st.error("Could not find your candidate profile. Please contact support.")
        return
    
    # Display candidate information
    st.subheader("Your Information")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Name:** {candidate.get('name', 'Not provided')}")
        st.write(f"**Email:** {candidate.get('email', 'Not provided')}")
        st.write(f"**Phone:** {candidate.get('phone', 'Not provided')}")
    
    with col2:
        st.write(f"**Application ID:** {candidate.get('id', 'Unknown')}")
        st.write(f"**Interview Status:** {candidate.get('interview_status', 'Not Scheduled')}")
        st.write(f"**CV Status:** {candidate.get('cv_status', 'Not Uploaded')}")
    
    # Display skills and experience
    st.subheader("Skills and Experience")
    st.write(f"**Skills:** {candidate.get('skills', 'Not provided')}")
    
    if candidate.get('experience'):
        st.write("**Experience:**")
        st.write(candidate['experience'])
    
    if candidate.get('education'):
        st.write("**Education:**")
        st.write(candidate['education'])
    
    # Display CV if available
    if candidate.get('resume_url') and candidate.get('cv_status') == 'Uploaded':
        st.subheader("Your CV")
        st.write(f"CV URL: {candidate['resume_url']}")
        
        # In a real implementation, we would add a button to download the CV
        if st.button("Download Your CV"):
            from cloud_storage import download_cv
            cv_content = download_cv(candidate['resume_url'])
            # This would normally download the file, but for now we just show a success message
            st.success("CV downloaded successfully (simulated)")
    
    # Option to edit the application
    st.subheader("Edit Your Application")
    if st.button("Edit Application"):
        st.session_state.editing_own_application = True
        st.rerun()
    
    # Show edit form if editing
    if st.session_state.get('editing_own_application'):
        success = edit_candidate_form(candidate)
        if success:
            st.session_state.editing_own_application = False
            st.rerun()
    
    # Logout button
    st.markdown("---")
    if st.button("Logout"):
        # Clear session state
        for key in ['authenticated', 'user_id', 'email', 'user_role', 'candidate_id', 'candidate_name']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

def unauthenticated_candidate_view():
    """
    View for unauthenticated candidates to login, register, or submit a new application
    """
    # Add tabs for different options
    tab1, tab2 = st.tabs(["Login/Register", "Submit Application Without Account"])
    
    with tab1:
        # Show login/registration view
        candidate_auth_view()
    
    with tab2:
        # Show new application form
        st.title("BRV Application Form")
        st.write("Please fill out the form below and upload your CV to apply.")
        
        # Initialize session state for form data if it doesn't exist
        if 'candidate_form_data' not in st.session_state:
            st.session_state.candidate_form_data = {
                'name': '',
                'email': '',
                'phone': '',
                'skills': '',
                'experience': '',
                'education': '',
                'cv_uploaded': False,
                'cv_path': None,
                'cv_url': None,
                'interview_status': 'Not Scheduled',
                'cv_status': 'Not Uploaded'
            }
        
        # Create the form
        with st.form("candidate_application_form"):
            # Personal Information
            st.subheader("Personal Information")
            name = st.text_input("Full Name*", value=st.session_state.candidate_form_data['name'])
            email = st.text_input("Email Address*", value=st.session_state.candidate_form_data['email'])
            phone = st.text_input("Phone Number", value=st.session_state.candidate_form_data['phone'])
            
            # Skills and Experience
            st.subheader("Skills and Experience")
            skills = st.text_area("Skills (comma separated)*", value=st.session_state.candidate_form_data['skills'])
            experience = st.text_area("Work Experience", value=st.session_state.candidate_form_data['experience'])
            education = st.text_area("Education", value=st.session_state.candidate_form_data['education'])
            
            # CV Upload
            st.subheader("CV Upload")
            uploaded_file = st.file_uploader("Upload your CV (PDF, DOC, DOCX)*", type=["pdf", "doc", "docx"])
            
            # Submit button
            submit_button = st.form_submit_button("Submit Application")
            
            if submit_button:
                # Validate required fields
                if not name or not email or not skills:
                    st.error("Please fill out all required fields marked with *")
                    return
                
                # Validate CV upload
                if not uploaded_file and not st.session_state.candidate_form_data['cv_uploaded']:
                    st.error("Please upload your CV")
                    return
                
                # Update session state with form data
                st.session_state.candidate_form_data.update({
                    'name': name,
                    'email': email,
                    'phone': phone,
                    'skills': skills,
                    'experience': experience,
                    'education': education
                })
                
                # Process CV upload if a new file was uploaded
                cv_url = None
                if uploaded_file:
                    try:
                        # Save the CV temporarily
                        file_content = uploaded_file.read()
                        filename = uploaded_file.name
                        temp_path = save_temp_cv(file_content, filename)
                        
                        # Update session state
                        st.session_state.candidate_form_data['cv_uploaded'] = True
                        st.session_state.candidate_form_data['cv_path'] = temp_path
                        st.session_state.candidate_form_data['cv_status'] = 'Uploaded'
                        
                        st.success(f"CV uploaded successfully: {filename}")
                    except Exception as e:
                        st.error(f"Error uploading CV: {str(e)}")
                        return
                
                # Prepare data for storage
                candidate_data = {
                    'name': name,
                    'email': email,
                    'phone': phone,
                    'skills': skills,
                    'experience': experience,
                    'education': education,
                    'cv_url': st.session_state.candidate_form_data.get('cv_url'),
                    'interview_status': 'Not Scheduled',
                    'cv_status': 'Uploaded' if st.session_state.candidate_form_data['cv_uploaded'] else 'Not Uploaded',
                    'created_by': 'self'
                }
                
                try:
                    # Store candidate data in MySQL database
                    candidate_id = create_candidate(candidate_data)
                    
                    if not candidate_id:
                        st.error("Failed to create candidate record in database")
                        return
                    
                    # If we have a new CV file, upload it to cloud storage with the new candidate ID
                    if uploaded_file:
                        # Reset the file pointer to the beginning
                        uploaded_file.seek(0)
                        # Upload to cloud storage and get URL
                        cv_url = upload_cv(candidate_id, uploaded_file.read(), uploaded_file.name)
                        
                        # Update the candidate record with the CV URL
                        if cv_url:
                            update_candidate(candidate_id, {'cv_url': cv_url, 'cv_status': 'Uploaded'})
                            st.session_state.candidate_form_data['cv_url'] = cv_url
                    
                    # Show success message
                    st.success(f"""
                    ✅ Application submitted successfully!
                    
                    **Name:** {name}
                    **Email:** {email}
                    **CV Uploaded:** {'Yes' if st.session_state.candidate_form_data['cv_status'] == 'Uploaded' else 'No'}
                    
                    Your application has been received and will be reviewed by our team.
                    
                    **Note:** Consider creating an account to easily access and edit your application in the future.
                    """)
                    
                    # Reset the form for a new application
                    st.session_state.candidate_form_data = {
                        'name': '',
                        'email': '',
                        'phone': '',
                        'skills': '',
                        'experience': '',
                        'education': '',
                        'cv_uploaded': False,
                        'cv_path': None,
                        'cv_url': None,
                        'interview_status': 'Not Scheduled',
                        'cv_status': 'Not Uploaded'
                    }
                    
                    # Print debug information to terminal
                    print(f"""
                    ✅ Candidate Data Submitted:
                      - ID: {candidate_id}
                      - Name: {name}
                      - Email: {email}
                      - CV Uploaded: {'Yes → ' + cv_url if cv_url else 'No'}
                      - Interview Status: Not Scheduled
                    
                    🔁 Stored in MySQL database
                    """)
                    
                except Exception as e:
                    st.error(f"Error submitting application: {str(e)}")
        
        # Instructions at the bottom
        st.markdown("""
        ### Instructions
        1. Fill out all required fields marked with *
        2. Upload your CV in PDF, DOC, or DOCX format
        3. Submit your application
        
        **Note:** Creating an account allows you to easily access and edit your application in the future.
        """)

def edit_candidate_form(candidate_data):
    """
    Form for editing an existing candidate application
    
    Args:
        candidate_data (dict): The candidate data to edit
    
    Returns:
        bool: True if the form was submitted successfully, False otherwise
    """
    st.title("Edit Application")
    st.write(f"Editing application for: **{candidate_data['name']}** (ID: {candidate_data['id']})")
    
    # Create the form
    with st.form("edit_candidate_form"):
        # Personal Information
        st.subheader("Personal Information")
        name = st.text_input("Full Name*", value=candidate_data.get('name', ''))
        email = st.text_input("Email Address*", value=candidate_data.get('email', ''))
        phone = st.text_input("Phone Number", value=candidate_data.get('phone', ''))
        
        # Skills and Experience
        st.subheader("Skills and Experience")
        skills = st.text_area("Skills (comma separated)*", value=candidate_data.get('skills', ''))
        experience = st.text_area("Work Experience", value=candidate_data.get('experience', ''))
        education = st.text_area("Education", value=candidate_data.get('education', ''))
        
        # CV Upload
        st.subheader("CV Upload")
        st.write("Current CV: " + ("Uploaded" if candidate_data.get('cv_status') == 'Uploaded' else "Not Uploaded"))
        uploaded_file = st.file_uploader("Upload a new CV (PDF, DOC, DOCX)", type=["pdf", "doc", "docx"])
        
        # Submit button
        submit_button = st.form_submit_button("Update Application")
        
        if submit_button:
            # Validate required fields
            if not name or not email or not skills:
                st.error("Please fill out all required fields marked with *")
                return False
            
            # Update candidate data
            updated_data = {
                'name': name,
                'email': email,
                'phone': phone,
                'skills': skills,
                'experience': experience,
                'education': education
            }
            
            # Process CV upload if a new file was uploaded
            if uploaded_file:
                try:
                    # Upload to cloud storage and get URL
                    uploaded_file.seek(0)
                    cv_url = upload_cv(candidate_data['id'], uploaded_file.read(), uploaded_file.name)
                    updated_data['cv_url'] = cv_url
                    updated_data['cv_status'] = 'Uploaded'
                    
                    st.success(f"CV uploaded successfully: {uploaded_file.name}")
                except Exception as e:
                    st.error(f"Error uploading CV: {str(e)}")
                    return False
            
            try:
                # Update candidate data in MySQL database
                success = update_candidate(candidate_data['id'], updated_data)
                
                if not success:
                    st.error("Failed to update candidate record in database")
                    return False
                
                # Show success message
                st.success(f"""
                ✅ Application updated successfully!
                
                **ID:** {candidate_data['id']}
                **Name:** {updated_data['name']}
                **Email:** {updated_data['email']}
                **CV Uploaded:** {'Yes' if updated_data.get('cv_status', candidate_data.get('cv_status')) == 'Uploaded' else 'No'}
                """)
                
                # Print debug information to terminal
                print(f"""
                ✅ Candidate Data Updated:
                  - ID: {candidate_data['id']}
                  - Name: {updated_data['name']}
                  - Email: {updated_data['email']}
                  - CV Uploaded: {'Yes' if updated_data.get('cv_status', candidate_data.get('cv_status')) == 'Uploaded' else 'No'}
                
                🔁 Updated in MySQL database
                """)
                
                return True
                
            except Exception as e:
                st.error(f"Error updating application: {str(e)}")
                return False
    
    return False