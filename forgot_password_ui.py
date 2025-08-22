import streamlit as st
from auth import create_reset_token, send_reset_email, verify_reset_token, register_user
from db_postgres import get_user_by_email, update_user_password, hash_password


def forgot_password_view():
    st.header("Forgot / Reset Password")

    # Back to login button
    if st.button("⬅ Back to Login"):
        st.session_state.auth_mode = None
        st.rerun()

    try:
        st.subheader("Request password reset")
        email = st.text_input("Your email", key="fp_email")
        if st.button("Request reset"):
            # Check if user exists using PostgreSQL function
            user = get_user_by_email(email)
            if not user:
                st.error("No user with that email")
            else:
                token = create_reset_token(email)
                ok = send_reset_email(email, token)
                if ok:
                    st.success("Reset token sent. Please check your email (or console log in dev).")
                else:
                    st.error("Failed to send reset email. Please verify email settings.")

        st.markdown("---")
        st.subheader("Perform password reset")
        token = st.text_input("Reset token (paste here)", key="rp_token")
        new_pass = st.text_input("New password", type="password", key="rp_new")
        if st.button("Reset password"):
            email_verified = verify_reset_token(token)
            if not email_verified:
                st.error("Invalid or expired token")
            else:
                # Check if user exists
                user = get_user_by_email(email_verified)
                if not user:
                    st.error("User not found")
                else:
                    # Update password using PostgreSQL function
                    success = update_user_password(email_verified, new_pass)
                    if success:
                        st.success("Password changed. Please login.")
                    else:
                        st.error("Failed to update password. Please try again.")

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")


def create_user_view():
    """Optional: Create new user interface"""
    st.header("Create New User")

    try:
        email = st.text_input("Email", key="create_email")
        password = st.text_input("Password", type="password", key="create_password")
        role = st.selectbox("Role", ["candidate", "receptionist", "interviewer", "admin", "ceo"], key="create_role")

        if st.button("Create User"):
            if not email or not password:
                st.error("Please fill in all fields")
            else:
                ok = register_user(email, password, role)
                if ok:
                    st.success(f"User created successfully: {email} with role {role}")
                else:
                    st.error("Failed to create user; it may already exist.")

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
