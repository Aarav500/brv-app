import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import random
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import sqlite3
import hashlib
import re

# Define valid roles for the application
VALID_ROLES = ["receptionist", "interviewer", "ceo", "admin", "hr", "candidate"]

def normalize_column_name(col):
    """
    Normalize column names by removing spaces, underscores, parentheses, and converting to lowercase.
    This helps match column names that might have slight variations.

    Args:
        col (str): The column name to normalize

    Returns:
        str: The normalized column name
    """
    if not col:
        return ""
    # Remove parentheses and their contents, and other special characters
    import re
    normalized = re.sub(r'\([^)]*\)', '', col)
    # Remove spaces, underscores, hyphens and convert to lowercase
    normalized = normalized.strip().lower().replace(" ", "").replace("_", "").replace("-", "")
    return normalized

def find_matching_column(columns, target):
    target_norm = normalize_column_name(target)
    for col in columns:
        if normalize_column_name(col) == target_norm:
            return col
    return None

def fetch_google_form_responses(force_refresh=False, form_url=None):
    """
    Fetches responses from a Google Form via Google Sheets API.

    Args:
        force_refresh (bool): If True, bypass any caching mechanisms
        form_url (str): Optional Google Form URL. If provided, will try to derive the sheet URL

    Returns:
        pandas.DataFrame: DataFrame containing form responses
    """
    import streamlit as st
    
    # Use session state for caching
    if not force_refresh and "google_sheet_data" in st.session_state:
        print("Using cached Google Sheet data")
        return st.session_state.google_sheet_data
        
    try:
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']

        # Check if credentials file exists
        if not os.path.exists('google_key.json'):
            print("Google API key file not found. Using sample data.")
            st.error("Google API key file not found. Using sample data.")
            return get_sample_data()

        creds = ServiceAccountCredentials.from_json_keyfile_name('google_key.json', scope)
        client = gspread.authorize(creds)

        # Use your shared sheet URL here:
        sheet_url = "https://docs.google.com/spreadsheets/d/1V0Sf65ZVrebpopBfg2vwk-_PjRxgqlbytIX-L2GImAE/edit?resourcekey=&gid=1400567486"
        try:
            sheet = client.open_by_url(sheet_url)
            worksheet = sheet.worksheet("Form Responses 2")  # Using explicit worksheet name
            
            # Use expected_headers to handle duplicate column names
            # Define expected headers based on the exact column names specified
            expected_headers = [
                "Timestamp",
                "Email Address",
                "Full Name( First-middle-last)",
                "Current Address",
                "Permanent Address",
                "Phone number",
                "Additional Phone Number (NA if none)",
                "Date Of birth",
                "Caste",
                "Sub Caste",
                "Marital Status",
                "Highest Qualification",
                "Work Experience ",
                "Referral ",
                "Upload your Resume"
            ]
            
            try:
                data = worksheet.get_all_records(expected_headers=expected_headers)
                
                # Strict header validation - check if all required columns are present
                actual_headers = worksheet.get_all_values()[0] if worksheet.get_all_values() else []
                missing_columns = [header for header in expected_headers if header not in actual_headers]
                
                if missing_columns:
                    error_message = f"Missing required columns in Google Sheet: {', '.join(missing_columns)}"
                    print(error_message)
                    st.error(error_message)
                    raise ValueError(error_message)
                    
            except Exception as headers_error:
                print(f"Error with expected headers: {headers_error}")
                
                # Check if it's our custom validation error
                if isinstance(headers_error, ValueError) and "Missing required columns" in str(headers_error):
                    raise headers_error
                
                # Get actual headers for better error reporting
                try:
                    actual_headers = worksheet.get_all_values()[0]
                    print(f"Actual headers in sheet: {actual_headers}")
                    
                    # Check for missing columns
                    missing_columns = [header for header in expected_headers if header not in actual_headers]
                    if missing_columns:
                        error_message = f"Missing required columns in Google Sheet: {', '.join(missing_columns)}"
                        print(error_message)
                        st.error(error_message)
                        raise ValueError(error_message)
                except Exception as e:
                    print(f"Error checking headers: {e}")
                
                # Fallback to get all values and manually create records with unique headers
                all_values = worksheet.get_all_values()
                if len(all_values) > 1:  # Ensure we have header row and data
                    headers = all_values[0]
                    
                    # Strict validation - check if all required columns are present
                    missing_columns = [header for header in expected_headers if header not in headers]
                    if missing_columns:
                        error_message = f"Missing required columns in Google Sheet: {', '.join(missing_columns)}"
                        print(error_message)
                        st.error(error_message)
                        raise ValueError(error_message)
                    
                    # Create unique headers by adding index to duplicates
                    unique_headers = []
                    seen_headers = {}
                    for h in headers:
                        if h in seen_headers:
                            seen_headers[h] += 1
                            unique_headers.append(f"{h} {seen_headers[h]}")
                        else:
                            seen_headers[h] = 0
                            unique_headers.append(h)
                    
                    # Create records with unique headers
                    data = []
                    for values in all_values[1:]:  # Skip header row
                        record = {}
                        for i, value in enumerate(values):
                            if i < len(unique_headers):
                                record[unique_headers[i]] = value
                        data.append(record)
                else:
                    raise Exception("No data found in worksheet")
                
        except Exception as sheet_error:
            print(f"Error accessing Google Sheet: {sheet_error}")
            st.error(f"Error accessing Google Sheet: {sheet_error}")
            return get_sample_data()

        # Convert to DataFrame
        df = pd.DataFrame(data)

        # Debug information
        print(f"Fetched {len(df)} rows from Google Sheet")
        print(f"Columns: {df.columns.tolist()}")

        # If DataFrame is empty, return sample data
        if df.empty:
            print("No data found in Google Sheet, returning sample data")
            st.warning("No data found in Google Sheet, using sample data instead.")
            return get_sample_data()

        # Fix PyArrowError by converting phone number columns to numeric with coercion
        for col in df.columns:
            if 'phone' in col.lower() or 'mobile' in col.lower() or 'number' in col.lower():
                print(f"Converting column {col} to numeric with coercion")
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
        # Cache the data in session state
        st.session_state.google_sheet_data = df
        
        # Show success message if force_refresh was requested
        if force_refresh:
            st.success("✅ Google Sheet data refreshed successfully!")

        return df

    except Exception as e:
        print("Error fetching Google Form responses:")
        import traceback
        traceback.print_exc()  # Add this to see the real traceback
        # Show error to user
        st.error(f"Error fetching Google Form responses: {str(e)}")
        # Return sample data if there's an error
        return get_sample_data()

