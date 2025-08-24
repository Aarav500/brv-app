# candidate_view.py (final patched validation with debugging)
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


# ------------------------------
# Pre-interview fields (with CV uploader included)
# ------------------------------
def _pre_interview_fields(initial: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = initial or {}
    st.subheader("Pre-Interview Form")

    # Add a note about required fields
    st.info("Fields marked with * are required")

    initial_name = data.get("name") or data.get("full_name") or ""

    # Basics with required indicators
    name = st.text_input("Full Name *", value=initial_name, help="Required field")
    email = st.text_input("Email *", value=data.get("email", ""), help="Required field")
    phone = st.text_input("Phone *", value=data.get("phone", ""), help="Required field - 10 digits minimum")

    # Addresses with required indicators
    current_address = st.text_area("Current Address *",
                                   value=data.get("current_address", "") or data.get("address", ""),
                                   help="Required field")
    permanent_address = st.text_area("Permanent Address *",
                                     value=data.get("permanent_address", ""),
                                     help="Required field")

    # Personal details
    col1, col2, col3 = st.columns(3)
    with col1:
        # DOB handling - always require explicit selection
        dob_default = None
        dob_raw = data.get("dob") or data.get("date_of_birth")

        if dob_raw:
            try:
                from datetime import datetime as _dt
                dob_default = _dt.fromisoformat(dob_raw).date()
            except Exception:
                try:
                    from datetime import datetime as _dt
                    dob_default = _dt.strptime(dob_raw, "%Y-%m-%d").date()
                except Exception:
                    pass

        # For new forms, don't set a default - let user pick
        if not initial:  # This is a new form
            dob = st.date_input("Date of Birth *",
                                min_value=date(1950, 1, 1),
                                max_value=date.today(),
                                help="Required field - Please select your date of birth")
        else:  # Editing existing form
            dob = st.date_input("Date of Birth *",
                                value=dob_default or date(1990, 1, 1),
                                min_value=date(1950, 1, 1),
                                max_value=date.today(),
                                help="Required field")

    with col2:
        caste = st.text_input("Caste", value=data.get("caste", ""))
    with col3:
        sub_caste = st.text_input("Sub-caste", value=data.get("sub_caste", ""))

    # Marital status & education
    col4, col5 = st.columns(2)
    with col4:
        marital_options = ["Single", "Married", "Divorced", "Widowed", "Prefer not to say"]
        m_index = marital_options.index(data["marital_status"]) if data.get("marital_status") in marital_options else 0
        marital_status = st.selectbox("Marital Status", options=marital_options, index=m_index)
    with col5:
        highest_qualification = st.text_input("Highest Qualification *",
                                              value=data.get("highest_qualification", ""),
                                              help="Required field")

    # Work & referral with required indicators
    work_experience = st.text_area("Work Experience (years/summary) *",
                                   value=data.get("work_experience", ""),
                                   help="Required field - Describe your work experience")
    referral = st.text_input("Referral (if any) *",
                             value=data.get("referral", ""),
                             help="Required field - How did you hear about us?")

    # Availability
    col6, col7 = st.columns(2)
    with col6:
        ready_festivals = st.selectbox(
            "Ready to work on festivals and national holidays?",
            options=["No", "Yes"],
            index=1 if str(data.get("ready_festivals", "")).lower() == "yes" else 0
        )
    with col7:
        ready_late_nights = st.selectbox(
            "Ready to work late nights if needed?",
            options=["No", "Yes"],
            index=1 if str(data.get("ready_late_nights", "")).lower() == "yes" else 0
        )

    # Resume upload with clear requirement
    st.markdown("### CV Upload *")
    uploaded_cv = st.file_uploader(
        "Upload Your Resume (PDF/DOC/DOCX preferred) — REQUIRED",
        type=["pdf", "doc", "docx"],
        key="new_candidate_cv",
        help="This is a required field. Please upload your CV in PDF, DOC, or DOCX format."
    )

    # Handle DOB value - only set if user actually selected something
    dob_value = None
    if isinstance(dob, date):
        # For new forms, only accept if it's not today's date (unless explicitly chosen)
        if initial or dob != date.today():
            dob_value = dob.isoformat()
        elif not initial and dob != date.today():
            dob_value = dob.isoformat()

    form_data = {
        "name": name.strip() if name else "",
        "email": email.strip() if email else "",
        "phone": phone.strip() if phone else "",
        "current_address": current_address.strip() if current_address else "",
        "permanent_address": permanent_address.strip() if permanent_address else "",
        "dob": dob_value,
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

    return _safe_json(form_data)


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
        form_data = _pre_interview_fields()
        st.markdown("---")

        # Debug: Show what data we captured (remove this in production)
        with st.expander("Debug: Form Data Captured", expanded=False):
            st.json(form_data)

        # Normalize phone
        if form_data.get("phone"):
            form_data["phone"] = "".join(filter(str.isdigit, form_data.get("phone", ""))).strip()

        if st.button("Submit Application", type="primary"):
            # Enhanced validation with specific error messages
            validation_errors = []

            # Debug each field
            st.write("Debugging validation:")

            # Name validation
            name_val = form_data.get("name", "").strip()
            st.write(f"Name: '{name_val}' (length: {len(name_val)})")
            if not name_val:
                validation_errors.append("• Full Name is required")

            # Email validation
            email_val = form_data.get("email", "").strip()
            st.write(f"Email: '{email_val}' (length: {len(email_val)})")
            if not email_val:
                validation_errors.append("• Email is required")
            elif "@" not in email_val or "." not in email_val.split("@")[-1]:
                validation_errors.append("• Please enter a valid email address")

            # Phone validation
            phone_val = form_data.get("phone", "")
            st.write(f"Phone: '{phone_val}' (length: {len(phone_val)})")
            if not phone_val:
                validation_errors.append("• Phone number is required")
            elif len(phone_val) < 10:
                validation_errors.append("• Phone number must be at least 10 digits")

            # DOB validation
            dob_val = form_data.get("dob")
            st.write(f"DOB: '{dob_val}'")
            if not dob_val:
                validation_errors.append("• Date of Birth is required")

            # Address validation
            curr_addr = form_data.get("current_address", "").strip()
            st.write(f"Current Address: '{curr_addr}' (length: {len(curr_addr)})")
            if not curr_addr:
                validation_errors.append("• Current Address is required")

            perm_addr = form_data.get("permanent_address", "").strip()
            st.write(f"Permanent Address: '{perm_addr}' (length: {len(perm_addr)})")
            if not perm_addr:
                validation_errors.append("• Permanent Address is required")

            # Qualification validation
            qual_val = form_data.get("highest_qualification", "").strip()
            st.write(f"Qualification: '{qual_val}' (length: {len(qual_val)})")
            if not qual_val:
                validation_errors.append("• Highest Qualification is required")

            # Work experience validation
            work_val = form_data.get("work_experience", "").strip()
            st.write(f"Work Experience: '{work_val}' (length: {len(work_val)})")
            if not work_val:
                validation_errors.append("• Work Experience is required")

            # Referral validation
            ref_val = form_data.get("referral", "").strip()
            st.write(f"Referral: '{ref_val}' (length: {len(ref_val)})")
            if not ref_val:
                validation_errors.append("• Referral information is required")

            # CV validation
            cv_val = form_data.get("uploaded_cv")
            st.write(f"CV: {cv_val}")
            if cv_val is None:
                validation_errors.append("• CV upload is required")

            # Display all validation errors at once
            if validation_errors:
                st.error("Please fix the following issues before submitting:")
                for error in validation_errors:
                    st.error(error)
                st.stop()

            # If validation passes, create the record
            candidate_id = _gen_candidate_code()
            rec = create_candidate_in_db(
                candidate_id=candidate_id,
                name=form_data.get("name", ""),
                address=form_data.get("current_address", ""),
                dob=form_data.get("dob", None),
                caste=form_data.get("caste", ""),
                email=form_data.get("email", ""),
                phone=form_data.get("phone", ""),
                form_data=form_data,
                created_by="candidate",
            )

            if rec:
                st.success(f"✅ Application submitted! Your candidate code is: **{candidate_id}**")

                # Save CV
                file = form_data["uploaded_cv"]
                if file:
                    file.seek(0)  # Reset file pointer
                    file_bytes = file.read()
                    ok = save_candidate_cv(candidate_id, file_bytes, file.name)
                    if ok:
                        st.success("📄 CV uploaded successfully.")
                    else:
                        st.error("⚠️ Failed to save CV.")
            else:
                st.error("Failed to create candidate record. Please try again.")

    else:
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
                    updated = _pre_interview_fields(initial=existing_form)
                    if st.button("Save Changes"):
                        ok = update_candidate_form_data(candidate_code.strip(), updated)
                        if ok:
                            st.success("Your application has been updated.")
                        else:
                            st.error("Failed to update your application.")


# Backward-compatible wrapper
def candidate_view():
    candidate_form_view()