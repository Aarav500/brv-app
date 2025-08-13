# admin.py
import streamlit as st
from db_postgres import (
    get_conn, hash_password, get_all_candidates, get_all_users,
    create_user_in_db, get_candidate_statistics, get_all_interviews,
    seed_sample_users, init_db
)
from psycopg2.extras import RealDictCursor
import json


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

    # Statistics Overview
    st.subheader("📊 Overview Statistics")
    try:
        stats = get_candidate_statistics()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                "Total Candidates",
                stats.get('total_candidates', 0),
                delta=f"+{stats.get('candidates_today', 0)} today"
            )
        with col2:
            st.metric(
                "With Resume",
                stats.get('candidates_with_resume', 0)
            )
        with col3:
            st.metric(
                "Total Interviews",
                stats.get('total_interviews', 0)
            )
        with col4:
            pass_rate = 0
            if stats.get('total_interviews', 0) > 0:
                pass_rate = round((stats.get('interviews_passed', 0) / stats.get('total_interviews', 0)) * 100, 1)
            st.metric(
                "Pass Rate",
                f"{pass_rate}%"
            )

        # Interview Results Breakdown
        st.subheader("📈 Interview Results")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("✅ Passed", stats.get('interviews_passed', 0))
        with col2:
            st.metric("❌ Failed", stats.get('interviews_failed', 0))
        with col3:
            st.metric("⏳ Pending", stats.get('interviews_pending', 0))

    except Exception as e:
        st.error(f"Error loading statistics: {str(e)}")

    st.markdown("---")

    # Tab layout for better organization
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Candidates", "Interviews", "Users", "Create User", "System"])

    with tab1:
        st.subheader("All Candidates")
        if st.button("Refresh Candidates List"):
            st.session_state.refresh_candidates = True

        try:
            candidates = get_all_candidates()
            if candidates:
                # Search/Filter
                search_term = st.text_input("Search candidates", placeholder="Enter name or email...")

                filtered_candidates = candidates
                if search_term:
                    filtered_candidates = [
                        c for c in candidates
                        if search_term.lower() in str(c.get('name', '')).lower() or
                           search_term.lower() in str(c.get('email', '')).lower()
                    ]

                st.info(f"Showing {len(filtered_candidates)} of {len(candidates)} candidates")

                for candidate in filtered_candidates:
                    with st.expander(f"📋 {candidate['name']} - {candidate['candidate_id']}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Name:** {candidate['name']}")
                            st.write(f"**Email:** {candidate['email']}")
                            st.write(f"**Phone:** {candidate.get('phone', 'N/A')}")
                            st.write(f"**Can Edit:** {candidate.get('can_edit', False)}")
                        with col2:
                            st.write(f"**Created by:** {candidate.get('created_by', 'N/A')}")
                            st.write(f"**Created:** {candidate.get('created_at', 'N/A')}")
                            if candidate.get('resume_link'):
                                st.markdown(f"**Resume:** [View Resume]({candidate['resume_link']})")
                            else:
                                st.write("**Resume:** Not uploaded")

                        if candidate.get('form_data'):
                            st.write("**Application Data:**")
                            form_data = candidate['form_data']
                            if isinstance(form_data, dict):
                                if form_data.get('skills'):
                                    st.write(f"**Skills:** {form_data['skills']}")
                                if form_data.get('experience'):
                                    st.write(f"**Experience:** {form_data['experience']}")
                                if form_data.get('education'):
                                    st.write(f"**Education:** {form_data['education']}")
                            else:
                                st.json(form_data)
            else:
                st.info("No candidates found")
        except Exception as e:
            st.error(f"Error fetching candidates: {str(e)}")

    with tab2:
        st.subheader("All Interviews")
        try:
            interviews = get_all_interviews()
            if interviews:
                # Filter by result
                result_filter = st.selectbox(
                    "Filter by result",
                    ["All", "scheduled", "completed", "pass", "fail", "on_hold"]
                )

                filtered_interviews = interviews
                if result_filter != "All":
                    filtered_interviews = [i for i in interviews if i.get('result') == result_filter]

                st.info(f"Showing {len(filtered_interviews)} of {len(interviews)} interviews")

                for interview in filtered_interviews:
                    with st.expander(f"🎯 {interview['candidate_name']} - {interview.get('result', 'Pending')}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Candidate:** {interview['candidate_name']}")
                            st.write(f"**Email:** {interview.get('candidate_email', 'N/A')}")
                            st.write(f"**Candidate ID:** {interview['candidate_id']}")
                            st.write(f"**Scheduled:** {interview.get('scheduled_at', 'N/A')}")
                        with col2:
                            st.write(f"**Interviewer:** {interview.get('interviewer', 'N/A')}")
                            st.write(f"**Result:** {interview.get('result', 'Pending')}")
                            st.write(f"**Created:** {interview.get('created_at', 'N/A')}")

                        if interview.get('notes'):
                            st.write("**Notes:**")
                            st.write(interview['notes'])
            else:
                st.info("No interviews found")
        except Exception as e:
            st.error(f"Error fetching interviews: {str(e)}")

    with tab3:
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

    with tab4:
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

    with tab5:
        st.subheader("System Management")

        col1, col2 = st.columns(2)

        with col1:
            st.write("**Database Operations**")
            if st.button("Initialize Database"):
                try:
                    init_db()
                    st.success("Database initialized successfully!")
                except Exception as e:
                    st.error(f"Database initialization failed: {str(e)}")

            if st.button("Seed Sample Users"):
                try:
                    seed_sample_users()
                    st.success("Sample users created!")
                    st.info(
                        "Sample users: admin@brv.com, ceo@brv.com, receptionist@brv.com, interviewer@brv.com, hr@brv.com, candidate@brv.com (all with password same as username)")
                except Exception as e:
                    st.error(f"Failed to create sample users: {str(e)}")

        with col2:
            st.write("**System Information**")
            try:
                conn = get_conn()
                with conn:
                    with conn.cursor() as cur:
                        # Check database version
                        cur.execute("SELECT version()")
                        db_version = cur.fetchone()[0]
                        st.write(f"**Database:** {db_version.split(',')[0]}")

                        # Check table counts
                        cur.execute("SELECT COUNT(*) FROM users")
                        user_count = cur.fetchone()[0]
                        st.write(f"**Users:** {user_count}")

                        cur.execute("SELECT COUNT(*) FROM candidates")
                        candidate_count = cur.fetchone()[0]
                        st.write(f"**Candidates:** {candidate_count}")

                        cur.execute("SELECT COUNT(*) FROM interviews")
                        interview_count = cur.fetchone()[0]
                        st.write(f"**Interviews:** {interview_count}")

                conn.close()
            except Exception as e:
                st.error(f"Error getting system info: {str(e)}")

        st.markdown("---")
        st.subheader("Export Data")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("Export Candidates"):
                try:
                    candidates = get_all_candidates()
                    if candidates:
                        # Convert to JSON for download
                        import json
                        candidates_json = []
                        for c in candidates:
                            # Convert datetime objects to strings
                            candidate_dict = dict(c)
                            if candidate_dict.get('created_at'):
                                candidate_dict['created_at'] = str(candidate_dict['created_at'])
                            if candidate_dict.get('updated_at'):
                                candidate_dict['updated_at'] = str(candidate_dict['updated_at'])
                            candidates_json.append(candidate_dict)

                        st.download_button(
                            label="Download Candidates JSON",
                            data=json.dumps(candidates_json, indent=2),
                            file_name="candidates_export.json",
                            mime="application/json"
                        )
                    else:
                        st.info("No candidates to export")
                except Exception as e:
                    st.error(f"Export failed: {str(e)}")

        with col2:
            if st.button("Export Interviews"):
                try:
                    interviews = get_all_interviews()
                    if interviews:
                        import json
                        interviews_json = []
                        for i in interviews:
                            interview_dict = dict(i)
                            # Convert datetime objects to strings
                            for key, value in interview_dict.items():
                                if hasattr(value, 'isoformat'):
                                    interview_dict[key] = str(value)
                            interviews_json.append(interview_dict)

                        st.download_button(
                            label="Download Interviews JSON",
                            data=json.dumps(interviews_json, indent=2),
                            file_name="interviews_export.json",
                            mime="application/json"
                        )
                    else:
                        st.info("No interviews to export")
                except Exception as e:
                    st.error(f"Export failed: {str(e)}")

        with col3:
            if st.button("Export Users"):
                try:
                    users = get_all_users()
                    if users:
                        import json
                        users_json = []
                        for u in users:
                            user_dict = dict(u)
                            if user_dict.get('created_at'):
                                user_dict['created_at'] = str(user_dict['created_at'])
                            # Remove password hash for security
                            user_dict.pop('password_hash', None)
                            users_json.append(user_dict)

                        st.download_button(
                            label="Download Users JSON",
                            data=json.dumps(users_json, indent=2),
                            file_name="users_export.json",
                            mime="application/json"
                        )
                    else:
                        st.info("No users to export")
                except Exception as e:
                    st.error(f"Export failed: {str(e)}")