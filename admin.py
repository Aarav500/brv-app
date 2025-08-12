# admin.py
import streamlit as st
from database import SessionLocal
from models import User, Candidate
from auth import hash_password

def show_admin_panel():
    st.header("Admin / CEO Dashboard")
    db = SessionLocal()
    try:
        if st.button("List users"):
            users = db.query(User).all()
            for u in users:
                st.write(u.id, u.email, u.role)

        st.subheader("Create default users")
        email = st.text_input("Email", key="admin_email")
        password = st.text_input("Password", type="password", key="admin_pass")
        role = st.selectbox("Role", ["ceo","admin","receptionist","interviewer","hr","candidate"], key="admin_role")
        if st.button("Create user"):
            u = User(email=email, password_hash=hash_password(password), role=role)
            db.add(u); db.commit()
            st.success("User created")
    finally:
        db.close()
