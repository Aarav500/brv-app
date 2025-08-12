import streamlit as st
import pandas as pd
import uuid
from datetime import datetime

from mysql_db import get_db_connection
from utils import VALID_ROLES
from security import hash_password  # existing helper that returns (hashed, salt)

# ---------- DB helper ----------
def _query_fetchall(query, params=()):
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall()
            return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()

def _query_execute(query, params=()):
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            conn.commit()
            return True
    except Exception as e:
        st.error(f"DB error: {e}")
        return False
    finally:
        conn.close()

# ---------- Business functions ----------
def get_all_users():
    query = "SELECT user_id AS id, username, email, role, force_password_reset, last_password_change FROM users ORDER BY created_at DESC"
    return _query_fetchall(query)

def add_user(email, password, role):
    role = role.lower()
    if role not in VALID_ROLES:
        return False, f"Invalid role: {role}"
    # Validate email basic
    if "@" not in email:
        return False, "Invalid email address"

    # Hash password
    password_hash, salt = hash_password(password)
    user_id = str(uuid.uuid4())
    now = datetime.utcnow()
    query = """
        INSERT INTO users (user_id, username, email, password_hash, role, last_password_change, force_password_reset)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    ok = _query_execute(query, (user_id, email, email, password_hash, role, now, True))
    if ok:
        return True, user_id
    else:
        return False, "Failed to add user"

def remove_user(user_id):
    # Prevent deleting last CEO or CEO itself handled by UI; here just attempt delete
    query = "DELETE FROM users WHERE user_id = %s"
    ok = _query_execute(query, (user_id,))
    return ok, ("User removed" if ok else "Failed to remove user")

def update_user_password(user_id, new_password):
    password_hash, salt = hash_password(new_password)
    query = "UPDATE users SET password_hash = %s, last_password_change = %s, force_password_reset = %s WHERE user_id = %s"
    ok = _query_execute(query, (password_hash, datetime.utcnow(), True, user_id))
    return ok

def update_user_role(user_id, new_role, new_email=None):
    new_role = new_role.lower()
    if new_role not in VALID_ROLES:
        return False, f"Invalid role: {new_role}"
    if new_email:
        query = "UPDATE users SET role = %s, email = %s, username = %s WHERE user_id = %s"
        ok = _query_execute(query, (new_role, new_email, new_email, user_id))
    else:
        query = "UPDATE users SET role = %s WHERE user_id = %s"
        ok = _query_execute(query, (new_role, user_id))
    return (ok, "Updated" if ok else "Failed to update")

def get_password_expiry_policy():
    query = "SELECT value FROM settings WHERE key = %s"
    rows = _query_fetchall(query, ("password_expiry_days",))
    if rows:
        try:
            return int(rows[0]["value"])
        except:
            return 30
    return 30

def update_password_expiry_policy(days):
    try:
        days = int(days)
    except:
        return False, "Invalid days value"
    query = """
        INSERT INTO settings (key, value, updated_at)
        VALUES (%s, %s, NOW())
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at
    """
    ok = _query_execute(query, ("password_expiry_days", str(days)))
    return (ok, f"Password expiry set to {days} days" if ok else "Failed to update")

def force_password_reset_all():
    query = "UPDATE users SET force_password_reset = TRUE"
    ok = _query_execute(query)
    return ok

# ---------- Streamlit UI ----------
def show_admin_panel():
    st.header("👤 CEO Control Panel")
    st.subheader("User Management")
    admin_view()

def admin_view():
    st.title("👑 Admin Dashboard")
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["User Management", "System Overview", "Candidate Statistics"])

    if page == "User Management":
        user_management_page()
    elif page == "System Overview":
        system_overview_page()
    elif page == "Candidate Statistics":
        candidate_statistics_page()

def user_management_page():
    st.header("👥 User Management")
    tab1, tab2, tab3, tab4 = st.tabs(["View Users", "Add User", "Modify User", "Password Policy"])

    with tab1:
        st.subheader("Current Users")
        users = get_all_users()
        if users:
            users_df = pd.DataFrame([{
                "Email": u.get("email"),
                "Role": u.get("role"),
                "Password Reset Required": "Yes" if u.get("force_password_reset") else "No",
                "Last Password Change": u.get("last_password_change") or "Never"
            } for u in users])
            st.dataframe(users_df)
        else:
            st.info("No users found.")

    with tab2:
        st.subheader("Add New User")
        with st.form("add_user_form"):
            email = st.text_input("Email")
            password = st.text_input("Initial Password", type="password")
            role = st.selectbox("Role", VALID_ROLES)
            submit = st.form_submit_button("Add User")
            if submit:
                ok, message = add_user(email, password, role)
                if ok:
                    st.success("User added")
                else:
                    st.error(message)

    with tab3:
        st.subheader("Modify Existing User")
        users = get_all_users()
        if not users:
            st.info("No users found.")
            return
        user_options = [f"{u['email']} ({u['role']})" for u in users]
        selected = st.selectbox("Select User", user_options)
        if selected:
            email = selected.split(" (")[0]
            user = next((u for u in users if u["email"] == email), None)
            if user:
                st.write(f"User ID: {user['id']}")
                new_email = st.text_input("New Email", value=user["email"])
                new_role = st.selectbox("New Role", VALID_ROLES, index = VALID_ROLES.index(user.get("role", VALID_ROLES[0])))
                if st.button("Change Role / Email"):
                    ok, msg = update_user_role(user["id"], new_role, new_email)
                    if ok:
                        st.success("Updated")
                    else:
                        st.error(msg)
                if st.button("Reset Password"):
                    import random, string
                    new_pass = ''.join(random.choices(string.ascii_letters+string.digits, k=12))
                    if update_user_password(user["id"], new_pass):
                        st.success(f"Password reset — new password: {new_pass}")
                    else:
                        st.error("Failed to reset password")
                if st.button("Remove User"):
                    if user.get("role","").lower() == "ceo":
                        st.error("Cannot delete CEO account")
                    else:
                        ok, msg = remove_user(user["id"])
                        if ok:
                            st.success("User removed")
                        else:
                            st.error(msg)

    with tab4:
        st.subheader("Password Policy")
        current = get_password_expiry_policy()
        with st.form("policy"):
            days = st.number_input("Password expiry (days)", min_value=1, max_value=365, value=current)
            submit = st.form_submit_button("Update")
            if submit:
                ok, msg = update_password_expiry_policy(days)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

def system_overview_page():
    st.header("📊 System Overview")
    users = get_all_users()
    total_users = len(users)
    st.write(f"**Total Users:** {total_users}")
    # roles chart
    roles = {}
    for u in users:
        r = u.get("role","unknown")
        roles[r] = roles.get(r, 0) + 1
    role_df = pd.DataFrame({"Role": list(roles.keys()), "Count": list(roles.values())})
    if not role_df.empty:
        st.bar_chart(role_df.set_index("Role"))

def candidate_statistics_page():
    st.header("👨‍💼 Candidate Statistics")
    conn = get_db_connection()
    if not conn:
        st.error("DB connection failed")
        return
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM candidates")
            total = cur.fetchone()[0]
            cur.execute("SELECT interview_status, COUNT(*) FROM candidates GROUP BY interview_status")
            status_counts = cur.fetchall()
            cur.execute("""
                SELECT c.full_name, r.interviewer_name, r.scheduled_time, r.result
                FROM interviews r
                JOIN candidates c ON r.candidate_id = c.candidate_id
                ORDER BY r.scheduled_time DESC
                LIMIT 5
            """)
            recents = cur.fetchall()
    except Exception as e:
        st.error(f"Error: {e}")
        return
    finally:
        conn.close()

    st.write(f"**Total Candidates:** {total}")
    if status_counts:
        df = pd.DataFrame(status_counts, columns=["Status","Count"])
        st.bar_chart(df.set_index("Status"))
    if recents:
        df2 = pd.DataFrame(recents, columns=["Candidate","Interviewer","Date","Result"])
        st.dataframe(df2)