def get_sample_data():
    """
    Returns sample data for testing when Google Sheets connection is not available.

    Returns:
        pandas.DataFrame: DataFrame containing sample form responses
    """
    # Create sample data
    sample_data = [
        {
            "Timestamp": "2023-07-01 10:30:45",
            "Full Name": "John Doe",
            "Email": "john.doe@example.com",
            "Phone": "1234567890",
            "Address": "123 Main St, Anytown, USA",
            "Education": "Bachelor's in Computer Science",
            "Experience": "5 years as Software Developer",
            "Skills": "Python, JavaScript, SQL",
            "Position Applied For": "Senior Developer"
        },
        {
            "Timestamp": "2023-07-02 11:45:22",
            "Full Name": "Jane Smith",
            "Email": "jane.smith@example.com",
            "Phone": "0987654321",
            "Address": "456 Oak Ave, Somewhere, USA",
            "Education": "Master's in Information Technology",
            "Experience": "3 years as System Analyst",
            "Skills": "Java, C++, Project Management",
            "Position Applied For": "Project Manager"
        },
        {
            "Timestamp": "2023-07-03 09:15:33",
            "Full Name": "Bob Johnson",
            "Email": "bob.johnson@example.com",
            "Phone": "5556667777",
            "Address": "789 Pine Rd, Nowhere, USA",
            "Education": "Associate's in Web Development",
            "Experience": "2 years as Frontend Developer",
            "Skills": "HTML, CSS, React",
            "Position Applied For": "UI/UX Designer"
        }
    ]

    df = pd.DataFrame(sample_data)

    # Fix PyArrowError by converting phone number columns to numeric with coercion
    for col in df.columns:
        if 'phone' in col.lower() or 'mobile' in col.lower() or 'number' in col.lower():
            print(f"Converting sample data column {col} to numeric with coercion")
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df

# Email configuration
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USER = "your_app_email@gmail.com"  # Replace with your actual email
EMAIL_PASS = "your-app-specific-password"  # Replace with your app-specific password

