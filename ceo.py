# admin_panel.py (Streamlit snippet)
import streamlit as st
from db_postgres import get_all_candidates, get_user_by_email, update_user_role, update_user_password, seed_sample_users

def show_admin_panel():
    st.header("Admin / CEO Panel")
    if st.button("Ensure DB & Seed sample users"):
        from db_postgres import init_db
        init_db()
        seed_sample_users()
        st.success("DB initialized & sample users created (if absent).")

    def remove_user(email):
        conn = get_conn()
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM users WHERE email=%s", (email,))

    def update_user_password(email, new_password):
        conn = get_conn()
        with conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET password=%s WHERE email=%s", (new_password, email))


    st.subheader("All candidates")
    candidates = get_all_candidates()
    for c in candidates:
        st.write(f"ID: {c['candidate_id']} — Name: {c.get('name')} — Resume: {c.get('resume_link')}")
        if c.get('resume_link'):
            st.markdown(f"[Open resume]({c.get('resume_link')})")

    st.subheader("User management")
    email = st.text_input("User email to manage")
    if email:
        user = get_user_by_email(email)
        if user:
            st.write(f"Email: {user['email']} — Role: {user['role']}")
            new_role = st.text_input("New role (leave blank to skip)")
            new_pwd = st.text_input("New password (leave blank to skip)", type="password")
            if st.button("Apply changes"):
                msg = []
                if new_role:
                    ok = update_user_role(email, new_role)
                    msg.append(f"role updated: {ok}")
                if new_pwd:
                    ok = update_user_password(email, new_pwd)
                    msg.append(f"password updated: {ok}")
                st.success(" ; ".join(msg))
        else:
            st.warning("User not found. You can create via seed or signup flow.")
