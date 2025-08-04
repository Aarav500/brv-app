import streamlit as st
import os
import sqlite3
from datetime import datetime
import uuid
import qrcode
from PIL import Image
import io
import pandas as pd
from auth import forgot_password_page
from firebase_db import authenticate as firebase_authenticate, update_password as firebase_update_password

# Set page configuration
st.set_page_config(
    page_title="BRV Applicant Management System",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Database setup
def init_db():
    conn = sqlite3.connect('data/brv_applicants.db')
    c = conn.cursor()

    # Create users table
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Create applicants table
    c.execute('''
    CREATE TABLE IF NOT EXISTS applicants (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        address TEXT,
        resume_path TEXT,
        form_data TEXT,
        speed_test_result TEXT,
        status TEXT DEFAULT 'new',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Create interviews table
    c.execute('''
    CREATE TABLE IF NOT EXISTS interviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id INTEGER,
        interviewer_id TEXT,
        interviewer_name TEXT,
        scheduled_time TEXT,
        feedback TEXT,
        status TEXT DEFAULT 'scheduled',
        result TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()
    conn.close()

# Initialize the database
init_db()

# Authentication functions
def authenticate(email, password):
    """Authenticate a user with email and password"""
    # Use Firebase authentication
    return firebase_authenticate(email, password)

def update_password(user_id, new_password):
    """Update a user's password and reset the force_password_reset flag"""
    # Use Firebase password update
    return firebase_update_password(user_id, new_password)


# Session state initialization
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'user_role' not in st.session_state:
    st.session_state.user_role = None

# Login page

def login_page():
    st.title("BRV Applicant Management System")

    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")

        if submit:
            # Check if email is a valid office email
            if not email.endswith("@bluematrixit.com"):
                st.error("Only official Bluematrix emails are allowed.")
                return

            # Use the authenticate function
            user = authenticate(email, password)

            if user:

                st.session_state.authenticated = True
                st.session_state.user_id = user.get("id", "")
                st.session_state.email = email
                st.session_state.user_role = user.get("role", "[no-role]")
                
                # Fetch candidate ID from Google Sheet
                from utils import fetch_google_form_responses
                form_df = fetch_google_form_responses()
                
                # Find the email column
                email_col = None
                for col in form_df.columns:
                    if 'email' in col.lower():
                        email_col = col
                        break
                
                # Find the Candidate ID column
                candidate_id_col = None
                for col in form_df.columns:
                    if 'candidate id' in col.lower() or 'application id' in col.lower():
                        candidate_id_col = col
                        break
                
                # If we found both columns, try to get the candidate ID
                if email_col and candidate_id_col and not form_df.empty:
                    # Find the row with the matching email
                    matching_rows = form_df[form_df[email_col] == email]
                    if not matching_rows.empty:
                        candidate_id = matching_rows.iloc[0][candidate_id_col]
                        st.success(f"Login successful! Your Candidate ID is: `{candidate_id}`")
                    else:
                        st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid email or password")

    # Add forgot password link outside the form
    if st.button("Forgot Password?"):
        st.session_state.show_forgot_password = True
        st.rerun()

# Main application
def main():
    if st.session_state.show_forgot_password:
        # If user successfully resets password, return to login page
        if forgot_password_page():
            st.session_state.show_forgot_password = False
            st.rerun()
    elif not st.session_state.authenticated:
        login_page()
    else:
        # Sidebar for navigation
        st.sidebar.title("Navigation")

        if st.session_state.user_role == "receptionist":
            from receptionist import receptionist_view
            receptionist_view()

        elif st.session_state.user_role == "interviewer":
            page = st.sidebar.radio("Go to", ["Walk-in Candidates", "Schedule Interview", "Scheduled Interviews", "Past Interviews"])
            if page == "Walk-in Candidates":
                from interviewer import interviewer_view
                interviewer_view()
            elif page == "Schedule Interview":
                from schedule_interview import schedule_interview_page
                schedule_interview_page()
            elif page == "Scheduled Interviews":
                interviewer_scheduled_page()
            elif page == "Past Interviews":
                interviewer_past_page()

        elif st.session_state.user_role == "ceo":
            page = st.sidebar.radio("Go to", ["Dashboard", "All Applicants", "Interview Results"])
            if page == "Dashboard":
                ceo_dashboard_page()
            elif page == "All Applicants":
                ceo_applicants_page()
            elif page == "Interview Results":
                ceo_results_page()

        # Logout button
        if st.sidebar.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.user_id = None
            st.session_state.user_role = None
            st.rerun()

# Placeholder functions for different pages
def receptionist_new_applicant_page():
    st.title("New Applicant Registration")

    # QR Code generation for form filling
    st.subheader("QR Code for Application Form")
    form_url = "https://brv-application-form.com"  # This would be replaced with the actual form URL
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(form_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # Convert PIL image to bytes
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    byte_im = buf.getvalue()

    # Display QR code
    st.image(byte_im, caption="Scan to fill application form", width=300)

    # Manual form for testing
    st.subheader("Or Fill Form Manually")
    with st.form("applicant_form"):
        name = st.text_input("Full Name")
        email = st.text_input("Email")
        phone = st.text_input("Phone Number")
        address = st.text_area("Address")

        # Resume upload
        resume_file = st.file_uploader("Upload Resume (PDF/DOC)", type=["pdf", "doc", "docx"])

        # Additional fields for receptionist
        speed_test = st.text_input("Speed Test Result")

        submit = st.form_submit_button("Submit")

        if submit:
            if name and email:
                # Save applicant information
                applicant_id = str(uuid.uuid4())

                # Save resume if uploaded
                resume_path = None
                if resume_file:
                    # Create directory if it doesn't exist
                    os.makedirs("cvs", exist_ok=True)
                    # Use Candidate ID for filename standardization
                    resume_path = f"cvs/CV_{applicant_id}.pdf"
                    with open(resume_path, "wb") as f:
                        f.write(resume_file.getbuffer())

                # Save to database
                conn = sqlite3.connect('data/brv_applicants.db')
                c = conn.cursor()
                c.execute(
                    "INSERT INTO applicants (id, name, email, phone, address, resume_path, speed_test_result, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (applicant_id, name, email, phone, address, resume_path, speed_test, "new")
                )
                conn.commit()
                conn.close()

                st.success("Applicant registered successfully!")
            else:
                st.error("Name and Email are required fields.")

def receptionist_profiles_page():
    st.title("Applicant Profiles")

    # Fetch all applicants
    conn = sqlite3.connect('data/brv_applicants.db')
    applicants_df = pd.read_sql_query("SELECT id, name, email, phone, status, created_at FROM applicants ORDER BY created_at DESC", conn)
    conn.close()

    if not applicants_df.empty:
        st.dataframe(applicants_df)

        # Select applicant to view/edit
        selected_applicant = st.selectbox("Select Applicant to View/Edit", applicants_df['name'].tolist())

        if selected_applicant:
            applicant_id = applicants_df[applicants_df['name'] == selected_applicant]['id'].iloc[0]

            # Fetch applicant details
            conn = sqlite3.connect('data/brv_applicants.db')
            c = conn.cursor()
            c.execute("SELECT * FROM applicants WHERE id = ?", (applicant_id,))
            applicant = c.fetchone()
            conn.close()

            if applicant:
                st.subheader(f"Profile: {applicant[1]}")  # applicant[1] is the name

                # Display current info
                st.write(f"Email: {applicant[2]}")
                st.write(f"Phone: {applicant[3]}")
                st.write(f"Address: {applicant[4]}")

                # Resume download if available
                if applicant[5]:  # applicant[5] is resume_path
                    st.write(f"Resume: {os.path.basename(applicant[5])}")
                    # In a real app, add a download button here

                # Edit form
                with st.form("edit_profile"):
                    new_speed_test = st.text_input("Speed Test Result", value=applicant[7] if applicant[7] else "")
                    new_status = st.selectbox("Status", ["new", "in_process", "interviewed", "hired", "rejected"], index=["new", "in_process", "interviewed", "hired", "rejected"].index(applicant[8]))

                    submit = st.form_submit_button("Update Profile")

                    if submit:
                        conn = sqlite3.connect('data/brv_applicants.db')
                        c = conn.cursor()
                        c.execute(
                            "UPDATE applicants SET speed_test_result = ?, status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                            (new_speed_test, new_status, applicant_id)
                        )
                        conn.commit()
                        conn.close()
                        st.success("Profile updated successfully!")
    else:
        st.info("No applicants registered yet.")

def interviewer_scheduled_page():
    st.title("Scheduled Interviews")

    # Fetch scheduled interviews
    conn = sqlite3.connect('data/brv_applicants.db')
    interviews_df = pd.read_sql_query(
        """
        SELECT i.id, a.name, i.scheduled_time, i.status
        FROM interviews i
        JOIN applicants a ON i.applicant_id = a.id
        WHERE i.interviewer_id = ? AND i.status = 'scheduled'
        ORDER BY i.scheduled_time
        """,
        conn,
        params=(st.session_state.user_id,)
    )
    conn.close()

    if not interviews_df.empty:
        st.dataframe(interviews_df)

        # Select interview to conduct
        selected_interview = st.selectbox("Select Interview to Conduct", interviews_df['id'].tolist())

        if selected_interview:
            # Fetch applicant details
            conn = sqlite3.connect('data/brv_applicants.db')
            applicant_id = pd.read_sql_query(
                "SELECT applicant_id FROM interviews WHERE id = ?",
                conn,
                params=(selected_interview,)
            ).iloc[0][0]

            applicant = pd.read_sql_query(
                "SELECT * FROM applicants WHERE id = ?",
                conn,
                params=(applicant_id,)
            ).iloc[0]
            conn.close()

            # Display applicant info
            st.subheader(f"Interview with {applicant['name']}")
            st.write(f"Email: {applicant['email']}")
            st.write(f"Phone: {applicant['phone']}")

            # Display resume if available
            if applicant['resume_path']:
                st.subheader("Candidate Resume")
                # Import the resume handler functions
                from resume_handler import display_resume
                import streamlit.components.v1 as components

                # Check if it's a Google Drive link or a local path
                resume_path = applicant['resume_path']

                # Create columns for resume and notes
                resume_col, notes_col = st.columns([3, 1])

                with resume_col:
                    if resume_path.startswith('http'):
                        # It's a URL (likely Google Drive)
                        # Extract file ID if it's a Google Drive link
                        from resume_handler import is_google_drive_link, extract_file_id
                        if is_google_drive_link(resume_path):
                            file_id = extract_file_id(resume_path)
                            if file_id:
                                # Create an iframe to embed the document preview
                                preview_url = f"https://drive.google.com/file/d/{file_id}/preview"
                                components.iframe(preview_url, height=800, width=1000)
                                st.markdown(f"[📄 View Resume in Google Drive]({resume_path})", unsafe_allow_html=True)
                            else:
                                display_resume(resume_path, applicant['name'])
                        else:
                            display_resume(resume_path, applicant['name'])
                    else:
                        # It's a local file path
                        display_resume(resume_path, applicant['name'])

                with notes_col:
                    st.subheader("Resume Notes")

                    # Get existing notes if any
                    conn = sqlite3.connect('data/brv_applicants.db')
                    c = conn.cursor()

                    # Check if the resume_notes table exists, create if not
                    c.execute("""
                    CREATE TABLE IF NOT EXISTS resume_notes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        interview_id INTEGER,
                        interviewer_id TEXT,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(interview_id) REFERENCES interviews(id)
                    )
                    """)

                    # Get existing notes
                    c.execute("""
                    SELECT notes FROM resume_notes 
                    WHERE interview_id = ? AND interviewer_id = ?
                    """, (selected_interview, st.session_state.user_id))

                    existing_notes = c.fetchone()
                    existing_notes = existing_notes[0] if existing_notes else ""

                    # Notes text area
                    resume_notes = st.text_area(
                        "Take notes while reviewing the resume",
                        value=existing_notes,
                        height=400,
                        placeholder="Note important points, skills, questions to ask..."
                    )

                    # Save notes button
                    if st.button("Save Resume Notes"):
                        if existing_notes:
                            # Update existing notes
                            c.execute("""
                            UPDATE resume_notes 
                            SET notes = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE interview_id = ? AND interviewer_id = ?
                            """, (resume_notes, selected_interview, st.session_state.user_id))
                        else:
                            # Insert new notes
                            c.execute("""
                            INSERT INTO resume_notes (interview_id, interviewer_id, notes)
                            VALUES (?, ?, ?)
                            """, (selected_interview, st.session_state.user_id, resume_notes))

                        conn.commit()
                        st.success("Notes saved successfully!")

                    conn.close()

                    # Add highlighting tips
                    with st.expander("Highlighting Tips"):
                        st.markdown("""
                        **How to highlight important points:**
                        - Use **asterisks** for important skills
                        - Use 🟢 for positive points
                        - Use 🔴 for concerns
                        - Use ❓ for questions to ask

                        Your notes are saved per candidate and only visible to you.
                        """)
            else:
                st.warning("⚠️ No resume available for this candidate.")

            # Display speed test results
            st.write(f"Speed Test Result: {applicant['speed_test_result']}")

            # Interview form
            with st.form("interview_form"):
                notes = st.text_area("Interview Notes")
                result = st.selectbox("Interview Result", ["pass", "fail", "on_hold"])

                submit = st.form_submit_button("Submit Interview Results")

                if submit:
                    conn = sqlite3.connect('data/brv_applicants.db')
                    c = conn.cursor()
                    c.execute(
                        "UPDATE interviews SET notes = ?, result = ?, status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (notes, result, selected_interview)
                    )

                    # Update applicant status based on interview result
                    new_status = "interviewed"
                    if result == "pass":
                        new_status = "passed_interview"
                    elif result == "fail":
                        new_status = "failed_interview"
                    elif result == "on_hold":
                        new_status = "on_hold"

                    c.execute(
                        "UPDATE applicants SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (new_status, applicant_id)
                    )

                    conn.commit()
                    conn.close()
                    st.success("Interview results submitted successfully!")
    else:
        st.info("No scheduled interviews.")

def interviewer_past_page():
    st.title("Past Interviews")

    # Fetch past interviews
    conn = sqlite3.connect('data/brv_applicants.db')
    interviews_df = pd.read_sql_query(
        """
        SELECT i.id, a.name, i.scheduled_time, i.result, i.notes
        FROM interviews i
        JOIN applicants a ON i.applicant_id = a.id
        WHERE i.interviewer_id = ? AND i.status = 'completed'
        ORDER BY i.scheduled_time DESC
        """,
        conn,
        params=(st.session_state.user_id,)
    )
    conn.close()

    if not interviews_df.empty:
        st.dataframe(interviews_df)
    else:
        st.info("No past interviews.")

def ceo_dashboard_page():
    st.title("CEO Dashboard")

    # Fetch statistics
    conn = sqlite3.connect('data/brv_applicants.db')

    # Total applicants
    total_applicants = pd.read_sql_query("SELECT COUNT(*) FROM applicants", conn).iloc[0][0]

    # Applicants by status
    status_counts = pd.read_sql_query(
        "SELECT status, COUNT(*) as count FROM applicants GROUP BY status",
        conn
    )

    # Interview results
    interview_results = pd.read_sql_query(
        "SELECT result, COUNT(*) as count FROM interviews WHERE status = 'completed' GROUP BY result",
        conn
    )

    # Recent applicants
    recent_applicants = pd.read_sql_query(
        "SELECT name, email, status, created_at FROM applicants ORDER BY created_at DESC LIMIT 5",
        conn
    )

    conn.close()

    # Display statistics
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Applicant Statistics")
        st.metric("Total Applicants", total_applicants)

        st.subheader("Applicants by Status")
        if not status_counts.empty:
            st.bar_chart(status_counts.set_index('status'))
        else:
            st.info("No applicant data available.")

    with col2:
        st.subheader("Interview Results")
        if not interview_results.empty:
            st.bar_chart(interview_results.set_index('result'))
        else:
            st.info("No interview data available.")

        st.subheader("Recent Applicants")
        if not recent_applicants.empty:
            st.dataframe(recent_applicants)
        else:
            st.info("No recent applicants.")

def ceo_applicants_page():
    st.title("All Applicants")

    # Fetch all applicants
    conn = sqlite3.connect('data/brv_applicants.db')
    applicants_df = pd.read_sql_query(
        "SELECT id, name, email, phone, status, created_at FROM applicants ORDER BY created_at DESC",
        conn
    )
    conn.close()

    if not applicants_df.empty:
        # Filters
        status_filter = st.multiselect(
            "Filter by Status",
            options=applicants_df['status'].unique().tolist(),
            default=applicants_df['status'].unique().tolist()
        )

        filtered_df = applicants_df[applicants_df['status'].isin(status_filter)]

        st.dataframe(filtered_df)

        # Select applicant to view details
        selected_applicant = st.selectbox("Select Applicant to View Details", filtered_df['name'].tolist())

        if selected_applicant:
            applicant_id = filtered_df[filtered_df['name'] == selected_applicant]['id'].iloc[0]

            # Fetch applicant details
            conn = sqlite3.connect('data/brv_applicants.db')
            applicant = pd.read_sql_query(
                "SELECT * FROM applicants WHERE id = ?",
                conn,
                params=(applicant_id,)
            ).iloc[0]

            # Fetch interview details
            interviews = pd.read_sql_query(
                """
                SELECT i.scheduled_time, u.username as interviewer, i.result, i.notes
                FROM interviews i
                JOIN users u ON i.interviewer_id = u.id
                WHERE i.applicant_id = ?
                ORDER BY i.scheduled_time DESC
                """,
                conn,
                params=(applicant_id,)
            )
            conn.close()

            # Display applicant details
            st.subheader(f"Applicant: {applicant['name']}")
            st.write(f"Email: {applicant['email']}")
            st.write(f"Phone: {applicant['phone']}")
            st.write(f"Address: {applicant['address']}")
            st.write(f"Status: {applicant['status']}")
            st.write(f"Speed Test Result: {applicant['speed_test_result']}")

            # Display resume if available
            if applicant['resume_path']:
                st.write(f"Resume: {os.path.basename(applicant['resume_path'])}")
                # In a real app, add a download button here

            # Display interview history
            if not interviews.empty:
                st.subheader("Interview History")
                st.dataframe(interviews)
            else:
                st.info("No interviews conducted yet.")
    else:
        st.info("No applicants registered yet.")

def ceo_results_page():
    st.title("Interview Results")

    # Fetch all interviews
    conn = sqlite3.connect('data/brv_applicants.db')
    interviews_df = pd.read_sql_query(
        """
        SELECT i.id, a.name as applicant, u.username as interviewer, 
               i.scheduled_time, i.result, i.status
        FROM interviews i
        JOIN applicants a ON i.applicant_id = a.id
        JOIN users u ON i.interviewer_id = u.id
        ORDER BY i.scheduled_time DESC
        """,
        conn
    )
    conn.close()

    if not interviews_df.empty:
        # Filters
        status_filter = st.multiselect(
            "Filter by Status",
            options=interviews_df['status'].unique().tolist(),
            default=interviews_df['status'].unique().tolist()
        )

        result_filter = st.multiselect(
            "Filter by Result",
            options=interviews_df['result'].unique().tolist(),
            default=interviews_df['result'].unique().tolist()
        )

        filtered_df = interviews_df[
            interviews_df['status'].isin(status_filter) & 
            interviews_df['result'].isin(result_filter)
        ]

        st.dataframe(filtered_df)

        # Select interview to view details
        selected_interview = st.selectbox("Select Interview to View Details", filtered_df['id'].tolist())

        if selected_interview:
            # Fetch interview details
            conn = sqlite3.connect('data/brv_applicants.db')
            interview = pd.read_sql_query(
                """
                SELECT i.*, a.name as applicant_name, u.username as interviewer_name
                FROM interviews i
                JOIN applicants a ON i.applicant_id = a.id
                JOIN users u ON i.interviewer_id = u.id
                WHERE i.id = ?
                """,
                conn,
                params=(selected_interview,)
            ).iloc[0]
            conn.close()

            # Display interview details
            st.subheader(f"Interview Details: {interview['applicant_name']}")
            st.write(f"Interviewer: {interview['interviewer_name']}")
            st.write(f"Scheduled Time: {interview['scheduled_time']}")
            st.write(f"Status: {interview['status']}")
            st.write(f"Result: {interview['result']}")
            st.write(f"Notes: {interview['notes']}")
    else:
        st.info("No interviews conducted yet.")

# Run the app
if __name__ == "__main__":
    main()
