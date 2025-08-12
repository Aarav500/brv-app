# forgot_password_ui.py
import streamlit as st
from auth import create_reset_token, send_reset_email, verify_reset_token, create_user, verify_password, hash_password
from database import SessionLocal
from models import User

def forgot_password_view():
    st.header("Forgot / Reset Password")
    db = SessionLocal()
    try:
        st.subheader("Request password reset")
        email = st.text_input("Your email", key="fp_email")
        if st.button("Request reset"):
            user = db.query(User).filter(User.email == email).first()
            if not user:
                st.error("No user with that email")
            else:
                token = create_reset_token(email)
                ok, msg = send_reset_email(email, token)
                if ok:
                    st.success("Reset token sent (or printed to console).")
                else:
                    st.error(f"Failed to send: {msg}")

        st.markdown("---")
        st.subheader("Perform password reset")
        token = st.text_input("Reset token (paste here)", key="rp_token")
        new_pass = st.text_input("New password", type="password", key="rp_new")
        if st.button("Reset password"):
            email_verified = verify_reset_token(token)
            if not email_verified:
                st.error("Invalid or expired token")
            else:
                user = db.query(User).filter(User.email == email_verified).first()
                if not user:
                    st.error("User not found")
                else:
                    user.password_hash = hash_password(new_pass)
                    user.force_password_reset = False
                    db.add(user); db.commit()
                    st.success("Password changed. Please login.")
    finally:
        db.close()
