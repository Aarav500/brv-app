# admin.py
import streamlit as st
from db_postgres import get_conn, hash_password, get_all_candidates
from psycopg2.extras import RealDictCursor


def get_all_users():
    """Get all users from PostgreSQL database"""
    conn = get_conn()
    with conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, email, role, created_at FROM users ORDER BY created_at DESC")
            users = cur.fetchall()
    conn.close()
    return users


def create_user_in_db(email: str, password: str, role: str):
    """Create user directly in database"""
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            # Check if user already exists
            cur.execute("SELECT id FROM users WHERE email=%s", (email,))
            if cur.fetchone():
                return False, "User already exists"

            # Create new user
            password_hash = hash_password(password)
            cur.execute("""
                        INSERT INTO users (email, password_hash, role)
                        VALUES (%s, %s, %s)
                        """, (email, password_hash, role))
    conn.close()
    return True, "User created successfully"


def show_admin_panel():
    st.header("Admin / CEO Dashboard")

    # Tab layout for better organization
    tab1, tab2, tab3 = st.tabs(["Users", "Create User", "Candidates"])

    with tab1:
        st.subheader("All Users")
        if st.button("Refresh Users List"):
            st.session_state.refresh_users = True

        try:
            users = get_all_users()
            if users:
                for user in users:
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.write(f"**ID:** {user['id']}")
                    with col2:
                        st.write(f"**Email:** {user['email']}")
                    with col3:
                        st.write(f"**Role:** {user['role']}")
                    with col4:
                        st.write(f"**Created:** {user['created_at'].strftime('%Y-%m-%d')}")
                    st.divider()
            else:
                st.info("No users found")
        except Exception as e:
            st.error(f"Error fetching users: {str(e)}")

    with tab2:
        st.subheader("Create New User")
        email = st.text_input("Email", key="admin_email")
        password = st.text_input("Password", type="password", key="admin_pass")
        role = st.selectbox("Role", ["admin", "ceo", "receptionist", "interviewer", "hr", "candidate"],
                            key="admin_role")

        if st.button("Create User"):
            if email and password:
                success, message = create_user_in_db(email.strip(), password.strip(), role)
                if success:
                    st.success(message)
                    # Clear the form
                    st.session_state.admin_email = ""
                    st.session_state.admin_pass = ""
                else:
                    st.error(message)
            else:
                st.error("Please fill in all fields")

    with tab3:
        st.subheader("All Candidates")
        if st.button("Refresh Candidates List"):
            st.session_state.refresh_candidates = True

        try:
            candidates = get_all_candidates()
            if candidates:
                for candidate in candidates:
                    with st.expander(f"{candidate['name']} ({candidate['email']})"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Candidate ID:** {candidate['candidate_id']}")
                            st.write(f"**Phone:** {candidate['phone']}")
                            st.write(f"**Created by:** {candidate['created_by']}")
                        with col2:
                            st.write(f"**Can Edit:** {candidate['can_edit']}")
                            st.write(f"**Resume:** {candidate['resume_link'] or 'Not uploaded'}")
                            st.write(f"**Created:** {candidate['created_at'].strftime('%Y-%m-%d %H:%M')}")

                        if candidate['form_data']:
                            st.write("**Form Data:**")
                            st.json(candidate['form_data'])
            else:
                st.info("No candidates found")
        except Exception as e:
            st.error(f"Error fetching candidates: {str(e)}")