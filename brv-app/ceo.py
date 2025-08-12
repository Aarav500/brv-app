import streamlit as st
import pandas as pd
from mysql_db import get_db_connection
from datetime import datetime

# Reuse the Postgres candidate helper from candidate_view (or query directly)
def fetch_all_candidates():
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT candidate_id::text AS id,
                       full_name AS name,
                       email,
                       phone,
                       resume_link,
                       interview_status,
                       timestamp
                FROM candidates
                ORDER BY timestamp DESC
            """)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
            return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()

def get_db_size_gb():
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_database_size(current_database())")
            size_bytes = cur.fetchone()[0]
            return size_bytes / (1024*1024*1024)
    except Exception as e:
        st.error(f"Error measuring DB size: {e}")
        return None
    finally:
        conn.close()

def ceo_view():
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Dashboard", "All Candidates", "Interview Results", "User Management"])

    # Check DB usage and show a warning on dashboard if > 5 GB
    db_size = get_db_size_gb()
    if st.session_state.get("user_role") == "ceo" and db_size is not None:
        if db_size >= 5:
            st.warning(f"⚠️ Database usage is {db_size:.2f} GB. Consider archiving or moving files to Google Drive. (Default plan limit may be 5GB.)")

    if page == "Dashboard":
        ceo_dashboard_page()
    elif page == "All Candidates":
        ceo_candidates_page()
    elif page == "Interview Results":
        ceo_results_page()
    elif page == "User Management":
        ceo_users_page()

def ceo_dashboard_page():
    st.title("📊 CEO Dashboard - BRV")
    candidates = fetch_all_candidates()
    if not candidates:
        st.warning("No candidate data available.")
        return
    df = pd.DataFrame(candidates)
    total = len(df)
    scheduled = len(df[df["interview_status"] == "Scheduled"]) if "interview_status" in df.columns else 0
    passed = len(df[df["interview_status"] == "Pass"]) if "interview_status" in df.columns else 0
    failed = len(df[df["interview_status"] == "Fail"]) if "interview_status" in df.columns else 0
    st.subheader("📈 Summary")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total candidates", total)
    c2.metric("Interviews scheduled", scheduled)
    c3.metric("Passed", passed)

    st.subheader("Recent candidates")
    st.dataframe(df.head(50), use_container_width=True)

def ceo_candidates_page():
    st.title("All Candidates")
    candidates = fetch_all_candidates()
    if not candidates:
        st.info("No candidates.")
        return
    df = pd.DataFrame(candidates)
    st.dataframe(df, use_container_width=True)

def ceo_results_page():
    st.title("Interview Results")
    candidates = fetch_all_candidates()
    if not candidates:
        st.info("No candidates.")
        return
    df = pd.DataFrame(candidates)
    if "interview_status" in df.columns:
        st.dataframe(df[["id","name","email","interview_status"]], use_container_width=True)
    else:
        st.info("No interview status recorded.")

def ceo_users_page():
    st.title("User Management")
    # show a link to admin page or simple note
    st.info("Use the Admin panel to manage users.")
