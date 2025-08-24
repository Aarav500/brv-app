# candidate_view.py
import json
import secrets
import string
from datetime import datetime
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

    initial_name = data.get("name") or data.get("full_name") or ""

    # Basics
    name = st.text_input("Full Name", value=initial_name)
    email = st.text_input("Email", value=data.get("email", ""))
    phone = st.text_input("Phone", value=data.get("phone", ""))

    # Addresses
    current_address = st.text_area("Current Address", value=data.get("current_address", "") or data.get("address", ""))
    permanent_address = st.text_area("Permanent Address", value=data.get("permanent_address", ""))

    # Personal details
    col1, col2, col3 = st.columns(3)
    with col1:
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
                    dob_default = None
        dob = st.date_input("Date of Birth", value=dob_default)
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
        highest_qualification = st.text_input("Highest Qualification", value=data.get("highest_qualification", ""))

    # Work & referral
    work_experience = st.text_area("Work Experience (years/summary)", value=data.get("work_experience", ""))
    referral = st.text_input("Referral (if any)", value=data.get("referral", ""))

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

    # Resume upload (MANDATORY now)
    uploaded_cv = st.file_uploader(
        "Upload Your Resume (PDF/DOC/DOCX preferred) — REQUIRED",
        type=["pdf", "doc", "docx"],
        key="new_candidate_cv"
    )

    return _safe_json({
        "name": name.strip(),
        "email": email.strip(),
        "phone": phone.strip(),
        "current_address": current_address.strip(),
        "permanent_address": permanent_address.strip(),
        "dob": dob.isoformat() if dob else None,
        "caste": caste.strip(),
        "sub_caste": sub_caste.strip(),
        "marital_status": marital_status,
        "highest_qualification": highest_qualification.strip(),
        "work_experience": work_experience.strip(),
        "referral": referral.strip(),
        "ready_festivals": "Yes" if ready_festivals == "Yes" else "No",
        "ready_late_nights": "Yes" if ready_late_nights == "Yes" else "No",
        "uploaded_cv": uploaded_cv,
        "updated_at": datetime.utcnow().isoformat(),
    })


def _cv_uploader(candidate_id: str):
    st.markdown("### Upload/Replace CV")
    file = st.file_uploader("Upload CV (PDF or DOC/DOCX preferred)", type=["pdf", "doc", "docx"], key=f"cv_{candidate_id}")
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

        # Normalize phone
        form_data["phone"] = "".join(filter(str.isdigit, form_data.get("phone", ""))).strip()
        form_data["name"] = form_data.get("name", "").strip()

        # Validate required fields
        missing_fields = []
        required_fields = {
            "Full Name": form_data.get("name"),
            "Email": form_data.get("email"),
            "Phone": form_data.get("phone"),
            "Date of Birth": form_data.get("dob"),
            "Current Address": form_data.get("current_address"),
            "Permanent Address": form_data.get("permanent_address"),
            "Highest Qualification": form_data.get("highest_qualification"),
            "Work Experience": form_data.get("work_experience"),
            "Referral": form_data.get("referral"),
            "CV": form_data.get("uploaded_cv"),
        }

        for label, value in required_fields.items():
            if not value or (isinstance(value, str) and not value.strip()):
                missing_fields.append(label)

        if form_data["phone"] and len(form_data["phone"]) < 10:
            st.error("⚠️ Please enter a valid 10-digit phone number.")
            st.stop()

        if st.button("Submit Application"):
            if missing_fields:
                st.error(f"Please fill in the following required fields: {', '.join(missing_fields)}")
                st.stop()

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

                # Save CV (mandatory, so guaranteed present)
                file = form_data["uploaded_cv"]
                file_bytes = file.read()
                ok = save_candidate_cv(candidate_id, file_bytes, file.name)
                if ok:
                    st.success("📄 CV uploaded successfully.")
                else:
                    st.error("⚠️ Failed to save CV.")

    else:
        st.caption("Enter your candidate code to view and edit your application (if permission is granted).")
        candidate_code = st.text_input("Candidate Code", key="cand_code")

        if candidate_code.strip():
            rec = get_candidate_by_id(candidate_code.strip())
            if not rec:
                st.error("No record found for the provided code.")
            else:
                existing_form = rec.get("form_data") or {}
                st.info(f"Welcome back, {rec.get('name','Candidate')}")

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
                        st.warning("🚫 You don’t have permission to view this CV.")
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
                        if (mime_type == "application/pdf") or (mime_type is None and (cv_name or "").lower().endswith(".pdf")):
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
