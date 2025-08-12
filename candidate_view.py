import streamlit as st
import uuid
from datetime import datetime
from db import get_candidate_by_id, create_candidate, update_candidate_form_data, update_candidate_resume_link, upload_resume_to_drive

def candidate_view():
    st.header("Candidate — Submit / Edit Application")

    candidate_id = st.text_input("Candidate ID (leave blank to create new)")
    name = st.text_input("Full name")
    email = st.text_input("Email")
    phone = st.text_input("Phone")
    uploaded_file = st.file_uploader("Upload CV", type=["pdf"], help="PDF recommended")

    if candidate_id:
        existing = get_candidate_by_id(candidate_id)
        if existing:
            st.info("Found record — you may edit if receptionist granted permission for your name.")
            st.write("Allowed Edit:", existing.get('form_data', {}).get('allowed_edit', False))
        else:
            st.warning("Candidate ID not found.")

    if st.button("Submit"):
        if not name or not email:
            st.warning("Name and email are required.")
            return

        if not candidate_id:
            # new record
            candidate_id = str(uuid.uuid4())[:8]
            form_data = {"allowed_edit": False, "history": [{"action": "created", "at": datetime.utcnow().isoformat()}]}
            created = create_candidate(candidate_id, name, email, phone, form_data, "candidate_portal")
            if created:
                st.success(f"Application created. Your Candidate ID: {candidate_id}")
            else:
                st.error("Failed to create candidate.")
        else:
            existing = get_candidate_by_id(candidate_id)
            if not existing:
                st.error("Candidate ID not found.")
                return

            # permission check — match name exactly & allowed_edit
            fd = existing.get('form_data') or {}
            allowed = fd.get('allowed_edit') and existing.get('name', '').strip().lower() == name.strip().lower()

            if not allowed:
                st.error("Permission denied. Receptionist has not granted edit rights for this name.")
                return

            fd.setdefault('history', []).append({"action": "edited_by_candidate", "at": datetime.utcnow().isoformat()})
            update_candidate_form_data(candidate_id, fd)
            st.success("Application updated.")

        # resume upload
        if uploaded_file:
            bytes_ = uploaded_file.read()
            st.info("Uploading resume to Google Drive...")
            success, webview, msg = upload_resume_to_drive(candidate_id, bytes_, uploaded_file.name)
            if success:
                update_candidate_resume_link(candidate_id, webview)
                st.success("Resume uploaded and linked.")
                st.markdown(f"[Open Resume]({webview})")
            else:
                st.error("Resume upload failed: " + msg)