# Google Form configuration
GOOGLE_FORM_URL = "https://forms.gle/WcERrdrfKRGKESWn9"  # Replace with your actual form URL
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1-w95t8EAoplGajPNsYxy2en0AyH6f5Rk0gm6L5f7kY4/edit"  # Replace with your actual sheet URL

def generate_otp(length=6):
    """
    Generate a random OTP of specified length.

    Args:
        length (int): Length of the OTP

    Returns:
        str: The generated OTP
    """
    # Generate OTP using only digits
    return ''.join(random.choices(string.digits, k=length))

def hash_otp(otp):
    """
    Hash an OTP for secure storage.

    Args:
        otp (str): The OTP to hash

    Returns:
        str: The hashed OTP
    """
    return hashlib.sha256(otp.encode()).hexdigest()

def save_otp(email, otp, expiry_minutes=10):
    """
    Save an OTP to Firestore.

    Args:
        email (str): The user's email
        otp (str): The OTP to save
        expiry_minutes (int): Minutes until the OTP expires

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        from firebase_db import db

        # Hash the OTP for secure storage
        hashed_otp = hash_otp(otp)

        # Calculate expiry time
        expiry_time = (datetime.now() + timedelta(minutes=expiry_minutes)).strftime("%Y-%m-%d %H:%M:%S")

        # Save to Firestore
        db.collection("otps").document(email).set({
            "otp": hashed_otp,
            "expiry": expiry_time,
            "attempts": 0
        })

        return True
    except Exception as e:
        print(f"Error saving OTP: {e}")
        return False

def verify_otp(email, otp):
    """
    Verify an OTP against the stored value in Firestore.

    Args:
        email (str): The user's email
        otp (str): The OTP to verify

    Returns:
        tuple: (is_valid, message)
    """
    try:
        from firebase_db import db

        # Get the stored OTP document
        doc = db.collection("otps").document(email).get()

        if not doc.exists:
            return False, "No OTP found for this email"

        otp_data = doc.to_dict()
        stored_otp = otp_data.get("otp")
        expiry_time = otp_data.get("expiry")
        attempts = otp_data.get("attempts", 0)

        # Check if OTP is expired
        if datetime.now() > datetime.strptime(expiry_time, "%Y-%m-%d %H:%M:%S"):
            return False, "OTP has expired"

        # Check if too many attempts
        if attempts >= 3:
            return False, "Too many failed attempts. Request a new OTP."

        # Hash the provided OTP and compare
        hashed_otp = hash_otp(otp)
        if hashed_otp != stored_otp:
            # Increment attempts counter
            db.collection("otps").document(email).update({
                "attempts": attempts + 1
            })
            return False, "Invalid OTP"

        # Clear OTP after successful verification
        db.collection("otps").document(email).delete()
        return True, "OTP verified successfully"
    except Exception as e:
        print(f"Error verifying OTP: {e}")
        return False, f"Error: {str(e)}"

def send_email(to_email, subject, body):
    """
    Send an email using SMTP.

    Args:
        to_email (str): Recipient email address
        subject (str): Email subject
        body (str): Email body (HTML)

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = to_email
        msg['Subject'] = subject

        # Attach HTML body
        msg.attach(MIMEText(body, 'html'))

        # Connect to SMTP server
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)

        # Send email
        server.send_message(msg)
        server.quit()

        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def send_otp_email(email, otp):
    """
    Send an OTP to a user's email.

    Args:
        email (str): The user's email
        otp (str): The OTP to send

    Returns:
        bool: True if successful, False otherwise
    """
    subject = "Password Reset OTP - BRV Applicant Management System"
    body = f"""
    <html>
    <body>
        <h2>Password Reset Request</h2>
        <p>You have requested to reset your password for the BRV Applicant Management System.</p>
        <p>Your OTP is: <strong>{otp}</strong></p>
        <p>This OTP will expire in 10 minutes.</p>
        <p>If you did not request this password reset, please ignore this email.</p>
    </body>
    </html>
    """

    return send_email(email, subject, body)

