import streamlit as st
import os
import pandas as pd
import json
import qrcode
from PIL import Image
import io
from mysql_db import add_candidate, get_all_candidates as get_candidates, update_candidate
from utils import (
    fetch_google_form_responses, 
    find_matching_column, 
    fetch_cv_from_google_drive,
    fetch_edit_urls,
    send_edit_link_email
)
import uuid

# STEP 1: QR CODE GENERATOR
def generate_qr_image(url):
    qr = qrcode.make(url)
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    buf.seek(0)
    return Image.open(buf)

# Removed gatekeeper_expander() function as per requirements

def receptionist_view():
    st.title("📝 Walk-In Registration - BRV")

    # Navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["New Applicant", "View Profiles", "Edit Candidate"])
    
    # Show the selected page
    if page == "New Applicant":
        receptionist_new_applicant()
    elif page == "View Profiles":
        receptionist_profiles()
    elif page == "Edit Candidate":
        # Import here to avoid circular imports
        from edit_profile import edit_profile
        edit_profile()

def receptionist_new_applicant():

    # Step 2: Show QR code for Google Form
    st.subheader("📱 Pre-Interview Form (Scan Before Proceeding)")
    form_url = "https://forms.gle/WcERrdrfKRGKESWn9"
    qr_img = generate_qr_image(form_url)
    st.image(qr_img, caption="Scan this QR to fill the Pre-Interview Form", width=200)

    st.markdown("---")

    st.subheader("🔗 Synced from Google Form")

    # Add a reload button
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("Select an applicant from the dropdown below:")
    with col2:
        force_refresh = st.button("🔄 Reload Data")

    # Fetch data with force_refresh parameter and form_url
    form_df = fetch_google_form_responses(force_refresh=force_refresh, form_url=form_url)

    # Display debug information in an expandable section
    with st.expander("🔍 Google Form Responses"):
        st.success(f"✅ Loaded {len(form_df)} responses")
        st.write("📋 Columns:", form_df.columns.tolist())
        st.dataframe(form_df.tail(5))  # Show last 5 rows

    if form_df.empty:
        st.warning("⚠️ No responses yet. Please ensure the candidate fills the form first.")
        return

    # Try multiple possible column names for the full name field
    possible_name_columns = ["Full Name( First-middle-last)", "Full Name", "Name"]
    name_column = None
    
    for col in possible_name_columns:
        if col in form_df.columns:
            name_column = col
            break
    
    # If none of the possible columns are found, try using find_matching_column
    if name_column is None:
        from utils import find_matching_column
        name_column = find_matching_column(form_df.columns, "Full Name")
    
    # If still no matching column, show error and return
    if name_column is None:
        st.error("❌ No suitable column for full name was found in the Google Sheet data.")
        st.write("Available columns:", form_df.columns.tolist())
        st.warning("Please ensure the Google Sheet has a column for full name (e.g., 'Full Name', 'Name').")
        return
    
    st.info(f"Using '{name_column}' as the full name column.")
    
    full_names = form_df[name_column].unique()

    selected_name = st.selectbox("Select Applicant (First Middle Last)", options=full_names)

    # Get the selected applicant data
    selected_applicant = form_df[form_df[name_column] == selected_name].iloc[0]
    st.write("📄 **Applicant Details from Google Form:**")
    st.json(selected_applicant.to_dict(), expanded=False)

    # Fetch CV files from Google Drive
    st.subheader("📎 Resume/CV from Google Drive")

    # Get email from form data using the exact column name
    email = selected_applicant.get("Email Address", "")

    # Search for CV files using both name and email
    with st.spinner("Searching for CV files in Google Drive..."):
        cv_files = fetch_cv_from_google_drive(candidate_name=selected_name, candidate_email=email)

    if cv_files:
        st.success(f"✅ Found {len(cv_files)} potential CV file(s) for {selected_name}")

        # Display each CV file with a link
        for i, cv_file in enumerate(cv_files):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**{i+1}. {cv_file['name']}**")
            with col2:
                st.markdown(f"[View in Drive]({cv_file['url']})")

        # Select which CV to use
        selected_cv_index = st.selectbox("Select CV to use", 
                                        range(len(cv_files)), 
                                        format_func=lambda i: cv_files[i]['name'])

        # Store the selected CV URL
        selected_cv_url = cv_files[selected_cv_index]['url']
        st.session_state['selected_cv_url'] = selected_cv_url

        # Preview the selected CV if possible
        st.subheader("Preview Selected CV")
        from resume_handler import display_resume_from_url
        display_resume_from_url(selected_cv_url, selected_name)
    else:
        st.warning("⚠️ No CV files found in Google Drive for this candidate.")
        selected_cv_url = None
        st.session_state['selected_cv_url'] = None

    collected_by = st.text_input("👤 Collected By (Employee Name)")

    st.markdown("### 🧪 HR Fields")
    speed = st.text_input("Typing Speed (WPM)")
    accuracy = st.text_input("Typing Accuracy (%)")
    comments = st.text_area("Additional Comments")

    if st.button("✅ Save Candidate"):
        if not collected_by:
            st.warning("Please enter your name (employee collecting the form).")
            return

        form_data = selected_applicant.to_dict()

        # Get email, phone, and address using exact column names
        email = selected_applicant.get("Email Address", "")
        phone = selected_applicant.get("Phone number", "")
        
        # Use Current Address as primary, fall back to Permanent Address if needed
        address = selected_applicant.get("Current Address", 
                 selected_applicant.get("Permanent Address", ""))

        # Get the selected CV URL from session state
        selected_cv_url = st.session_state.get('selected_cv_url')

        hr_data = {
            "name": selected_name,
            "email": email,
            "phone": phone,
            "address": address,
            "collected_by": collected_by,
            "typing_speed": speed,
            "accuracy_test": accuracy,
            "comment": comments,
            "resume_path": None,  # No local resume file
            "resume_url": selected_cv_url  # Store the Google Drive URL
        }

        # Save to DB with both form data and HR data
        success, result = add_candidate(hr_data, form_data)

        # If we have a CV URL, also store it in the user's profile if they exist
        if selected_cv_url and email:
            try:
                from firebase_admin import firestore
                db = firestore.client()

                # Check if user exists
                user_ref = db.collection("users").document(email)
                user_doc = user_ref.get()

                if user_doc.exists:
                    # Update user with CV link
                    user_ref.update({
                        "cv_link": selected_cv_url,
                        "cv_updated_at": firestore.SERVER_TIMESTAMP
                    })

                # Also store in resumes collection for easier lookup
                db.collection("resumes").document(email).set({
                    "resume_url": selected_cv_url,
                    "candidate_name": selected_name,
                    "updated_at": firestore.SERVER_TIMESTAMP
                }, merge=True)

                print(f"[DEBUG] Stored CV link for {email}: {selected_cv_url}")
            except Exception as e:
                print(f"[ERROR] Failed to store CV link in user profile: {e}")
                import traceback
                traceback.print_exc()

        # ✅ Confirmation screen
        st.success("✅ Candidate data saved successfully!")
        st.markdown("---")
        st.subheader("📋 Confirmation Summary")

        st.write(f"**🆔 Candidate Name:** {selected_name}")
        st.write(f"**👤 Collected By:** {collected_by}")

        # Display contact information if available
        if email:
            st.write(f"**📧 Email:** {email}")
        if phone:
            st.write(f"**📱 Phone:** {phone}")
        if address:
            st.write(f"**🏠 Address:** {address}")

        # Display HR assessment
        st.write(f"**⌨️ Typing Speed:** {speed} WPM")
        st.write(f"**🎯 Accuracy:** {accuracy}%")

        if comments:
            st.write(f"**📝 Additional Comments:** {comments}")

