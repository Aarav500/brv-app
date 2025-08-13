# candidate_view.py
import streamlit as st
import uuid
from datetime import datetime
from db_postgres import get_candidate_by_id, create_candidate_in_db, update_candidate_form_data, \
    update_candidate_resume_link
import json


def upload_resume_to_drive(candidate_id: str, file_bytes: bytes, filename: str):
    """
    Placeholder function for Google Drive upload
    Replace this with your actual Google Drive integration
    """
    # This is a placeholder - implement your actual Drive upload logic here
    st.warning("Google Drive upload not implemented yet")
    return False, "", "Drive upload not configured"


def candidate_form_view():
    st.header("Candidate — Submit / Edit Application")

    # Form fields
    candidate_id = st.text_input(
        "Candidate ID",
        placeholder="Leave blank to create new application",
        help="If you have an existing Candidate ID, enter it here to edit your application"
    )

    name = st.text_input("Full Name", placeholder="Enter your full name")
    email = st.text_input("Email Address", placeholder="Enter your email address")
    phone = st.text_input("Phone Number", placeholder="Enter your phone number")

    # Additional form fields
    st.subheader("Additional Information")
    skills = st.text_area("Skills", placeholder="List your key skills and technologies")
    experience = st.text_area("Experience", placeholder="Describe your work experience")
    education = st.text_area("Education", placeholder="Your educational background")

    # Resume upload
    st.subheader("Resume Upload")
    uploaded_file = st.file_uploader(
        "Upload Resume/CV",
        type=["pdf", "doc", "docx"],
        help="PDF format recommended"
    )

    # Check existing candidate if ID provided
    existing_candidate = None
    can_edit = False

    if candidate_id.strip():
        try:
            existing_candidate = get_candidate_by_id(candidate_id.strip())
            if existing_candidate:
                st.success("✅ Found existing application")

                # Check edit permission
                can_edit = existing_candidate.get('can_edit', False)
                if can_edit:
                    st.info("🔓 You have permission to edit this application")

                    # Pre-populate form with existing data
                    if not name and existing_candidate.get('name'):
                        name = existing_candidate['name']
                    if not email and existing_candidate.get('email'):
                        email = existing_candidate['email']
                    if not phone and existing_candidate.get('phone'):
                        phone = existing_candidate['phone']

                    # Pre-populate additional fields from form_data
                    form_data = existing_candidate.get('form_data', {})
                    if isinstance(form_data, str):
                        try:
                            form_data = json.loads(form_data)
                        except:
                            form_data = {}

                    if not skills and form_data.get('skills'):
                        skills = form_data['skills']
                    if not experience and form_data.get('experience'):
                        experience = form_data['experience']
                    if not education and form_data.get('education'):
                        education = form_data['education']

                else:
                    st.warning("🔒 Edit permission not granted. Contact the receptionist to enable editing.")

                # Show existing resume if available
                if existing_candidate.get('resume_link'):
                    st.markdown(f"**Current Resume:** [View Resume]({existing_candidate['resume_link']})")

            else:
                st.warning("❌ Candidate ID not found")

        except Exception as e:
            st.error(f"Error checking candidate ID: {str(e)}")

    # Submit button
    if st.button("Submit Application", type="primary"):
        # Validation
        if not name.strip() or not email.strip():
            st.error("❌ Name and email are required fields")
            return

        try:
            if not candidate_id.strip():
                # Create new candidate
                new_candidate_id = str(uuid.uuid4())[:8].upper()

                # Prepare form data
                form_data = {
                    "skills": skills.strip(),
                    "experience": experience.strip(),
                    "education": education.strip(),
                    "allowed_edit": False,
                    "history": [{
                        "action": "created",
                        "at": datetime.utcnow().isoformat(),
                        "source": "candidate_portal"
                    }]
                }

                # Create candidate in database
                result = create_candidate_in_db(
                    candidate_id=new_candidate_id,
                    name=name.strip(),
                    email=email.strip(),
                    phone=phone.strip(),
                    form_data=form_data,
                    created_by="candidate_portal"
                )

                if result:
                    st.success(f"🎉 Application created successfully!")
                    st.info(f"📝 Your Candidate ID: **{new_candidate_id}**")
                    st.info("💡 Save this ID to edit your application later")
                    candidate_id = new_candidate_id  # Update for resume upload
                else:
                    st.error("❌ Failed to create application. Please try again.")
                    return

            else:
                # Update existing candidate
                if not existing_candidate:
                    st.error("❌ Candidate ID not found")
                    return

                if not can_edit:
                    st.error("❌ You don't have permission to edit this application")
                    return

                # Verify name matches (security check)
                if existing_candidate.get('name', '').strip().lower() != name.strip().lower():
                    st.error("❌ Name doesn't match the original application. Permission denied.")
                    return

                # Update form data
                existing_form_data = existing_candidate.get('form_data', {})
                if isinstance(existing_form_data, str):
                    try:
                        existing_form_data = json.loads(existing_form_data)
                    except:
                        existing_form_data = {}

                # Update fields
                existing_form_data.update({
                    "skills": skills.strip(),
                    "experience": experience.strip(),
                    "education": education.strip()
                })

                # Add history entry
                existing_form_data.setdefault('history', []).append({
                    "action": "updated_by_candidate",
                    "at": datetime.utcnow().isoformat()
                })

                # Update in database
                success = update_candidate_form_data(candidate_id.strip(), existing_form_data)
                if success:
                    st.success("✅ Application updated successfully!")
                else:
                    st.error("❌ Failed to update application")
                    return

            # Handle resume upload
            if uploaded_file is not None:
                file_bytes = uploaded_file.read()
                st.info("📤 Uploading resume...")

                try:
                    success, webview_url, message = upload_resume_to_drive(
                        candidate_id,
                        file_bytes,
                        uploaded_file.name
                    )

                    if success:
                        # Update resume link in database
                        if update_candidate_resume_link(candidate_id, webview_url):
                            st.success("📄 Resume uploaded and linked successfully!")
                            st.markdown(f"[📎 View Your Resume]({webview_url})")
                        else:
                            st.warning("⚠️ Resume uploaded but failed to update database link")
                    else:
                        st.error(f"❌ Resume upload failed: {message}")

                except Exception as e:
                    st.error(f"❌ Resume upload error: {str(e)}")

        except Exception as e:
            st.error(f"❌ Error submitting application: {str(e)}")


def candidate_view():
    """Main candidate view function (keeping for backward compatibility)"""
    candidate_form_view()