def fetch_edit_urls(force_refresh=False):
    """
    Fetches edit URLs from Google Sheet for all form responses.
    
    This function:
    1. Fetches Google Sheet data using fetch_google_form_responses
    2. Looks for the "Edit URL" column (added by the Google Apps Script)
    3. Creates a dictionary mapping email addresses to edit URLs
    
    Args:
        force_refresh (bool): If True, bypass any caching mechanisms
        
    Returns:
        dict: Dictionary mapping email addresses to edit URLs
    """
    import streamlit as st
    
    # Use session state for caching
    if not force_refresh and "edit_urls" in st.session_state:
        print("Using cached edit URLs")
        return st.session_state.edit_urls
    
    # Fetch the Google Sheet data
    df = fetch_google_form_responses(force_refresh=force_refresh)
    
    if df.empty:
        return {}
    
    # Find the Edit URL column
    edit_url_col = None
    for col in df.columns:
        if col == "Edit URL":
            edit_url_col = col
            break
    
    if not edit_url_col:
        print("No Edit URL column found in Google Sheet")
        st.warning("No Edit URL column found in Google Sheet. Please ensure the Google Apps Script is properly set up.")
        return {}
    
    # Find the email column
    email_col = None
    for col in df.columns:
        if 'email' in col.lower():
            email_col = col
            break
    
    if not email_col:
        print("No email column found in Google Sheet")
        st.warning("No email column found in Google Sheet")
        return {}
    
    # Create a dictionary mapping email addresses to edit URLs
    edit_urls = {}
    for _, row in df.iterrows():
        email = row[email_col]
        edit_url = row[edit_url_col]
        
        if email and edit_url:
            edit_urls[email] = edit_url
    
    # Cache the edit URLs in session state
    st.session_state.edit_urls = edit_urls
    
    # Show success message if force_refresh was requested
    if force_refresh and edit_urls:
        st.success(f"✅ Found {len(edit_urls)} edit URLs")
    
    return edit_urls

