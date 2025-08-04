import streamlit as st
import pandas as pd
from mysql_db import get_all_users, create_user, add_user, remove_user, update_user_password, update_user_role
from mysql_db import get_password_expiry_policy, update_password_expiry_policy, force_password_reset_all
from utils import VALID_ROLES

def show_admin_panel():
    """
    Wrapper function for the admin dashboard.
    This is called from main.py.
    """
    st.header("👤 CEO Control Panel")
    st.subheader("User Management")

    # Call the existing admin view function
    admin_view()

def admin_view():
    """
    Main view for the admin/CEO dashboard.
    """
    st.title("👑 Admin Dashboard")

    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["User Management", "System Overview", "Candidate Statistics"])

    if page == "User Management":
        user_management_page()
    elif page == "System Overview":
        system_overview_page()
    elif page == "Candidate Statistics":
        candidate_statistics_page()

def user_management_page():
    """
    Page for managing users (add, remove, reset password, assign roles).
    """
    st.header("👥 User Management")

    # Tabs for different user management functions
    tab1, tab2, tab3, tab4 = st.tabs(["View Users", "Add User", "Modify User", "Password Policy"])

    with tab1:
        st.subheader("Current Users")
        users = get_all_users()

        if users:
            # Create a DataFrame for display
            users_df = pd.DataFrame([
                {
                    "Email": user.get("email", "N/A"),
                    "Role": user.get("role", ""),
                    "Password Reset Required": "Yes" if user.get("force_password_reset", True) else "No",
                    "Last Password Change": user.get("last_password_change", "") or "Never"
                }
                for user in users
            ])

            st.dataframe(users_df)
        else:
            st.info("No users found in the system.")

    with tab2:
        st.subheader("Add New User")

        with st.form("add_user_form"):
            username = st.text_input("Email", placeholder="john.doe@bluematrixit.com")
            password = st.text_input("Initial Password", type="password")
            role = st.selectbox("Role", VALID_ROLES)

            submit = st.form_submit_button("Add User")

            if submit:
                if not username or not password:
                    st.error("Username and password are required.")
                else:
                    try:
                        # Add user to both database and YAML
                        success, message = add_user(username, password, role)
                        create_user(username, password, role)

                        if success:
                            st.success(f"✅ User {username} added successfully.")
                        else:
                            st.error(f"❌ {message}")
                    except Exception as e:
                        st.error(f"❌ Error adding user: {str(e)}")

    with tab3:
        st.subheader("Modify Existing User")

        users = get_all_users()
        if not users:
            st.info("No users found in the system.")
            return

        # Create a selection box with emails
        user_options = [f"{user.get('email', '[no-email]')} ({user.get('role', '[no-role]')})" for user in users]
        selected_user = st.selectbox("Select User", user_options)

        if selected_user:
            # Extract email from selection
            selected_email = selected_user.split(" (")[0]

            # Find the user in the list
            user = next((u for u in users if u.get("email", "") == selected_email), None)

            if user:
                st.write(f"**User ID:** {user.get('id', '[no-id]')}")
                new_email = st.text_input("Change Email", value=user.get("email", ""))
                st.write(f"**Current Role:** {user.get('role', '')}")
                st.write(f"**Password Reset Required:** {'Yes' if user.get('force_password_reset', True) else 'No'}")
                st.write(f"**Last Password Change:** {user.get('last_password_change', '') or 'Never'}")

                # Actions
                col1, col2, col3 = st.columns(3)

                with col1:
                    if st.button("Reset Password"):
                        # Generate a random password
                        import random
                        import string
                        new_password = ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=12))

                        # Reset password in database
                        success = update_user_password(user.get("id", ""), new_password)

                        if success:
                            success = True
                            message = "Password reset successfully"
                            st.success(f"✅ Password reset to: **{new_password}**")
                            st.info("The user will be required to change this password on next login.")
                        else:
                            st.error(f"❌ {message}")

                with col2:
                    # Find the index of the current role in VALID_ROLES, defaulting to 0 if not found
                    try:
                        current_role_index = VALID_ROLES.index(user.get("role", "").lower())
                    except ValueError:
                        current_role_index = 0

                    new_role = st.selectbox("New Role", VALID_ROLES, index=current_role_index)
                    if st.button("Change Role"):
                        # Update role and email in database
                        success, message = update_user_role(user.get("id", ""), new_role, new_email)

                        if success:
                            if new_email != user.get("email", ""):
                                st.success(f"✅ Role updated to {new_role} and email updated to {new_email}")
                            else:
                                st.success(f"✅ Role updated to {new_role}")
                            # Refresh the page to show updated information
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")

                with col3:
                    if st.button("Remove User"):
                        # Check if user is CEO
                        if user.get("role", "").lower() == "ceo":
                            st.error("❌ Cannot delete CEO account!")
                        else:
                            # Confirm deletion
                            if st.session_state.get('confirm_delete') != user.get("id", ""):
                                st.session_state['confirm_delete'] = user.get("id", "")
                                st.warning(f"Are you sure you want to remove {user.get('email', '')}? Click again to confirm.")
                            else:
                                # Delete from database
                                success, message = remove_user(user.get("id", ""))

                                if success:
                                    st.success(f"✅ User {user.get('email', '')} removed successfully.")
                                    st.session_state['confirm_delete'] = None
                                    st.rerun()  # Refresh the page
                                else:
                                    st.error(f"❌ {message}")

    with tab4:
        st.subheader("Password Policy Settings")

        # Get current policy
        current_policy = get_password_expiry_policy()

        st.write("Set how often users must change their passwords.")
        st.write(f"Current setting: **{current_policy} days**")

        with st.form("password_policy_form"):
            new_policy = st.number_input(
                "Password expiry (days)", 
                min_value=1, 
                max_value=365, 
                value=current_policy,
                help="Number of days after which passwords expire and must be changed."
            )

            submit = st.form_submit_button("Update Policy")

            if submit:
                success, message = update_password_expiry_policy(new_policy)
                if success:
                    st.success(f"✅ {message}")
                else:
                    st.error(f"❌ {message}")

        # Add option to force password reset for all users
        st.subheader("Force Password Reset")
        st.write("You can force all users to reset their passwords on next login.")

        if st.button("Force All Users to Reset Passwords"):
            users = get_all_users()
            if not users:
                st.info("No users found in the system.")
            else:
                # Force password reset for all users
                if force_password_reset_all():
                    st.success("✅ All users will be required to reset their passwords on next login.")
                else:
                    st.error("❌ Failed to force password reset for all users.")

        # Add a section for password security information
        st.subheader("Password Security Information")
        st.write("""
        **Password Requirements:**
        - At least 8 characters long
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        - At least one special character

        **Password Security Best Practices:**
        - Use unique passwords for different accounts
        - Avoid using personal information in passwords
        - Change passwords regularly
        - Use a password manager to store complex passwords
        """)


