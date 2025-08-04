import streamlit as st
from datetime import datetime
import time

from mysql_db import (
    authenticate_user, 
    get_user_by_email, 
    create_candidate, 
    get_candidate_by_user_id,
    get_candidate_by_email
)

def candidate_login_view():
    """
    Display the login view for candidates.
    
    Returns:
        bool: True if login was successful, False otherwise
    """
    st.title("Candidate Login")
    st.write("Please log in to access your application.")
    
    with st.form("candidate_login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            if not email or not password:
                st.error("Please enter both email and password.")
                return False
            
            # Authenticate user
            user = authenticate_user(email, password)
            
            if user and user.get('role') == 'candidate':
                # Set up session state
                st.session_state.authenticated = True
                st.session_state.user_id = user.get("id", "")
                st.session_state.email = email
                st.session_state.user_role = 'candidate'
                
                # Get candidate data
                candidate = get_candidate_by_user_id(user.get("id"))
                if candidate:
                    st.session_state.candidate_id = candidate.get('id')
                    st.session_state.candidate_name = candidate.get('name')
                    
                    # Store resume URL in session state if available
                    resume_url = candidate.get("resume_url", "")
                    if resume_url:
                        st.session_state.resume_url = resume_url
                
                st.success("Login successful!")
                st.rerun()
                return True
            else:
                st.error("Invalid email or password, or you are not registered as a candidate.")
                return False
    
    # Add registration link
    st.markdown("---")
    st.write("Don't have an account?")
    if st.button("Register as a Candidate"):
        st.session_state.show_candidate_registration = True
        st.rerun()
    
    return False

def candidate_registration_view():
    """
    Display the registration view for candidates.
    
    Returns:
        bool: True if registration was successful, False otherwise
    """
    st.title("Candidate Registration")
    st.write("Please fill out the form below to register as a candidate.")
    
    with st.form("candidate_registration_form"):
        name = st.text_input("Full Name*")
        email = st.text_input("Email Address*")
        phone = st.text_input("Phone Number")
        password = st.text_input("Password*", type="password")
        confirm_password = st.text_input("Confirm Password*", type="password")
        
        # Basic skills and experience
        skills = st.text_area("Skills (comma separated)*")
        experience = st.text_area("Work Experience")
        education = st.text_area("Education")
        
        submit = st.form_submit_button("Register")
        
        if submit:
            # Validate required fields
            if not name or not email or not skills or not password or not confirm_password:
                st.error("Please fill out all required fields marked with *")
                return False
            
            # Validate password
            if password != confirm_password:
                st.error("Passwords do not match")
                return False
            
            if len(password) < 8:
                st.error("Password must be at least 8 characters long")
                return False
            
            # Check if email is already registered
            existing_user = get_user_by_email(email)
            if existing_user:
                st.error("This email is already registered. Please log in instead.")
                return False
            
            # Check if candidate with this email already exists
            existing_candidate = get_candidate_by_email(email)
            if existing_candidate:
                # If candidate exists but doesn't have a user account, we can create one and link it
                st.warning("An application with this email already exists. Creating a user account for it.")
            
            # Prepare candidate data
            candidate_data = {
                'name': name,
                'email': email,
                'phone': phone,
                'skills': skills,
                'experience': experience,
                'education': education,
                'created_by': 'self'
            }
            
            try:
                # Create candidate with user account
                candidate_id = create_candidate(candidate_data, create_user_account=True, password=password)
                
                if not candidate_id:
                    st.error("Failed to create candidate record in database")
                    return False
                
                # Show success message
                st.success(f"""
                ✅ Registration successful!
                
                **Name:** {name}
                **Email:** {email}
                
                You can now log in with your email and password.
                """)
                
                # Reset the form and show login view
                time.sleep(2)
                st.session_state.show_candidate_registration = False
                st.rerun()
                return True
                
            except Exception as e:
                st.error(f"Error registering candidate: {str(e)}")
                return False
    
    # Add back to login button
    st.markdown("---")
    if st.button("Back to Login"):
        st.session_state.show_candidate_registration = False
        st.rerun()
    
    return False

def candidate_auth_view():
    """
    Main authentication view for candidates.
    Handles both login and registration.
    
    Returns:
        bool: True if authentication was successful, False otherwise
    """
    # Initialize session state
    if 'show_candidate_registration' not in st.session_state:
        st.session_state.show_candidate_registration = False
    
    # Show registration or login view based on session state
    if st.session_state.show_candidate_registration:
        return candidate_registration_view()
    else:
        return candidate_login_view()