def send_edit_link_email(email, edit_url, candidate_name=None):
    """
    Send an email with an edit link to a candidate.
    
    Args:
        email (str): The candidate's email address
        edit_url (str): The edit URL for the candidate's form response
        candidate_name (str, optional): The candidate's name
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Use candidate name if provided, otherwise use email
    recipient_name = candidate_name if candidate_name else email
    
    subject = "Edit Your BRV Application Form"
    body = f"""
    <html>
    <body>
        <h2>Edit Your BRV Application</h2>
        <p>Hello {recipient_name},</p>
        <p>You have been granted permission to edit your BRV application form.</p>
        <p>Please click the link below to edit your information:</p>
        <p><a href="{edit_url}" style="display: inline-block; background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Edit Your Application</a></p>
        <p>If the button above doesn't work, you can copy and paste this URL into your browser:</p>
        <p>{edit_url}</p>
        <p>This link is unique to you and should not be shared with others.</p>
        <p>If you have any questions, please contact the BRV recruitment team.</p>
        <p>Thank you,<br>BRV Recruitment Team</p>
    </body>
    </html>
    """
    
    return send_email(email, subject, body)

def update_resume_links_from_google_sheet():
    """
    Fetches resume links from Google Sheet and updates the Firestore database.

    This function:
    1. Fetches Google Sheet data using fetch_google_form_responses
    2. Extracts email and resume URL from each row
    3. Updates the Firestore database with the resume links

    Returns:
        tuple: (success, message)
    """
    try:
        from firebase_db import db

        # Fetch Google Sheet data
        df = fetch_google_form_responses(force_refresh=True)

        if df.empty:
            return False, "No data found in Google Sheet"

        # Find resume column
        resume_column = None
        for col in df.columns:
            if 'resume' in col.lower() or 'cv' in col.lower() or 'file' in col.lower():
                resume_column = col
                break

        if not resume_column:
            return False, "No resume column found in Google Sheet"

        # Find email column
        email_column = None
        for col in df.columns:
            if 'email' in col.lower():
                email_column = col
                break

        if not email_column:
            return False, "No email column found in Google Sheet"

        # Update resume links in Firestore
        updated_count = 0
        for _, row in df.iterrows():
            email = row[email_column]
            resume_link = row[resume_column]

            if email and resume_link:
                # Update resume link in Firestore
                db.collection("resumes").document(email).set({
                    "resume_url": resume_link,
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }, merge=True)

                # Also update the candidate document if it exists
                candidates_ref = db.collection("candidates").where("email", "==", email).limit(1).stream()
                for candidate_doc in candidates_ref:
                    candidate_doc.reference.update({
                        "resume_link": resume_link,
                        "resume_updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                    updated_count += 1

        return True, f"Updated {updated_count} candidate resume links"

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"Error updating resume links: {str(e)}"

def sanitize_for_drive_query(s):
    """
    Sanitizes a string for use in a Google Drive query.

    Args:
        s (str): The string to sanitize

    Returns:
        str: The sanitized string
    """
    s = str(s or "").strip()
    s = re.sub(r"[\"']", "", s)  # remove quotes
    s = s.replace("\\", "")
    return s

def fetch_cv_from_google_drive(row=None, candidate_name=None, candidate_email=None):
    """
    Fetches CV files from Google Drive based on candidate information.

    This function searches Google Drive for files that might be CVs/resumes
    for a specific candidate. It can work with either:
    1. A row from a DataFrame (containing candidate details)
    2. Direct candidate_name and candidate_email parameters
    
    It also checks Firestore for any CV links associated with the candidate's email.

    Args:
        row (dict or pandas.Series, optional): A row containing candidate information
        candidate_name (str, optional): The candidate's name to search for
        candidate_email (str, optional): The candidate's email to search for

    Returns:
        list: A list of dictionaries containing file information (id, name, url)
    """
    # If row is provided, extract candidate information from it
    if row is not None:
        # Extract full name from row with fallbacks for different column names
        full_name = row.get('Full Name( First-middle-last)', 
                   row.get('Full Name', 
                   row.get('Name', ''))).strip()
                   
        # Extract email from row with fallbacks for different column names
        email = row.get('Email Address', 
               row.get('Email', 
               row.get('email', ''))).strip()
               
        # Update candidate_email for Firestore check
        if email and not candidate_email:
            candidate_email = email
               
        # Extract candidate_no and timestamp if available
        candidate_no = row.get('candidate_no', '').strip()
        timestamp = row.get('timestamp', '').strip()
        
        # Log if using fallback logic
        if not candidate_no or not timestamp:
            print(f"[FALLBACK] No candidate_no/timestamp. Searching using full name: {full_name}, email: {email}")
    else:
        # Use provided candidate_name and candidate_email
        full_name = candidate_name or ''
        email = candidate_email or ''
        candidate_no = ''
        timestamp = ''
    try:
        cv_files = []

        # First, check if we have a CV link stored in Firestore for this email
        if candidate_email:
            from firebase_admin import firestore
            db = firestore.client()

            # Check in users collection
            user_ref = db.collection("users").document(candidate_email)
            user_doc = user_ref.get()

            if user_doc.exists:
                user_data = user_doc.to_dict()
                cv_link = user_data.get("cv_link")

                if cv_link:
                    # Extract file ID if it's a Google Drive link
                    from resume_handler import is_google_drive_link, extract_file_id
                    if is_google_drive_link(cv_link):
                        file_id = extract_file_id(cv_link)
                        if file_id:
                            # Get candidate ID from user data or use email as fallback
                            candidate_id = user_data.get("candidate_id") or user_data.get("application_id")
                            if not candidate_id and "id" in user_data:
                                candidate_id = user_data["id"]
                            if not candidate_id:
                                # Use timestamp as last resort
                                from datetime import datetime
                                candidate_id = datetime.now().strftime("%Y%m%d%H%M%S")
                            
                            cv_files.append({
                                'id': file_id,
                                'name': f"CV_{candidate_id}.pdf",
                                'mime_type': 'application/pdf',
                                'url': cv_link,
                                'download_url': f"https://drive.google.com/uc?export=download&id={file_id}",
                                'source': 'user_profile',
                                'candidate_id': candidate_id
                            })

            # Also check in candidates collection
            candidates_ref = db.collection("candidates").where("email", "==", candidate_email).limit(1)
            candidate_docs = candidates_ref.stream()

            for doc in candidate_docs:
                candidate_data = doc.to_dict()
                resume_link = candidate_data.get("resume_link")

                if resume_link:
                    # Extract file ID if it's a Google Drive link
                    from resume_handler import is_google_drive_link, extract_file_id
                    if is_google_drive_link(resume_link):
                        file_id = extract_file_id(resume_link)
                        if file_id:
                            # Check if this file is already in our list
                            if not any(cf['id'] == file_id for cf in cv_files):
                                # Get candidate ID from candidate data or use document ID as fallback
                                candidate_id = candidate_data.get("candidate_id") or candidate_data.get("application_id")
                                if not candidate_id and "id" in candidate_data:
                                    candidate_id = candidate_data["id"]
                                if not candidate_id:
                                    # Use document ID as fallback
                                    candidate_id = doc.id
                                
                                cv_files.append({
                                    'id': file_id,
                                    'name': f"CV_{candidate_id}.pdf",
                                    'mime_type': 'application/pdf',
                                    'url': resume_link,
                                    'download_url': f"https://drive.google.com/uc?export=download&id={file_id}",
                                    'source': 'candidate_profile',
                                    'candidate_id': candidate_id
                                })

            # Also check in resumes collection
            resume_ref = db.collection("resumes").document(candidate_email)
            resume_doc = resume_ref.get()

            if resume_doc.exists:
                resume_data = resume_doc.to_dict()
                resume_url = resume_data.get("resume_url")

                if resume_url:
                    # Extract file ID if it's a Google Drive link
                    from resume_handler import is_google_drive_link, extract_file_id
                    if is_google_drive_link(resume_url):
                        file_id = extract_file_id(resume_url)
                        if file_id:
                            # Check if this file is already in our list
                            if not any(cf['id'] == file_id for cf in cv_files):
                                # Get candidate ID from resume data or use email as fallback
                                candidate_id = resume_data.get("candidate_id")
                                if not candidate_id:
                                    # Use timestamp as last resort
                                    from datetime import datetime
                                    candidate_id = datetime.now().strftime("%Y%m%d%H%M%S")
                                
                                cv_files.append({
                                    'id': file_id,
                                    'name': f"CV_{candidate_id}.pdf",
                                    'mime_type': 'application/pdf',
                                    'url': resume_url,
                                    'download_url': f"https://drive.google.com/uc?export=download&id={file_id}",
                                    'source': 'resume_collection',
                                    'candidate_id': candidate_id
                                })

        # If we already found CV files in Firestore, return them
        if cv_files:
            return cv_files

        # Otherwise, search Google Drive
        # Set up credentials and service
        scope = ['https://www.googleapis.com/auth/drive.readonly']

        # Check if credentials file exists
        if not os.path.exists('google_key.json'):
            print("Google API key file not found.")
            return []

        creds = ServiceAccountCredentials.from_json_keyfile_name('google_key.json', scope)

        # Build the Drive API client
        from googleapiclient.discovery import build
        service = build('drive', 'v3', credentials=creds)

        # Prepare search query
        # Sanitize inputs
        full_name = sanitize_for_drive_query(full_name)
        email = sanitize_for_drive_query(email)
        candidate_no = sanitize_for_drive_query(candidate_no)
        timestamp = sanitize_for_drive_query(timestamp)

        # Build query parts based on available information
        query_parts = []

        # Prefer new logic if candidate_no and timestamp are present
        if candidate_no and timestamp:
            query_parts.append(f"name contains '{candidate_no}_{timestamp}'")
        else:
            # fallback logic for older entries
            if full_name:
                query_parts.append(f"name contains '{full_name}' or fullText contains '{full_name}'")

            if email:
                query_parts.append(f"name contains '{email}' or fullText contains '{email}'")

        # If no search terms provided, return empty list
        if not query_parts:
            return []

        # MIME filter
        mime_filter = "(mimeType contains 'pdf' or mimeType contains 'word' or mimeType contains 'image')"
        
        # Join query parts with OR
        query = " or ".join(query_parts)
        final_query = f"({query}) and {mime_filter}"
        # Strip newlines and whitespaces for URL safety
        final_query = " ".join(final_query.strip().split())

        # Execute the search
        results = service.files().list(
            q=final_query,
            spaces='drive',
            fields="files(id, name, mimeType, webViewLink)",
            pageSize=10
        ).execute()

        files = results.get('files', [])

        # Format the results
        for file in files:
            file_id = file['id']
            # Check if this file is already in our list
            if not any(cf['id'] == file_id for cf in cv_files):
                cv_files.append({
                    'id': file_id,
                    'name': file['name'],
                    'mime_type': file['mimeType'],
                    'url': file['webViewLink'],
                    'download_url': f"https://drive.google.com/uc?export=download&id={file_id}",
                    'source': 'drive_search'
                })

        return cv_files

    except Exception as e:
        print(f"Error fetching CV from Google Drive: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_cv_from_drive_by_candidate_id(identifier):
    """
    Get the CV file from Google Drive based on an identifier (email, application_id).
    
    Args:
        identifier (str): The identifier (email, application_id) to search for
        
    Returns:
        dict: CV file information if found, None otherwise
    """
    if not identifier:
        return None
    
    try:
        # Set up credentials
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        
        if not os.path.exists('google_key.json'):
            print("Google API key file not found.")
            return None
        
        creds = ServiceAccountCredentials.from_json_keyfile_name('google_key.json', scope)
        
        # Connect to the Google Sheet containing the mapping
        sheet_id = os.getenv('MAPPING_SHEET_ID')
        if not sheet_id:
            print("MAPPING_SHEET_ID environment variable is not set.")
            return None
        
        sheet_name = os.getenv('MAPPING_SHEET_NAME', 'Candidate ID Mapping')
        
        # Connect to the sheet
        gc = gspread.authorize(creds)
        try:
            spreadsheet = gc.open_by_key(sheet_id)
            worksheet = spreadsheet.worksheet(sheet_name)
        except Exception as e:
            print(f"Error opening Google Sheet: {e}")
            return None
        
        # Get all records
        records = worksheet.get_all_records()
        
        # Find the matching record
        matching_record = None
        for record in records:
            if record.get('Candidate ID') == identifier or record.get('Application ID') == identifier or record.get('Email') == identifier:
                matching_record = record
                break
        
        if not matching_record:
            print(f"No mapping found for identifier: {identifier}")
            return None
        
        # Get the Google Drive file ID
        file_id = matching_record.get('Google Drive File ID')
        if not file_id:
            print(f"No Google Drive file ID found for identifier: {identifier}")
            return None
        
        # Build the Drive API client
        from googleapiclient.discovery import build
        drive_service = build('drive', 'v3', credentials=creds)
        
        # Get the file metadata
        file = drive_service.files().get(
            fileId=file_id,
            fields="id, name, mimeType, webViewLink"
        ).execute()
        
        # Format the result
        cv_file = {
            'id': file['id'],
            'name': file['name'],
            'mime_type': file['mimeType'],
            'url': file['webViewLink'],
            'download_url': f"https://drive.google.com/uc?export=download&id={file['id']}",
            'source': 'candidate_id_mapping'
        }
        
        return cv_file
    
    except Exception as e:
        print(f"Error getting CV from Drive by Candidate ID: {e}")
        import traceback
        traceback.print_exc()
        return None

def match_cvs_with_form_submissions(form_df, cv_files, max_time_diff_hours=24):
    """
    Match CV files with form submissions based on timestamps and name/email similarity.
    
    Args:
        form_df (pandas.DataFrame): DataFrame containing form submissions
        cv_files (list): List of CV file objects from Google Drive
        max_time_diff_hours (int): Maximum time difference in hours to consider for matching
        
    Returns:
        list: List of dictionaries containing matches with confidence scores
    """
    import datetime
    from dateutil import parser
    import re
    from difflib import SequenceMatcher
    
    # Function to calculate string similarity (0-1 score)
    def string_similarity(a, b):
        if not a or not b:
            return 0
        return SequenceMatcher(None, str(a).lower(), str(b).lower()).ratio()
    
    # Function to parse Google Drive timestamp
    def parse_drive_time(time_str):
        try:
            return parser.parse(time_str)
        except:
            return None
    
    # Function to parse form submission timestamp
    def parse_form_time(time_str):
        try:
            return parser.parse(time_str)
        except:
            return None
    
    # Function to calculate time difference score (1.0 for perfect match, decreasing as difference increases)
    def time_diff_score(time1, time2, max_hours=24):
        if not time1 or not time2:
            return 0
        
        diff_seconds = abs((time1 - time2).total_seconds())
        diff_hours = diff_seconds / 3600
        
        if diff_hours > max_hours:
            return 0
        
        # Score decreases linearly as time difference increases
        return 1.0 - (diff_hours / max_hours)
    
    # Extract name and email columns from form_df
    name_col = None
    email_col = None
    timestamp_col = None
    
    for col in form_df.columns:
        if 'name' in col.lower():
            name_col = col
        elif 'email' in col.lower():
            email_col = col
        elif 'timestamp' in col.lower():
            timestamp_col = col
    
    if not name_col or not email_col or not timestamp_col:
        print("Warning: Missing required columns in form data")
        return []
    
    # Prepare results list
    matches = []
    
    # Process each form submission
    for _, form_row in form_df.iterrows():
        form_name = str(form_row[name_col]).strip() if name_col else ""
        form_email = str(form_row[email_col]).strip() if email_col else ""
        form_time_str = str(form_row[timestamp_col]).strip() if timestamp_col else ""
        form_time = parse_form_time(form_time_str)
        
        # Skip if we can't parse the form submission time
        if not form_time:
            continue
        
        # Find potential matches for this form submission
        potential_matches = []
        
        for cv_file in cv_files:
            # Parse file creation and modification times
            created_time = parse_drive_time(cv_file.get('createdTime', ''))
            modified_time = parse_drive_time(cv_file.get('modifiedTime', ''))
            
            # Use the more recent of creation or modification time
            file_time = modified_time if modified_time else created_time
            
            # Skip if we can't determine file time
            if not file_time:
                continue
            
            # Calculate time difference score
            time_score = time_diff_score(form_time, file_time, max_time_diff_hours)
            
            # Skip if time difference is too large
            if time_score == 0:
                continue
            
            # Calculate name similarity
            file_name = cv_file.get('name', '')
            name_score = string_similarity(form_name, file_name)
            
            # Check if email appears in filename
            email_in_filename = 1.0 if form_email and form_email.lower() in file_name.lower() else 0.0
            
            # Calculate overall confidence score (weighted average)
            # Time proximity is most important, followed by email match, then name similarity
            confidence = (time_score * 0.6) + (email_in_filename * 0.3) + (name_score * 0.1)
            
            # Add to potential matches if confidence is above threshold
            if confidence > 0.3:  # Adjust threshold as needed
                potential_matches.append({
                    'cv_file': cv_file,
                    'confidence': confidence,
                    'time_score': time_score,
                    'name_score': name_score,
                    'email_match': email_in_filename > 0,
                    'form_time': form_time,
                    'file_time': file_time,
                    'time_difference_hours': abs((form_time - file_time).total_seconds()) / 3600
                })
        
        # Sort potential matches by confidence (highest first)
        potential_matches.sort(key=lambda x: x['confidence'], reverse=True)
        
        # Add to results
        if potential_matches:
            matches.append({
                'form_data': form_row,
                'potential_matches': potential_matches
            })
    
    return matches

def get_cv_by_candidate_id(identifier):
    """
    Get the CV file path for a candidate based on their identifier (email, application_id).
    First tries to find the CV in Google Drive using the mapping sheet,
    then falls back to local file system search.
    
    Args:
        identifier (str): The identifier (email, application_id) to search for
        
    Returns:
        str: Path to the CV file if found, None otherwise
    """
    if not identifier:
        return None
    
    # First try to get the CV from Google Drive
    cv_file = get_cv_from_drive_by_candidate_id(identifier)
    if cv_file:
        return cv_file['url']
    
    # Fallback to local file system search
    
    # Standardized path format: cvs/CV_<identifier>.pdf
    cv_path = f"cvs/CV_{identifier}.pdf"
    
    # Check if the file exists
    if os.path.exists(cv_path):
        return cv_path
    
    # Backward compatibility: check the old location and format
    if os.path.exists("data/resumes"):
        # Get all files in the resumes directory
        resume_files = [f for f in os.listdir("data/resumes") if os.path.isfile(os.path.join("data/resumes", f))]
        
        # Look for files that start with the identifier
        matching_files = [f for f in resume_files if f.startswith(f"{identifier}_CV")]
        
        if matching_files:
            # Return the path to the first matching file
            return os.path.join("data/resumes", matching_files[0])
    
    # Also check the resumes directory
    if os.path.exists("resumes"):
        # Get all files in the resumes directory
        resume_files = [f for f in os.listdir("resumes") if os.path.isfile(os.path.join("resumes", f))]
        
        # Look for files that contain the identifier
        matching_files = [f for f in resume_files if identifier in f]
        
        if matching_files:
            # Return the path to the first matching file
            return os.path.join("resumes", matching_files[0])
    
    return None