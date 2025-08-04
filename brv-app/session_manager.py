import streamlit as st

def get_user_session():
    """
    Get the current user session information.
    
    Returns:
        dict: A dictionary containing session information, or None if not authenticated
    """
    if not st.session_state.get('authenticated', False):
        return None
    
    return {
        'user_id': st.session_state.get('user_id'),
        'username': st.session_state.get('username'),
        'role': st.session_state.get('user_role'),
        'password_reset_required': st.session_state.get('password_reset_required', False)
    }