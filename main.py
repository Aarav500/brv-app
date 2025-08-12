# main.py
import streamlit as st
from database import init_db, SessionLocal
import auth, models
from auth import authenticate_user, create_user
from utils import require_login, VALID_ROLES
from admin import show_admin_panel
from receptionist import receptionist_view
from candidate_view import candidate_form_view
from interviewer import interviewer_view

st.set_page_config(page_title="BRV Applicant Management", layout="wide")

# Initialize DB if not exists
init_db()

def login_form():
    st.sidebar.title("Login")
    email = st.sidebar.text_input("Email")
    password = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Login"):
        user = authenticate_user(email.strip(), password.strip())
        if user:
            st.session_state["user"] = {"id": user.id, "email": user.email, "role": user.role.value}
            st.experimental_rerun()
        else:
            st.sidebar.error("Invalid credentials")

def register_form():
    st.sidebar.header("Create account (for testing)")
    email = st.sidebar.text_input("New email", key="reg_email")
    password = st.sidebar.text_input("New password", type="password", key="reg_pass")
    role = st.sidebar.selectbox("Role", list(VALID_ROLES), index=5, key="reg_role")
    if st.sidebar.button("Register"):
        user, err = create_user(email.strip(), password.strip(), role)
        if err:
            st.sidebar.error(err)
        else:
            st.sidebar.success("User created. Please login.")

def logout():
    if st.sidebar.button("Logout"):
        st.session_state.pop("user", None)
        st.experimental_rerun()

def main():
    st.title("BRV Applicant Management System")
    if "user" not in st.session_state:
        login_form()
        register_form()
        st.info("Please login from the sidebar. Create a test user with Register if needed.")
        return

    user = st.session_state["user"]
    st.sidebar.write(f"Logged in as: **{user['email']}** ({user['role']})")
    if st.sidebar.button("Logout"):
        st.session_state.pop("user", None)
        st.experimental_rerun()

    role = user["role"]
    if role == "ceo" or role == "admin":
        show_admin_panel()
    elif role == "receptionist":
        receptionist_view()
    elif role == "interviewer":
        interviewer_view()
    elif role == "candidate":
        candidate_form_view()
    else:
        st.warning(f"Role {role} not implemented yet.")

if __name__ == "__main__":
    main()
