import streamlit as st
from interviewer import interviewer_view

def profiles_view():
    """
    Wrapper function for the interviewer view, which handles candidate profiles.
    This function is used for role-based redirection from login.py.
    """
    interviewer_view()

if __name__ == "__main__":
    st.set_page_config(
        page_title="Interviewer - Candidate Profiles",
        page_icon="👥",
        layout="wide"
    )
    
    # Initialize session state for testing
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = True
    if 'user_id' not in st.session_state:
        st.session_state.user_id = "test_interviewer_id"
    if 'user_role' not in st.session_state:
        st.session_state.user_role = "interviewer"
    
    profiles_view()