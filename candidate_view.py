# candidate_view.py (fixed with session state)
import json
import secrets
import string
from datetime import datetime, date
from typing import Dict, Any, Optional

import streamlit as st
import base64

from db_postgres import (
    create_candidate_in_db,
    update_candidate_form_data,
    get_candidate_by_id,
    save_candidate_cv,
    get_candidate_cv_secure,
    get_all_candidates,
)


# --------------------------------
# helpers
# --------------------------------

def _gen_candidate_code(prefix="BRV") -> str:
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(chars) for _ in range(6))
    return f"{prefix}-{suffix}"


def _safe_json(o: Any) -> Any:
    try:
        json.dumps(o)
        return o
    except Exception:
        return {}


def _cv_uploader(candidate_id: str):
    st.markdown("### Upload/Replace CV")
    file = st.file_uploader("Upload CV (PDF or DOC/DOCX preferred)", type=["pdf", "doc", "docx"],
                            key=f"cv_{candidate_id}")
    if file is not None:
        file_bytes = file.read()
        ok = save_candidate_cv(candidate_id, file_bytes, file.name)
        if ok:
            st.success("CV saved.")
        else:
            st.error("Failed to save CV.")


# --------------------------------
# Candidate views
# --------------------------------

def candidate_form_view():
    st.header("Candidate — Pre-Interview Application")
    mode = st.radio("I am a…", ["New candidate", "Returning candidate"], horizontal=True)

    if mode == "New candidate":
        st.subheader("Pre-Interview Form")
        st.info("Fields marked with * are required")

        # Use form to ensure all data is captured together
        with st.form("candidate_form", clear_on_submit=False):
            # Initialize session state for initial values if not exists
            if 'form_data' not in st.session_state:
                st.session_state.form_data = {}

            initial_data = st.session_state.form_data

            # Basic Information
            name = st.text_input("Full Name *",
                                 value=initial_data.get("name", ""),
                                 help="Required field")

            email = st.text_input("Email *",
                                  value=initial_data.get("email", ""),
                                  help="Required field")

            phone = st.text_input("Phone *",
                                  value=initial_data.get("phone", ""),
                                  help="Required field - 10 digits minimum")

            # Addresses
            current_address = st.text_area("Current Address *",
                                           value=initial_data.get("current_address", ""),
                                           help="Required field")

            permanent_address = st.text_area("Permanent Address *",
                                             value=initial_data.get("permanent_address", ""),
                                             help="Required field")

            # Personal details
            col1, col2, col3 = st.columns(3)

            with col1:
                # DOB handling
                dob_default = None
                if initial_data.get("dob"):
                    try:
                        dob_default = datetime.fromisoformat(initial_data["dob"]).date()
                    except:
                        dob_default = None

                if dob_default:
                    dob = st.date_input("Date of Birth *",
                                        value=dob_default,
                                        min_value=date(1950, 1, 1),
                                        max_value=date.today(),
                                        help="Required field")
                else:
                    dob = st.date_input("Date of Birth *",
                                        min_value=date(1950, 1, 1),
                                        max_value=date.today(),
                                        help="Required field - Please select your date of birth")

            with col2:
                caste = st.text_input("Caste",
                                      value=initial_data.get("caste", ""))

            with col3:
                sub_caste = st.text_input("Sub-caste",
                                          value=initial_data.get("sub_caste", ""))

            # Marital status & education
            col4, col5 = st.columns(2)

            with col4:
                marital_options = ["Single", "Married", "Divorced", "Widowed", "Prefer not to say"]
                marital_index = 0
                if initial_data.get("marital_status") in marital_options:
                    marital_index = marital_options.index(initial_data["marital_status"])

                marital_status = st.selectbox("Marital Status",
                                              options=marital_options,
                                              index=marital_index)

            with col5:
                highest_qualification = st.text_input("Highest Qualification *",
                                                      value=initial_data.get("highest_qualification", ""),
                                                      help="Required field")

            # Work & referral
            work_experience = st.text_area("Work Experience (years/summary) *",
                                           value=initial_data.get("work_experience", ""),
                                           help="Required field - Describe your work experience")

            referral = st.text_input("Referral (if any) *",
                                     value=initial_data.get("referral", ""),
                                     help="Required field - How did you hear about us?")

            # Availability
            col6, col7 = st.columns(2)

            with col6:
                festivals_index = 1 if initial_data.get("ready_festivals") == "Yes" else 0
                ready_festivals = st.selectbox("Ready to work on festivals and national holidays?",
                                               options=["No", "Yes"],
                                               index=festivals_index)

            with col7:
                nights_index = 1 if initial_data.get("ready_late_nights") == "Yes" else 0
                ready_late_nights = st.selectbox("Ready to work late nights if needed?",
                                                 options=["No", "Yes"],
                                                 index=nights_index)

            # CV Upload
            st.markdown("### CV Upload *")
            uploaded_cv = st.file_uploader("Upload Your Resume (PDF/DOC/DOCX preferred) — REQUIRED",
                                           type=["pdf", "doc", "docx"],
                                           help="This is a required field. Please upload your CV in PDF, DOC, or DOCX format.")

            # Submit button inside the form
            submitted = st.form_submit_button("Submit Application", type="primary")

            if submitted:
                # Collect all form data
                form_data = {
                    "name": name.strip() if name else "",
                    "email": email.strip() if email else "",
                    "phone": "".join(filter(str.isdigit, phone)) if phone else "",
                    "current_address": current_address.strip() if current_address else "",
                    "permanent_address": permanent_address.strip() if permanent_address else "",
                    "dob": dob.isoformat() if isinstance(dob, date) else None,
                    "caste": caste.strip() if caste else "",
                    "sub_caste": sub_caste.strip() if sub_caste else "",
                    "marital_status": marital_status,
                    "highest_qualification": highest_qualification.strip() if highest_qualification else "",
                    "work_experience": work_experience.strip() if work_experience else "",
                    "referral": referral.strip() if referral else "",
                    "ready_festivals": "Yes" if ready_festivals == "Yes" else "No",
                    "ready_late_nights": "Yes" if ready_late_nights == "Yes" else "No",
                    "uploaded_cv": uploaded_cv,
                    "updated_at": datetime.utcnow().isoformat(),
                }

                # Store in session state
                st.session_state.form_data = form_data

                # Debug output
                with st.expander("Debug: Form Data Captured", expanded=True):
                    st.write("Debugging validation:")
                    st.write(f"Name: '{form_data.get('name', '')}' (length: {len(form_data.get('name', ''))})")
                    st.write(f"Email: '{form_data.get('email', '')}' (length: {len(form_data.get('email', ''))})")
                    st.write(f"Phone: '{form_data.get('phone', '')}' (length: {len(form_data.get('phone', ''))})")
                    st.write(f"DOB: '{form_data.get('dob', 'None')}'")
                    st.write(
                        f"Current Address: '{form_data.get('current_address', '')}' (length: {len(form_data.get('current_address', ''))})")
                    st.write(
                        f"Permanent Address: '{form_data.get('permanent_address', '')}' (length: {len(form_data.get('permanent_address', ''))})")
                    st.write(
                        f"Qualification: '{form_data.get('highest_qualification', '')}' (length: {len(form_data.get('highest_qualification', ''))})")
                    st.write(
                        f"Work Experience: '{form_data.get('work_experience', '')}' (length: {len(form_data.get('work_experience', ''))})")
                    st.write(
                        f"Referral: '{form_data.get('referral', '')}' (length: {len(form_data.get('referral', ''))})")
                    st.write(f"CV: {form_data.get('uploaded_cv')}")

                # Validation
                validation_errors = []

                if not form_data.get("name"):
                    validation_errors.append("• Full Name is required")

                email_val = form_data.get("email", "")
                if not email_val:
                    validation_errors.append("• Email is required")
                elif "@" not in email_val or "." not in email_val.split("@")[-1]:
                    validation_errors.append("• Please enter a valid email address")

                phone_val = form_data.get("phone", "")
                if not phone_val:
                    validation_errors.append("• Phone number is required")
                elif len(phone_val) < 10:
                    validation_errors.append("• Phone number must be at least 10 digits")

                if not form_data.get("dob"):
                    validation_errors.append("• Date of Birth is required")

                if not form_data.get("current_address"):
                    validation_errors.append("• Current Address is required")

                if not form_data.get("permanent_address"):
                    validation_errors.append("• Permanent Address is required")

                if not form_data.get("highest_qualification"):
                    validation_errors.append("• Highest Qualification is required")

                if not form_data.get("work_experience"):
                    validation_errors.append("• Work Experience is required")

                if not form_data.get("referral"):
                    validation_errors.append("• Referral information is required")

                if not form_data.get("uploaded_cv"):
                    validation_errors.append("• CV upload is required")

                if validation_errors:
                    st.error("Please fix the following issues before submitting:")
                    for error in validation_errors:
                        st.error(error)
                else:
                    # Validation passed - create candidate
                    candidate_id = _gen_candidate_code()
                    rec = create_candidate_in_db(
                        candidate_id=candidate_id,
                        name=form_data.get("name", ""),
                        address=form_data.get("current_address", ""),
                        dob=form_data.get("dob", None),
                        caste=form_data.get("caste", ""),
                        email=form_data.get("email", ""),
                        phone=form_data.get("phone", ""),
                        form_data=_safe_json(form_data),
                        created_by="candidate",
                    )

                    if rec:
                        st.success(f"✅ Application submitted! Your candidate code is: **{candidate_id}**")

                        # Save CV
                        cv_file = form_data.get("uploaded_cv")
                        if cv_file:
                            file_bytes = cv_file.read()
                            ok = save_candidate_cv(candidate_id, file_bytes, cv_file.name)
                            if ok:
                                st.success("📄 CV uploaded successfully.")
                            else:
                                st.error("⚠️ Failed to save CV.")

                        # Clear the form data from session state
                        st.session_state.form_data = {}
                        st.rerun()
                    else:
                        st.error("Failed to create candidate record. Please try again.")

    else:
        # Returning candidate section
        st.caption("Enter your candidate code to view and edit your application (if permission is granted).")
        candidate_code = st.text_input("Candidate Code", key="cand_code")

        if candidate_code.strip():
            rec = get_candidate_by_id(candidate_code.strip())
            if not rec:
                st.error("No record found for the provided code.")
            else:
                existing_form = rec.get("form_data") or {}
                st.info(f"Welcome back, {rec.get('name', 'Candidate')}")

                from auth import get_current_user
                user = get_current_user()
                actor_id = (user.get("id") if user else 0)

                # Always allow CV upload
                _cv_uploader(candidate_code.strip())

                # Secure CV fetch
                try:
                    res = get_candidate_cv_secure(candidate_code.strip(), actor_id)
                    cv_bytes = cv_name = mime_type = None
                    reason = "not_found"

                    if isinstance(res, (tuple, list)):
                        if len(res) == 4:
                            cv_bytes, cv_name, mime_type, reason = res
                        elif len(res) == 3:
                            cv_bytes, cv_name, reason = res
                            mime_type = None
                    elif isinstance(res, (bytes, bytearray)):
                        cv_bytes = bytes(res)
                        cv_name = f"{candidate_code}_cv.bin"
                        reason = "ok"

                    if reason == "no_permission":
                        st.warning("🚫 You don't have permission to view this CV.")
                    elif reason == "not_found":
                        st.info("No CV uploaded yet.")
                    elif cv_bytes:
                        st.download_button(
                            "Download CV",
                            data=cv_bytes,
                            file_name=cv_name or f"{candidate_code}_cv.bin",
                            mime=mime_type or "application/octet-stream",
                            key=f"cand_dlcv_{candidate_code}",
                        )
                        if (mime_type == "application/pdf") or (
                                mime_type is None and (cv_name or "").lower().endswith(".pdf")):
                            b64 = base64.b64encode(cv_bytes).decode("utf-8")
                            st.markdown(
                                f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="600"></iframe>',
                                unsafe_allow_html=True,
                            )
                except Exception as e:
                    st.error(f"Error fetching CV: {e}")

                # Allow editing only if permitted
                if rec.get("can_edit", False):
                    st.success("Editing is enabled for your application.")

                    with st.form("edit_candidate_form"):
                        # Similar form structure for editing
                        name = st.text_input("Full Name *", value=existing_form.get("name", ""))
                        email = st.text_input("Email *", value=existing_form.get("email", ""))
                        phone = st.text_input("Phone *", value=existing_form.get("phone", ""))
                        current_address = st.text_area("Current Address *",
                                                       value=existing_form.get("current_address", ""))
                        permanent_address = st.text_area("Permanent Address *",
                                                         value=existing_form.get("permanent_address", ""))

                        # DOB for editing
                        dob_default = None
                        if existing_form.get("dob"):
                            try:
                                dob_default = datetime.fromisoformat(existing_form["dob"]).date()
                            except:
                                pass

                        if dob_default:
                            dob = st.date_input("Date of Birth *", value=dob_default)
                        else:
                            dob = st.date_input("Date of Birth *")

                        caste = st.text_input("Caste", value=existing_form.get("caste", ""))
                        sub_caste = st.text_input("Sub-caste", value=existing_form.get("sub_caste", ""))

                        marital_options = ["Single", "Married", "Divorced", "Widowed", "Prefer not to say"]
                        marital_index = 0
                        if existing_form.get("marital_status") in marital_options:
                            marital_index = marital_options.index(existing_form["marital_status"])
                        marital_status = st.selectbox("Marital Status", options=marital_options, index=marital_index)

                        highest_qualification = st.text_input("Highest Qualification *",
                                                              value=existing_form.get("highest_qualification", ""))
                        work_experience = st.text_area("Work Experience *",
                                                       value=existing_form.get("work_experience", ""))
                        referral = st.text_input("Referral *", value=existing_form.get("referral", ""))

                        festivals_index = 1 if existing_form.get("ready_festivals") == "Yes" else 0
                        ready_festivals = st.selectbox("Ready to work on festivals?", options=["No", "Yes"],
                                                       index=festivals_index)

                        nights_index = 1 if existing_form.get("ready_late_nights") == "Yes" else 0
                        ready_late_nights = st.selectbox("Ready to work late nights?", options=["No", "Yes"],
                                                         index=nights_index)

                        save_changes = st.form_submit_button("Save Changes")

                        if save_changes:
                            updated_data = {
                                "name": name.strip(),
                                "email": email.strip(),
                                "phone": "".join(filter(str.isdigit, phone)),
                                "current_address": current_address.strip(),
                                "permanent_address": permanent_address.strip(),
                                "dob": dob.isoformat() if isinstance(dob, date) else None,
                                "caste": caste.strip(),
                                "sub_caste": sub_caste.strip(),
                                "marital_status": marital_status,
                                "highest_qualification": highest_qualification.strip(),
                                "work_experience": work_experience.strip(),
                                "referral": referral.strip(),
                                "ready_festivals": "Yes" if ready_festivals == "Yes" else "No",
                                "ready_late_nights": "Yes" if ready_late_nights == "Yes" else "No",
                                "updated_at": datetime.utcnow().isoformat(),
                            }

                            ok = update_candidate_form_data(candidate_code.strip(), updated_data)
                            if ok:
                                st.success("Your application has been updated.")
                            else:
                                st.error("Failed to update your application.")


# Backward-compatible wrapper
def candidate_view():
    candidate_form_view()