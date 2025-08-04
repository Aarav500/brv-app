import streamlit as st
from auth import login as auth_login, password_reset_page, change_password, forgot_password_page
from datetime import datetime
import importlib

def show_password_reset_form():
    """Display a form for password reset and handle the password change logic."""
    st.warning("You must reset your password before continuing.")

    # Track success
    if "password_changed" not in st.session_state:
        st.session_state["password_changed"] = False

    if not st.session_state["password_changed"]:
        with st.form("password_reset_form"):
            new_password = st.text_input("New Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")

            if st.form_submit_button("Change Password"):
                if new_password != confirm_password:
                    st.error("Passwords do not match.")
                elif len(new_password) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    # Use email from session state instead of user_id
                    success, message = change_password("", new_password)
                    if success:
                        st.success("✅ Password changed successfully. Please log in again.")
                        st.session_state["password_changed"] = True
                        # Clear session to force logout
                        st.session_state.clear()
                        st.rerun()
                    else:
                        st.error(f"Failed to update password: {message}")
    else:
        st.success("✅ Password changed successfully. Please log in again.")
        # Add back-to-login button here
        if st.button("🔙 Back to Login"):
            # Clear session and rerun
            st.session_state.clear()
            st.rerun()

        # Optional: Auto-redirect after 3 seconds
        import time
        time.sleep(3)
        st.session_state.clear()
        st.rerun()

    # Add Back to Login button (only show if password not changed)
    if not st.session_state.get("password_changed", False):
        st.markdown("---")
        if st.button("🔙 Back to Login"):
            st.session_state.clear()  # Clear all session state
            st.rerun()

    # Prevent app from continuing if reset needed
    st.stop()

def login():
    # Clear conditional logic to show only one screen at a time

    # CASE 0: User wants to reset password via forgot password flow
    if st.session_state.get('show_forgot_password', False):
        # If user successfully resets password, return to login page
        if forgot_password_page():
            st.session_state.show_forgot_password = False
            st.rerun()
        return

    # CASE 1: User needs to reset password (highest priority)
    if 'authenticated' in st.session_state and st.session_state.get('authenticated') and st.session_state.get('password_reset_required'):
        st.title("🔐 Password Reset Required")
        show_password_reset_form()
        return

    # CASE 2: User is authenticated but doesn't need password reset
    if 'authenticated' in st.session_state and st.session_state.get('authenticated') and not st.session_state.get('password_reset_required'):
        # Role-based redirection
        role = st.session_state.user_role.lower() if st.session_state.user_role else ""

        if role == "ceo":
            st.info("Redirecting to Admin Panel...")
            # Redirect to admin.py will be handled by main.py
        elif role == "receptionist":
            st.info("Redirecting to New Applicant Panel...")
            # Redirect to new_applicant.py will be handled by main.py
        elif role == "interviewer":
            st.info("Redirecting to Profiles Panel...")
            # Redirect to profiles.py will be handled by main.py

        # No need to rerun here as main.py will handle the redirection
        return

    # CASE 3: User is not authenticated (show login form)
    st.title("🔐 BRV Applicant Management Login")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")

        if submit:
            if not username or not password:
                st.error("Please enter both username and password.")
            else:
                # Use the auth_login function from auth.py
                success, message = auth_login(username, password)

                # Print force_reset flag for debugging
                if success:
                    print(f"User {username} - force_reset: {st.session_state.get('password_reset_required', False)}")

                if success:
                    # Set session state variables
                    st.session_state["role"] = st.session_state.user_role

                    if st.session_state.get('password_reset_required'):
                        st.warning("⚠️ Password reset required. You will be redirected.")
                        st.rerun()  # Rerun to show the password reset form
                    else:
                        st.success(f"Welcome, {username}!")
                        st.rerun()  # Rerun to trigger role-based redirection
                else:
                    st.error(f"❌ {message}")

    # Add forgot password button in its own form to ensure it works on first click
    with st.form("forgot_password_form", clear_on_submit=False):
        forgot_password_submitted = st.form_submit_button("Forgot Password?")
        if forgot_password_submitted:
            st.session_state.show_forgot_password = True
            st.rerun()

# For testing the login page directly
if __name__ == "__main__":
    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'user_role' not in st.session_state:
        st.session_state.user_role = None
    if 'show_forgot_password' not in st.session_state:
        st.session_state.show_forgot_password = False

    login()
