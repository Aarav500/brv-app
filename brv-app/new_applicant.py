import streamlit as st
from receptionist import receptionist_view

def new_applicant_view():
    """
    Wrapper function for the receptionist view, which handles new applicants.
    This function is used for role-based redirection from login.py.
    """
    receptionist_view()

if __name__ == "__main__":
    st.set_page_config(
        page_title="HR - New Applicant",
        page_icon="👤",
        layout="wide"
    )
    
    # Initialize session state for testing
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = True
    if 'user_id' not in st.session_state:
        st.session_state.user_id = "test_hr_id"
    if 'user_role' not in st.session_state:
        st.session_state.user_role = "receptionist"
    
    new_applicant_view()