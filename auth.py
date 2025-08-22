# auth.py
import streamlit as st
import os
import secrets
import time
import jwt
import datetime
from db_postgres import (
    get_user_by_email, get_user_by_id,
    create_user_in_db, update_user_password,
    verify_password, seed_sample_users,
    get_all_users_with_permissions, get_user_permissions
)

# === SESSION HELPERS ===

def _init_session():
    if "user" not in st.session_state:
        st.session_state.user = None
    if "auth_token" not in st.session_state:
        st.session_state.auth_token = None
    if "flash" not in st.session_state:
        st.session_state.flash = None


def _flash(msg, level="info"):
    st.session_state.flash = (msg, level)


def _show_flash():
    if st.session_state.flash:
        msg, level = st.session_state.flash
        if level == "success":
            st.success(msg)
        elif level == "error":
            st.error(msg)
        else:
            st.info(msg)
        st.session_state.flash = None


def is_logged_in():
    return bool(st.session_state.get("user"))


def require_login():
    if not is_logged_in():
        st.warning("You must log in to continue.")
        st.stop()


def logout():
    st.session_state.user = None
    st.session_state.auth_token = None
    _flash("You have been logged out.", "success")
    st.rerun()


# === AUTH LOGIC ===

def login_user(email: str, password: str) -> bool:
    """Check credentials and set session state."""
    user = get_user_by_email(email)
    if not user:
        return False
    if not verify_password(password, user["password_hash"]):
        return False

    # Generate session token
    st.session_state.auth_token = secrets.token_hex(16)
    # fetch fresh user with permission flags
    st.session_state.user = {
        "id": user["id"],
        "email": user["email"],
        "role": user["role"],
        "can_view_cvs": user.get("can_view_cvs", False),
        "can_delete_records": user.get("can_delete_records", False),
        "can_grant_delete": user.get("can_grant_delete", False),
    }
    return True


def register_user(email: str, password: str, role: str = "candidate") -> bool:
    return create_user_in_db(email, password, role)


def reset_password(email: str, new_password: str) -> bool:
    return update_user_password(email, new_password)


# Backwards compatibility: some modules import create_user
create_user = register_user


# === STREAMLIT UI VIEWS ===

def login_view():
    st.title("🔐 Login")

    _init_session()
    _show_flash()

    with st.form("login_form"):
        email = st.text_input("Email", placeholder="you@example.com")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

    if submitted:
        if login_user(email.strip(), password.strip()):
            _flash("Login successful.", "success")
            st.rerun()
        else:
            _flash("Invalid credentials.", "error")
            st.rerun()

    st.caption("Don’t have an account? Contact admin or register if allowed.")


def register_view():
    st.title("📝 Register New Account")
    with st.form("register_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm Password", type="password")
        role = st.selectbox("Role", ["candidate", "receptionist", "interviewer", "hr"])
        submitted = st.form_submit_button("Register")

    if submitted:
        if not email or not password:
            st.error("Email and password required.")
            return
        if password != confirm:
            st.error("Passwords do not match.")
            return
        ok = register_user(email, password, role)
        if ok:
            st.success(f"Account created for {email}. Please login.")
        else:
            st.error("Failed to register (maybe user exists).")


def reset_password_view():
    st.title("🔑 Reset Password")
    with st.form("reset_form"):
        email = st.text_input("Email")
        new_pass = st.text_input("New Password", type="password")
        confirm = st.text_input("Confirm New Password", type="password")
        submitted = st.form_submit_button("Update Password")

    if submitted:
        if not email or not new_pass:
            st.error("Email and new password required.")
            return
        if new_pass != confirm:
            st.error("Passwords do not match.")
            return
        if reset_password(email, new_pass):
            st.success("Password updated. Please log in.")
        else:
            st.error("Password reset failed.")


def user_profile_view():
    require_login()
    st.title("👤 Profile")
    user = st.session_state.user

    st.write(f"**Email:** {user['email']}")
    st.write(f"**Role:** {user['role']}")
    st.write("**Permissions:**")
    st.json({
        "can_view_cvs": user.get("can_view_cvs", False),
        "can_delete_records": user.get("can_delete_records", False),
        "can_grant_delete": user.get("can_grant_delete", False),
    })

    if st.button("Logout"):
        logout()


def manage_users_view():
    require_login()
    user = st.session_state.user
    if user["role"].lower() not in ("admin", "ceo"):
        st.error("You do not have permission to view this page.")
        return

    st.title("👥 Manage Users")
    users = get_all_users_with_permissions()
    if not users:
        st.info("No users found.")
        return

    for u in users:
        label = u.get("email", "(no email)")
        role_val = (u.get("role") or "").strip().lower()
        if role_val and role_val != "ceo":
            label = f"{label} — {u.get('role')}"
        with st.expander(label):
            st.write(f"ID: {u['id']}")
            st.write(f"Role: {u['role']}")
            st.json({
                "can_view_cvs": u.get("can_view_cvs", False),
                "can_delete_records": u.get("can_delete_records", False),
                "can_grant_delete": u.get("can_grant_delete", False),
            })


# === ENTRY POINTS ===

def auth_router():
    """Show appropriate auth view based on session/user."""
    _init_session()
    if not is_logged_in():
        login_view()
    else:
        user_profile_view()


def seed_users_if_needed():
    """Create initial test accounts."""
    seed_sample_users()


# === PASSWORD RESET TOKEN HELPERS ===

SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key")
RESET_TOKEN_EXPIRY = 3600  # 1 hour


def create_reset_token(email: str) -> str:
    """Generate a password reset JWT token for a given user email."""
    payload = {
        "email": email,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(seconds=RESET_TOKEN_EXPIRY)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def verify_reset_token(token: str):
    """Verify token and return email if valid, else None."""
    try:
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return decoded.get("email")
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def send_reset_email(to_email: str, token: str) -> bool:
    """Send reset email with token link."""
    import smtplib
    from email.mime.text import MIMEText

    reset_link = f"http://localhost:8501/reset-password?token={token}"
    msg = MIMEText(f"Click this link to reset your password: {reset_link}")
    msg["Subject"] = "Password Reset"
    msg["From"] = os.getenv("EMAIL_FROM", "noreply@example.com")
    msg["To"] = to_email

    try:
        with smtplib.SMTP(os.getenv("SMTP_SERVER", "localhost"), int(os.getenv("SMTP_PORT", 25))) as server:
            if os.getenv("SMTP_USER") and os.getenv("SMTP_PASS"):
                server.starttls()
                server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS"))
            server.send_message(msg)
        return True
    except Exception as e:
        print("Email sending failed:", e)
        return False