def receptionist_profiles():
    st.header("👥 Applicant Profiles")

    # Fetch all candidates
    candidates = get_candidates()

    if candidates:
        # Create a list of dictionaries for the DataFrame
        candidates_list = []
        for candidate in candidates:
            # Extract basic info from the candidate dictionary
            name = candidate.get('Candidate Name', 'Unknown')
            email = candidate.get('Email', 'Unknown')
            phone = candidate.get('Phone', 'Unknown')
            status = candidate.get('Interview Status', 'Pending')

            # Add to list
            candidates_list.append({
                "Name": name,
                "Email": email,
                "Phone": phone,
                "Status": status
            })

        # Convert to DataFrame for display
        df = pd.DataFrame(candidates_list)
        st.dataframe(df)

        # Select candidate to view/edit
        selected_email = st.selectbox("Select Candidate to View/Edit", 
                                  [c['Email'] for c in candidates_list])

        if selected_email:
            # Find the candidate in the original data
            candidate = next((c for c in candidates if c.get('Email') == selected_email), None)

            if candidate:
                st.subheader(f"Profile: {candidate.get('Candidate Name', 'Unknown')}")

                # Display current info
                st.write(f"**Email:** {candidate.get('Email', 'Unknown')}")
                st.write(f"**Phone:** {candidate.get('Phone', 'Unknown')}")
                st.write(f"**Address:** {candidate.get('Address', 'Unknown')}")

                # Parse HR data if available
                hr_data = {}
                if candidate.get('hr_data'):  # hr_data field
                    try:
                        if isinstance(candidate.get('hr_data'), str):
                            hr_data = json.loads(candidate.get('hr_data'))
                        else:
                            hr_data = candidate.get('hr_data', {})
                        st.subheader("HR Assessment")
                        for key, value in hr_data.items():
                            if key not in ['name', 'email', 'phone', 'address', 'resume_path']:
                                st.write(f"**{key.replace('_', ' ').title()}:** {value}")
                    except:
                        st.warning("Could not parse HR data")

                # Resume handling
                resume_file = candidate.get('resume_path')  # resume_path field

                # Check if there's a local resume file
                if resume_file and os.path.exists(resume_file):
                    with open(resume_file, "rb") as f:
                        st.download_button("📄 Download Resume", f, file_name=os.path.basename(resume_file))
                else:
                    # Check if there's a resume URL in the HR data
                    resume_url = None
                    if hr_data and 'resume_url' in hr_data:
                        resume_url = hr_data['resume_url']

                    if resume_url:
                        st.success("📄 Resume available from Google Drive")
                        st.markdown(f"[View Resume in Google Drive]({resume_url})")

                        # Preview the resume
                        st.subheader("Resume Preview")
                        from resume_handler import display_resume_from_url
                        display_resume_from_url(resume_url, candidate.get('Candidate Name', 'Unknown'))
                    else:
                        st.warning("⚠️ Resume not uploaded or file not found.")
                
                # Form Edit Permission Section
                st.subheader("🔐 Form Edit Permission")
                
                # Get candidate email
                candidate_email = candidate.get('Email', '')
                
                if candidate_email:
                    # Create columns for the edit permission section
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        st.write("Allow the candidate to edit their Google Form response.")
                        st.write("This will send an email with a unique edit link to the candidate.")
                    
                    # Fetch edit URLs with a refresh button
                    with col2:
                        refresh_edit_urls = st.button("🔄 Refresh Edit URLs")
                    
                    # Fetch edit URLs
                    edit_urls = fetch_edit_urls(force_refresh=refresh_edit_urls)
                    
                    # Check if we have an edit URL for this candidate
                    if candidate_email in edit_urls:
                        edit_url = edit_urls[candidate_email]
                        
                        # Create a button to send the edit link
                        if st.button("✉️ Send Edit Link to Candidate"):
                            # Send the edit link email
                            success = send_edit_link_email(
                                candidate_email, 
                                edit_url, 
                                candidate_name=candidate.get('Candidate Name', 'Unknown')
                            )
                            
                            if success:
                                st.success(f"✅ Edit link sent to {candidate_email}")
                            else:
                                st.error(f"❌ Failed to send edit link to {candidate_email}")
                    else:
                        st.warning("⚠️ No edit URL found for this candidate.")
                        st.info("Make sure the Google Form is set up correctly and the Google Apps Script is running.")
                        
                        # Show setup instructions in an expander
                        with st.expander("📋 Setup Instructions"):
                            st.markdown("""
                            ### Google Form Setup
                            1. Open your Google Form
                            2. Go to Settings (gear icon)
                            3. Enable "Collect email addresses"
                            4. Enable "Limit to 1 response"
                            5. Enable "Allow response editing"
                            
                            ### Google Apps Script Setup
                            1. Open your Google Sheet linked to the form
                            2. Go to Extensions > Apps Script
                            3. Copy and paste the code from `google_form_edit_urls.js`
                            4. Save and run the script
                            """)
                else:
                    st.warning("⚠️ No email address found for this candidate.")

                # Edit form
                with st.form("edit_profile"):
                    # Get current values for the form
                    current_status = candidate.get('Interview Status', 'Pending')

                    # Form fields
                    new_status = st.selectbox(
                        "Status", 
                        ["Pending", "Interview Scheduled", "Pass", "Fail", "Hold"],
                        index=["Pending", "Interview Scheduled", "Pass", "Fail", "Hold"].index(current_status) 
                        if current_status in ["Pending", "Interview Scheduled", "Pass", "Fail", "Hold"] else 0
                    )

                    # Get current HR data or initialize empty
                    current_hr_data = hr_data.copy() if hr_data else {}

                    # HR assessment fields
                    typing_speed = st.text_input(
                        "Typing Speed (WPM)", 
                        value=current_hr_data.get("typing_speed", "")
                    )

                    accuracy = st.text_input(
                        "Accuracy (%)", 
                        value=current_hr_data.get("accuracy_test", "")
                    )

                    submit = st.form_submit_button("Update Profile")

                    if submit:
                        # Update HR data
                        current_hr_data.update({
                            "typing_speed": typing_speed,
                            "accuracy_test": accuracy
                        })

                        # Update candidate in database
                        update_candidate(selected_email, new_status, current_hr_data)
                        st.success("Profile updated successfully!")
                        st.rerun()
    else:
        st.info("No candidates registered yet.")

# For testing the receptionist view directly
if __name__ == "__main__":
    st.set_page_config(
        page_title="Receptionist View - BRV Applicant System",
        page_icon="📋",
        layout="wide"
    )

    # Initialize session state for testing
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = True
    if 'user_id' not in st.session_state:
        st.session_state.user_id = "test_receptionist_id"
    if 'user_role' not in st.session_state:
        st.session_state.user_role = "receptionist"

    receptionist_view()
