import streamlit as st
import os

from db_postgres import init_db, get_user_by_email, verify_password, hash_password
from utils import VALID_ROLES
from admin import show_admin_panel
from ceo import show_ceo_panel
from candidate_view import candidate_form_view
from interviewer import interviewer_view
from forgot_password_ui import forgot_password_view

st.set_page_config(page_title="BRV Applicant Management", layout="wide")

# Initialize DB
init_db()


# -------------------------
# AUTH HELPERS
# -------------------------
def authenticate_user(email: str, password: str):
    """Authenticate user using PostgreSQL database"""
    user = get_user_by_email(email)
    if user and verify_password(password, user['password_hash']):
        return user
    return None


def create_user(email: str, password: str, role: str = "candidate"):
    """Create new user in PostgreSQL database"""
    try:
        from db_postgres import get_conn
        conn = get_conn()
        with conn:
            with conn.cursor() as cur:
                # Check if user already exists
                cur.execute("SELECT id FROM users WHERE email=%s", (email,))
                if cur.fetchone():
                    return None, "User already exists"

                # Create new user
                password_hash = hash_password(password)
                cur.execute(
                    "INSERT INTO users (email, password_hash, role) VALUES (%s, %s, %s) RETURNING id",
                    (email, password_hash, role)
                )
                user_id = cur.fetchone()[0]

        conn.close()
        return {"id": user_id, "email": email, "role": role}, None
    except Exception as e:
        return None, str(e)


# -------------------------
# LOGIN & REGISTER
# -------------------------
def login_form():
    st.sidebar.title("Login")
    email = st.sidebar.text_input("Email")
    password = st.sidebar.text_input("Password", type="password")

    if st.sidebar.button("Login"):
        user = authenticate_user(email.strip(), password.strip())
        if user:
            st.session_state["user"] = {
                "id": user["id"],
                "email": user["email"],
                "role": user["role"],
                # extra permissions if DB query returned them
                "can_delete_records": user.get("can_delete_records", False),
                "can_grant_delete": user.get("can_grant_delete", False),
            }
            st.rerun()
        else:
            st.sidebar.error("Invalid credentials")

    if st.sidebar.button("Forgot Password?"):
        st.session_state.page = "forgot_password"
        st.rerun()


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


# -------------------------
# MAIN ROUTER
# -------------------------
def main():
    # Forgot password page routing
    if st.session_state.get("page") == "forgot_password":
        forgot_password_view()
        return

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
        st.rerun()

    # Role-based routing
    role = user["role"].lower()
    if role == "ceo":
        show_ceo_panel()
    elif role == "admin":
        show_admin_panel()
    elif role == "receptionist":
        from receptionist import receptionist_view
        receptionist_view()
    elif role == "interviewer":
        interviewer_view()
    elif role == "candidate":
        candidate_form_view()
    else:
        st.warning(f"Role {role} not implemented yet.")


if __name__ == "__main__":
    main()
