import streamlit as st
from login import login
from admin import show_admin_panel
from resume_handler import show_resume_handler
from receptionist import receptionist_view
from session_manager import get_user_session
from database import init_db, init_users
from utils import VALID_ROLES

# Set page configuration
st.set_page_config(
    page_title="BRV Applicant Management System",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize the database
init_db()
init_users()

# Main application
def main():
    # Check for reset_triggered flag
    if st.session_state.get("reset_triggered"):
        st.session_state["reset_triggered"] = False
        # Use st.rerun() (experimental_rerun is deprecated)
        st.rerun()

    # Check login
    login()

    # Now check user session
    session = get_user_session()

    if not session:
        return

    st.sidebar.header("Navigation")
    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())

    role = session.get("role")

    # Convert role to lowercase for case-insensitive comparison
    if role:
        role = role.lower()

    if role not in VALID_ROLES:
        st.warning(f"Unknown role: '{role}'. Access denied. Please contact admin to assign a valid role.")
        print(f"User Role: {role}")  # Debug print to check what role is actually fetched
        return

    if role == "ceo":
        show_admin_panel()
    elif role == "hr":
        show_resume_handler()
    elif role == "receptionist":
        receptionist_view()
    elif role == "interviewer":
        # Import here to avoid circular imports
        from interviewer import interviewer_view
        interviewer_view()
    elif role == "admin":
        show_admin_panel()  # Admin uses same panel as CEO
    else:
        st.info(f"Role '{role}' is recognized but no specific view is implemented yet.")

# Run the app
if __name__ == "__main__":
    main()
