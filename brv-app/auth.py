import streamlit as st
from datetime import datetime, timedelta
import time
import secrets
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from mysql_db import authenticate_user, get_user_by_email, update_user_password, get_candidate_by_email

# Password validation
def validate_password_strength(password):
    """
    Validate password strength.
    
    Args:
        password (str): The password to validate
        
    Returns:
        tuple: (is_valid, message) where is_valid is a boolean and message is a string
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    
    if not (has_upper and has_lower and has_digit):
        return False, "Password must contain at least one uppercase letter, one lowercase letter, and one digit."
    
    return True, "Password is strong."

def needs_reset(force_reset, last_change_date):
    """
    Check if a password needs to be reset.
    
    Args:
        force_reset (bool): Whether a reset is forced
        last_change_date (str): The date the password was last changed
        
    Returns:
        bool: True if the password needs to be reset, False otherwise
    """
    if force_reset:
        return True
    
    if not last_change_date:
        return False
    
    try:
        # Parse the last change date
        last_change = datetime.fromisoformat(last_change_date)
        
        # Check if it's been more than 90 days
        return (datetime.now() - last_change) > timedelta(days=90)
    except:
        return False

def login(email, password):
    """
    Authenticate a user and set up session state.
    
    Args:
        email (str): The email to authenticate
        password (str): The password to verify
        
    Returns:
        tuple: (success, message) where success is a boolean and message is a string
    """
    # Use MySQL authentication
    user = authenticate_user(email, password)
    
    if not user:
        return False, "Invalid email or password"
    
    # Set up session state
    st.session_state.authenticated = True
    st.session_state.user_id = user.get("id", "")
    st.session_state.email = email
    st.session_state.user_role = user.get("role", "[no-role]")
    
    # Fetch candidate data if available (for candidates who might also be users)
    candidate_data = get_candidate_by_email(email)
    if candidate_data:
        # Store resume URL in session state
        resume_url = candidate_data.get("resume_url", "")
        st.session_state.resume_url = resume_url
        print(f"[DEBUG] Found resume link for {email}: {resume_url}")
    
    # For now, we're not implementing password expiration
    # In a real implementation, you would check if the password needs to be reset
    st.session_state.password_reset_required = False
    
    return True, "Login successful"

def logout():
    """
    Log out the current user by clearing session state.
    """
    for key in ['authenticated', 'user_id', 'email', 'user_role', 'password_reset_required']:
        if key in st.session_state:
            del st.session_state[key]

def change_password(user_id, new_password):
    """
    Change a user's password.
    
    Args:
        user_id (int): The ID of the user
        new_password (str): The new password
        
    Returns:
        tuple: (success, message) where success is a boolean and message is a string
    """
    # Validate password strength
    is_valid, message = validate_password_strength(new_password)
    if not is_valid:
        return False, message
    
    # Update the password in the database
    success = update_user_password(user_id, new_password)
    
    if not success:
        return False, "Failed to update password"
    
    # Update session state
    st.session_state.password_reset_required = False
    
    return True, "Password changed successfully"

def is_first_time_setup():
    """
    Check if this is the first time the system is being set up.
    
    Returns:
        bool: True if this is the first time setup, False otherwise
    """
    # In a real implementation, you would check if there are any users in the database
    # For now, we'll assume it's not the first time
    return False

def get_dashboard_url(role):
    """
    Get the URL for a user's dashboard based on their role.
    
    Args:
        role (str): The user's role
        
    Returns:
        str: The URL for the user's dashboard
    """
    # Convert role to lowercase for case-insensitive comparison
    role = role.lower()
    
    if role == "receptionist":
        return "/receptionist"
    elif role == "interviewer":
        return "/interviewer"
    elif role == "ceo" or role == "admin":
        return "/admin"
    else:
        return "/"

def password_reset_page():
    """
    Display the password reset page for logged-in users who need to change their password.
    
    Returns:
        bool: True if the password was reset successfully, False otherwise
    """
    st.title("Password Reset Required")
    st.warning("⚠️ You must change your password before continuing.")
    
    # Track success
    if "password_changed" not in st.session_state:
        st.session_state["password_changed"] = False
    
    if not st.session_state["password_changed"]:
        with st.form("password_reset_form"):
            new_password = st.text_input("New Password", type="password")
            confirm_password = st.text_input("Confirm New Password", type="password")
            submit = st.form_submit_button("Change Password")
            
            if submit:
                if not new_password:
                    st.error("Password cannot be empty.")
                    return False
                
                if new_password != confirm_password:
                    st.error("Passwords do not match.")
                    return False
                
                # Validate password strength
                is_valid, message = validate_password_strength(new_password)
                if not is_valid:
                    st.error(message)
                    return False
                
                # Change the password
                success, message = change_password(st.session_state.user_id, new_password)
                if success:
                    st.success("✅ Password changed successfully. Please log in again.")
                    st.session_state["password_changed"] = True
                    # Clear session to force logout
                    st.session_state.clear()
                    st.rerun()
                    return True
                else:
                    st.error("❌ " + message)
                    return False
    else:
        st.success("✅ Password changed successfully. Please log in again.")
        # Add back-to-login button here
        if st.button("🔙 Back to Login"):
            # Clear session and rerun
            st.session_state.clear()
            st.rerun()
            return True
        
        # Optional: Auto-redirect after 3 seconds
        time.sleep(3)
        st.session_state.clear()
        st.rerun()
        return True
    
    # Add Back to Login button (only show if password not changed)
    if not st.session_state.get("password_changed", False):
        st.markdown("---")
        if st.button("🔙 Back to Login"):
            st.session_state.clear()  # Clear all session state
            st.rerun()
    
    return False

def generate_otp():
    """
    Generate a 6-digit OTP.
    
    Returns:
        str: The generated OTP
    """
    return ''.join(secrets.choice(string.digits) for _ in range(6))

def save_otp(email, otp):
    """
    Save an OTP for a user.
    
    Args:
        email (str): The user's email
        otp (str): The OTP to save
        
    Returns:
        bool: True if the OTP was saved successfully, False otherwise
    """
    # In a real implementation, you would save the OTP in the database
    # For now, we'll store it in session state
    if 'otps' not in st.session_state:
        st.session_state.otps = {}
    
    st.session_state.otps[email] = {
        'otp': otp,
        'created_at': datetime.now().isoformat()
    }
    
    return True

def verify_otp(email, otp):
    """
    Verify an OTP for a user.
    
    Args:
        email (str): The user's email
        otp (str): The OTP to verify
        
    Returns:
        tuple: (is_valid, message) where is_valid is a boolean and message is a string
    """
    # In a real implementation, you would verify the OTP from the database
    # For now, we'll verify it from session state
    if 'otps' not in st.session_state or email not in st.session_state.otps:
        return False, "Invalid OTP or OTP expired."
    
    stored_otp = st.session_state.otps[email]['otp']
    created_at = datetime.fromisoformat(st.session_state.otps[email]['created_at'])
    
    # Check if OTP is expired (10 minutes)
    if (datetime.now() - created_at) > timedelta(minutes=10):
        return False, "OTP expired. Please request a new one."
    
    # Check if OTP matches
    if otp != stored_otp:
        return False, "Invalid OTP. Please try again."
    
    # Clear the OTP
    del st.session_state.otps[email]
    
    return True, "OTP verified successfully."

def send_otp_email(email, otp):
    """
    Send an OTP to a user's email.
    
    Args:
        email (str): The user's email
        otp (str): The OTP to send
        
    Returns:
        bool: True if the email was sent successfully, False otherwise
    """
    # In a real implementation, you would send an email with the OTP
    # For now, we'll just print it to the console
    print(f"[DEBUG] Sending OTP {otp} to {email}")
    
    # Simulate email sending
    time.sleep(1)
    
    return True

def forgot_password_page():
    """
    Display the forgot password page with OTP-based reset flow.
    
    Returns:
        bool: True if the password was reset successfully, False otherwise
    """
    st.title("Forgot Password")
    
    # Step 1: Enter email
    if "otp_sent" not in st.session_state:
        st.session_state.otp_sent = False
    
    if not st.session_state.otp_sent:
        with st.form("email_form"):
            email = st.text_input("Enter your email")
            submit_email = st.form_submit_button("Send OTP")
            
            if submit_email:
                if not email:
                    st.error("Please enter your email.")
                    return False
                
                if not email.endswith("@bluematrixit.com"):
                    st.error("Only official Bluematrix emails are allowed.")
                    return False
                
                # Check if email exists in database
                user = get_user_by_email(email)
                if not user:
                    # Don't reveal if email exists or not for security
                    st.success("If your email is registered, you will receive an OTP shortly.")
                    return False
                
                # Generate and save OTP with loading indicator
                with st.spinner("Sending OTP to your email..."):
                    try:
                        otp = generate_otp()
                        if save_otp(email, otp):
                            # Send OTP email
                            if send_otp_email(email, otp):
                                st.session_state.otp_email = email
                                st.session_state.otp_sent = True
                                st.success("OTP sent to your email. Please check your inbox.")
                                try:
                                    st.rerun()
                                except:
                                    st.session_state["reset_triggered"] = True
                                    st.stop()
                            else:
                                st.error("Failed to send OTP email. Please check your email address and try again.")
                        else:
                            st.error("Failed to generate and save OTP. Please try again later.")
                    except Exception as e:
                        st.error(f"An error occurred: {str(e)}. Please try again later.")
        
        # Add Back to Login button
        st.markdown("---")
        if st.button("← Back to Login"):
            st.session_state.pop("forgot_password", None)
            st.session_state.pop("show_forgot_password", None)
            st.session_state.pop("verify_otp_user", None)
            st.rerun()
    
    # Step 2: Verify OTP and set new password
    else:
        with st.form("otp_form"):
            otp = st.text_input("Enter OTP")
            new_password = st.text_input("New Password", type="password")
            confirm_password = st.text_input("Confirm New Password", type="password")
            submit_otp = st.form_submit_button("Reset Password")
            
            if submit_otp:
                if not otp:
                    st.error("Please enter the OTP.")
                    return False
                
                if not new_password:
                    st.error("Password cannot be empty.")
                    return False
                
                if new_password != confirm_password:
                    st.error("Passwords do not match.")
                    return False
                
                # Validate password strength
                is_valid, message = validate_password_strength(new_password)
                if not is_valid:
                    st.error(message)
                    return False
                
                # Verify OTP and change password with loading indicator
                with st.spinner("Verifying OTP and resetting password..."):
                    try:
                        # Verify OTP
                        is_valid, message = verify_otp(st.session_state.otp_email, otp)
                        if not is_valid:
                            st.error(message)
                            return False
                        
                        # Get user ID
                        user = get_user_by_email(st.session_state.otp_email)
                        if not user:
                            st.error("User not found.")
                            return False
                        
                        # Change the password
                        success, message = change_password(user['id'], new_password)
                        if success:
                            # Reset session state
                            st.session_state.otp_sent = False
                            st.session_state.otp_email = None
                            st.session_state.show_forgot_password = False
                            
                            st.success("✅ " + message)
                            st.info("You can now log in with your new password.")
                            return True
                        else:
                            st.error("❌ " + message)
                            return False
                    except Exception as e:
                        st.error(f"An error occurred: {str(e)}. Please try again later.")
                        return False
        
        # Add option to go back or resend OTP
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Back"):
                st.session_state.otp_sent = False
                st.session_state.otp_email = None
                try:
                    st.rerun()
                except:
                    st.session_state["reset_triggered"] = True
                    st.stop()
        
        with col2:
            if st.button("Resend OTP"):
                # Generate and save new OTP
                otp = generate_otp()
                if save_otp(st.session_state.otp_email, otp):
                    # Send OTP email
                    if send_otp_email(st.session_state.otp_email, otp):
                        st.success("New OTP sent to your email. Please check your inbox.")
                    else:
                        st.error("Failed to send OTP. Please try again.")
                else:
                    st.error("Failed to generate OTP. Please try again.")
        
        # Add Back to Login button
        st.markdown("---")
        if st.button("← Back to Login"):
            st.session_state.pop("forgot_password", None)
            st.session_state.pop("show_forgot_password", None)
            st.session_state.pop("verify_otp_user", None)
            st.session_state.pop("otp_sent", None)
            st.session_state.pop("otp_email", None)
            st.rerun()
    
    return False

def login_page():
    """
    Display the login page.
    
    Returns:
        bool: True if login was successful, False otherwise
    """
    st.title("🔐 BRV Applicant Management System")
    
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            if not email or not password:
                st.error("Please enter both email and password.")
                return False
            
            success, message = login(email, password)
            if success:
                if "Password reset required" in message:
                    st.warning("⚠️ " + message)
                else:
                    st.success("✅ " + message)
                return True
            else:
                st.error("❌ " + message)
                return False
    
    # Add forgot password link outside the form
    if st.button("Forgot Password?"):
        st.session_state.show_forgot_password = True
        try:
            st.rerun()
        except:
            st.session_state["reset_triggered"] = True
            st.stop()
    
    return False

def initialize_session():
    """
    Initialize session state variables if they don't exist.
    """
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'email' not in st.session_state:
        st.session_state.email = None
    if 'user_role' not in st.session_state:
        st.session_state.user_role = None
    if 'password_reset_required' not in st.session_state:
        st.session_state.password_reset_required = False
    if 'show_forgot_password' not in st.session_state:
        st.session_state.show_forgot_password = False
    if 'otp_email' not in st.session_state:
        st.session_state.otp_email = None
    if 'otp_sent' not in st.session_state:
        st.session_state.otp_sent = False