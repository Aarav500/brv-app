import streamlit as st
from login import login
from admin import show_admin_panel
from resume_handler import show_resume_handler
from receptionist import receptionist_view
from session_manager import get_user_session
from database import init_db, init_users
from utils import VALID_ROLES
from candidate_view import candidate_form_view
import asyncio
from mysql_db import get_db_connection

# Set page configuration
st.set_page_config(
    page_title="BRV Applicant Management System",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize the database
from database import init_db
asyncio.run(init_db())

# Function to check DB size
def get_db_size_gb():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT pg_database_size(current_database());")
        size_bytes = cur.fetchone()[0]
        conn.close()
        return size_bytes / (1024 * 1024 * 1024)  # Convert to GB
    except Exception as e:
        st.error(f"Error checking DB size: {e}")
        return None

# Call this early in your main()
def maybe_show_storage_warning():
    if st.session_state.get("user_role") == "ceo":
        db_size = get_db_size_gb()
        if db_size is not None and db_size >= 5:
            st.warning(f"⚠ Database usage is at {db_size:.2f} GB. "
                       f"Please free space or archive old data before hitting the 10 GB limit.")


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
    elif role == "candidate":
        candidate_form_view()
    else:
        st.info(f"Role '{role}' is recognized but no specific view is implemented yet.")

# Run the app
if __name__ == "__main__":
    main()