def system_overview_page():
    """
    Page showing system overview statistics.
    """
    st.header("📊 System Overview")

    # Get user statistics
    users = get_all_users()
    total_users = len(users)
    roles = {}
    for user in users:
        role = user.get("role", "unknown").lower()  # Standardize role to lowercase
        roles[role] = roles.get(role, 0) + 1

    # Display user statistics
    st.subheader("User Statistics")
    st.write(f"**Total Users:** {total_users}")

    # Create a DataFrame for role distribution
    role_df = pd.DataFrame({
        "Role": list(roles.keys()),
        "Count": list(roles.values())
    })

    # Display role distribution
    st.bar_chart(role_df.set_index("Role"))

    # System health checks
    st.subheader("System Health")

    # Check for users with password resets required
    reset_required = sum(1 for user in users if user.get("force_password_reset", False))
    if reset_required > 0:
        st.warning(f"⚠️ {reset_required} users have password resets pending.")
    else:
        st.success("✅ All users have updated passwords.")

    # Check database connection
    try:
        import sqlite3
        conn = sqlite3.connect('data/brv_applicants.db')
        conn.cursor()
        conn.close()
        st.success("✅ Database connection is working.")
    except Exception as e:
        st.error(f"❌ Database connection error: {str(e)}")

def candidate_statistics_page():
    """
    Page showing candidate statistics.
    """
    st.header("👨‍💼 Candidate Statistics")

    # Get candidate statistics from database
    try:
        import sqlite3
        conn = sqlite3.connect('data/brv_applicants.db')
        c = conn.cursor()

        # Total candidates
        c.execute("SELECT COUNT(*) FROM candidates")
        total_candidates = c.fetchone()[0]

        # Candidates by status
        c.execute("SELECT status, COUNT(*) FROM candidates GROUP BY status")
        status_counts = c.fetchall()

        # Recent interviews
        c.execute("""
            SELECT c.name, i.interviewer_name, i.scheduled_time, i.result
            FROM interviews i
            JOIN candidates c ON i.candidate_id = c.id
            ORDER BY i.scheduled_time DESC
            LIMIT 5
        """)
        recent_interviews = c.fetchall()

        conn.close()

        # Display statistics
        st.subheader("Candidate Overview")
        st.write(f"**Total Candidates:** {total_candidates}")

        # Display status distribution
        if status_counts:
            status_df = pd.DataFrame(status_counts, columns=["Status", "Count"])
            st.write("**Candidates by Status:**")
            st.bar_chart(status_df.set_index("Status"))

        # Display recent interviews
        if recent_interviews:
            st.subheader("Recent Interviews")
            interviews_df = pd.DataFrame(
                recent_interviews, 
                columns=["Candidate", "Interviewer", "Date", "Result"]
            )
            st.dataframe(interviews_df)
        else:
            st.info("No interviews recorded yet.")

    except Exception as e:
        st.error(f"Error fetching candidate statistics: {str(e)}")

# For testing the admin view directly
if __name__ == "__main__":
    st.set_page_config(
        page_title="Admin Dashboard - BRV Applicant System",
        page_icon="👑",
        layout="wide"
    )

    # Initialize session state for testing
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = True
    if 'user_id' not in st.session_state:
        st.session_state.user_id = "test_admin_id"
    if 'user_role' not in st.session_state:
        st.session_state.user_role = "admin"

    admin_view()
