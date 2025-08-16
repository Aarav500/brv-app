import streamlit as st
import uuid
from datetime import datetime
import json
from db_postgres import (
    get_candidate_by_id,
    create_candidate_in_db,
    update_candidate_form_data,
    update_candidate_resume_link,  # keep for backward compatibility
    set_candidate_permission,
    save_candidate_cv,
    get_candidate_cv,
    delete_candidate_cv,
)


def candidate_form_view():
    st.header("Candidate — Submit / Edit Application")

    # Form fields
    candidate_id = st.text_input(
        "Candidate ID",
        placeholder="Leave blank to create new application",
        help="If you have an existing Candidate ID, enter it here to edit your application",
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
        help="PDF format recommended",
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
                can_edit = existing_candidate.get("can_edit", False)
                if can_edit:
                    st.info("🔓 You have permission to edit this application")

                    # Show current values
                    st.info(f"Current Name: {existing_candidate.get('name', 'Not set')}")
                    st.info(f"Current Email: {existing_candidate.get('email', 'Not set')}")
                    st.info(f"Current Phone: {existing_candidate.get('phone', 'Not set')}")

                else:
                    st.warning("🔒 Edit permission not granted. Contact the receptionist to enable editing.")

                # Show existing resume if available
                if existing_candidate.get("cv_filename"):
                    st.markdown(f"**Current Resume:** {existing_candidate['cv_filename']}")

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
                    "history": [
                        {
                            "action": "created",
                            "at": datetime.utcnow().isoformat(),
                            "source": "candidate_portal",
                        }
                    ],
                }

                # Create candidate in database
                result = create_candidate_in_db(
                    candidate_id=new_candidate_id,
                    name=name.strip(),
                    email=email.strip(),
                    phone=phone.strip(),
                    form_data=form_data,
                    created_by="candidate_portal",
                )

                if result:
                    st.success(f"🎉 Application created successfully!")
                    st.info(f"📝 Your Candidate ID: **{new_candidate_id}**")
                    st.info("💡 Save this ID to edit your application later")
                    candidate_id = new_candidate_id
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

                st.info("✅ Candidate ID verified. Name can be updated.")

                # Update form data
                existing_form_data = existing_candidate.get("form_data") or {}
                if isinstance(existing_form_data, str):
                    try:
                        existing_form_data = json.loads(existing_form_data)
                    except:
                        existing_form_data = {}

                existing_form_data.update(
                    {
                        "skills": skills.strip(),
                        "experience": experience.strip(),
                        "education": education.strip(),
                    }
                )

                existing_form_data.setdefault("history", []).append(
                    {
                        "action": "updated_by_candidate",
                        "at": datetime.utcnow().isoformat(),
                    }
                )

                success = update_candidate_form_data(candidate_id.strip(), existing_form_data)
                set_candidate_permission(candidate_id, False)

                if success:
                    st.success("✅ Application updated successfully! Edit permission reset.")
                else:
                    st.error("❌ Failed to update application")
                    return

            # Handle resume upload
            if uploaded_file is not None:
                file_bytes = uploaded_file.read()
                filename = uploaded_file.name
                st.info("📤 Uploading resume...")

                ok = save_candidate_cv(candidate_id, file_bytes, filename)
                if ok:
                    st.success("📄 Resume uploaded successfully!")
                    st.info(f"Saved as {filename}")
                else:
                    st.error("❌ Failed to upload resume")

        except Exception as e:
            st.error(f"❌ Error submitting application: {str(e)}")

    # Resume management section (if candidate exists)
    if candidate_id.strip():
        file_bytes, filename = get_candidate_cv(candidate_id.strip())
        if file_bytes:
            st.download_button(
                "📥 Download Your Resume",
                file_bytes,
                file_name=filename or f"{candidate_id}.pdf",
            )
            if st.button("🗑️ Delete Resume"):
                if delete_candidate_cv(candidate_id.strip()):
                    st.success("✅ Resume deleted successfully")
                else:
                    st.error("❌ Failed to delete resume")


def candidate_view():
    """Main candidate view function (backward compatibility)"""
    candidate_form_view()
