import streamlit as st
import uuid
from datetime import datetime
import json
from db_postgres import (
    get_candidate_by_id,
    create_candidate_in_db,
    update_candidate_form_data,
    set_candidate_permission,
    save_candidate_cv,
    get_candidate_cv,
    delete_candidate_cv,
    get_conn,
)
from receptionist import _send_candidate_code   # ✅ for emailing Candidate ID


import streamlit as st
from db_postgres import create_candidate_in_db
from datetime import date

def candidate_form():
    st.header("📝 Candidate Pre-Interview Form")
    # Always initialize candidate_id
    candidate_id = st.text_input("Candidate ID (auto-generated if left blank)", "")
    name = st.text_input("Full Name")
    current_address = st.text_area("Current Address")
    permanent_address = st.text_area("Permanent Address")
    dob = st.date_input("Date of Birth", min_value=date(1900, 1, 1), max_value=date.today())
    caste = st.text_input("Caste")
    sub_caste = st.text_input("Sub-Caste")
    marital_status = st.selectbox("Marital Status", ["Single", "Married", "Divorced", "Widowed"])
    highest_qualification = st.text_input("Highest Qualification")
    work_experience = st.text_area("Work Experience")
    referral = st.text_input("Referral (if any)")

    ready_festivals = st.radio("Ready to work on festivals and national holidays?", ["Yes", "No"])
    ready_late_nights = st.radio("Ready to work late nights if needed?", ["Yes", "No"])

    email = st.text_input("Email")
    phone = st.text_input("Phone")

    if st.button("Submit Candidate Form"):
        if not name:
            st.error("Full name is required.")
        else:
            candidate_id = f"cand_{int(date.today().strftime('%Y%m%d'))}_{phone[-4:] if phone else '0000'}"
            data = {
                "name": name,
                "current_address": current_address,
                "permanent_address": permanent_address,
                "dob": str(dob),
                "caste": caste,
                "sub_caste": sub_caste,
                "marital_status": marital_status,
                "highest_qualification": highest_qualification,
                "work_experience": work_experience,
                "referral": referral,
                "ready_festivals": (ready_festivals == "Yes"),
                "ready_late_nights": (ready_late_nights == "Yes"),
                "email": email,
                "phone": phone
            }
            created = create_candidate_in_db(
                candidate_id,
                name,
                current_address,
                dob,
                caste,
                email,
                phone,
                data,
                created_by="self-service"
            )
            if created:
                st.success(f"Candidate {name} registered successfully!")
            else:
                st.error("Error saving candidate data.")

    # Resume upload
    st.subheader("Resume Upload")
    uploaded_file = st.file_uploader(
        "Upload Resume/CV", type=["pdf", "doc", "docx"], help="PDF format recommended"
    )

    # Existing candidate check
    existing_candidate, can_edit = None, False
    if candidate_id.strip():
        try:
            existing_candidate = get_candidate_by_id(candidate_id.strip())
            if existing_candidate:
                st.success("✅ Found existing application")
                can_edit = existing_candidate.get("can_edit", False)
                if can_edit:
                    st.info("🔓 You have permission to edit this application")
                else:
                    st.warning("🔒 Edit permission not granted. Contact receptionist.")
                if existing_candidate.get("cv_filename"):
                    st.markdown(f"**Current Resume:** {existing_candidate['cv_filename']}")
            else:
                st.warning("❌ Candidate ID not found")
        except Exception as e:
            st.error(f"Error checking candidate ID: {str(e)}")

    # Submit
    if st.button("Submit Application", type="primary"):
        # 🔴 Validate mandatory fields
        if not all([
            name.strip(),
            email.strip(),
            phone.strip(),
            skills.strip(),
            experience.strip(),
            education.strip(),
        ]):
            st.error("❌ All fields are mandatory (Name, Email, Phone, Skills, Experience, Education).")
            return

        try:
            if not candidate_id.strip():
                # --- Prevent duplicates by checking email ---
                conn = get_conn()
                with conn, conn.cursor() as cur:
                    cur.execute("SELECT candidate_id FROM candidates WHERE email = %s", (email.strip(),))
                    row = cur.fetchone()
                conn.close()

                if row:
                    candidate_id = row[0]
                    st.info(f"⚠️ Candidate already exists. Using existing ID: {candidate_id}")
                else:
                    # --- Create new candidate ---
                    new_candidate_id = str(uuid.uuid4())[:8].upper()
                    form_data = {
                        "skills": skills.strip(),
                        "experience": experience.strip(),
                        "education": education.strip(),
                        "allowed_edit": False,
                        "history": [
                            {"action": "created", "at": datetime.utcnow().isoformat()}
                        ],
                    }

                    result = create_candidate_in_db(
                        candidate_id=new_candidate_id,
                        name=name.strip(),
                        email=email.strip(),
                        phone=phone.strip(),
                        form_data=form_data,
                        created_by="candidate_portal",
                    )

                    if result:
                        st.success("🎉 Application created successfully!")
                        st.info(f"📝 Your Candidate ID: **{new_candidate_id}**")
                        candidate_id = new_candidate_id

                        # ✅ Send Candidate ID by email
                        ok, msg = _send_candidate_code(email.strip(), new_candidate_id)
                        if ok:
                            st.success("📧 Candidate ID emailed successfully.")
                        else:
                            st.warning(f"⚠️ Could not send email: {msg}")
                    else:
                        st.error("❌ Failed to create application")
                        return

            else:
                # --- Update existing candidate ---
                if not existing_candidate:
                    st.error("❌ Candidate ID not found")
                    return
                if not can_edit:
                    st.error("❌ You don't have permission to edit this application")
                    return

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
                    {"action": "updated_by_candidate", "at": datetime.utcnow().isoformat()}
                )

                success = update_candidate_form_data(candidate_id.strip(), existing_form_data)
                set_candidate_permission(candidate_id, False)

                if success:
                    st.success("✅ Application updated successfully! Edit permission reset.")
                else:
                    st.error("❌ Failed to update application")
                    return

            # --- Resume upload (AFTER candidate exists) ---
            if uploaded_file is not None:
                file_bytes = uploaded_file.read()
                filename = uploaded_file.name
                ok = save_candidate_cv(candidate_id, file_bytes, filename)
                if ok:
                    st.success("📄 Resume uploaded successfully!")
                    st.info(f"Saved as {filename}")
                else:
                    st.error("❌ Failed to upload resume")

        except Exception as e:
            st.error(f"❌ Error submitting application: {str(e)}")

    # Resume management
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

def candidate_form_view():
    """Wrapper so main.py can call candidate form."""
    st.title("Candidate Registration")
    candidate_form()


def candidate_view():
    """Main candidate view function (backward compatibility)"""
    candidate_form_view()
