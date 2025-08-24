# candidate_view.py (full version with strict required fields, email+phone uniqueness, and email sending)
# ------------------------------------------------------------------------------------
# This file renders the Candidate Pre-Interview application flow in Streamlit.
# It provides:
#   • New Candidate submission with strict validation:
#       - Required fields: Full Name, Email, Phone, Date of Birth, Current Address,
#                          Permanent Address, Highest Qualification, Work Experience,
#                          Referral, CV
#       - One application per Email AND per Phone (duplicate prevention)
#       - Candidate code generation + email delivery via smtp_mailer.send_email
#   • Returning Candidate section:
#       - View application by candidate code
#       - Upload/Replace CV, secure fetch + inline PDF preview
#       - If allowed (can_edit), edit application with validation
#   • Session-state preservation of in-progress form inputs
#   • Small quality-of-life helpers (summary sidebar, clear error list, etc.)
#
# Notes:
#   - This module relies on the following functions from db_postgres:
#       create_candidate_in_db, update_candidate_form_data, get_candidate_by_id,
#       save_candidate_cv, get_candidate_cv_secure, get_all_candidates
#   - Email is sent with smtp_mailer.send_email(to_email, subject, text, html=None)
#   - No changes required in smtp_mailer.py
# ------------------------------------------------------------------------------------

import json
import secrets
import string
from datetime import datetime, date
from typing import Any, Dict, Optional, List, Tuple

import streamlit as st
import base64

# DB glue
from db_postgres import (
    create_candidate_in_db,
    update_candidate_form_data,
    get_candidate_by_id,
    save_candidate_cv,
    get_candidate_cv_secure,
    get_all_candidates,
)

# ------------------------------------------------------------------------------
# CONFIG / CONSTANTS
# ------------------------------------------------------------------------------

APP_TITLE = "Candidate — Pre-Interview Application"
REQUIRED_NOTE = "Fields marked with * are required."
PHONE_MIN_DIGITS = 10
DOB_MIN = date(1950, 1, 1)
DOB_MAX = date.today()

MARITAL_OPTIONS = ["Single", "Married", "Divorced", "Widowed", "Prefer not to say"]

# Toggle for debugging helpers (prints)
DEBUG = False

# ------------------------------------------------------------------------------
# UTILS
# ------------------------------------------------------------------------------

def _gen_candidate_code(prefix: str = "BRV") -> str:
    """Generate a short unique candidate code."""
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(chars) for _ in range(6))
    return f"{prefix}-{suffix}"


def _safe_json(o: Any) -> Any:
    """Return JSON-serializable object; if not serializable, return {}."""
    try:
        json.dumps(o)
        return o
    except Exception:
        return {}


def _normalize_phone(raw: str) -> str:
    """Strip to digits only."""
    if not raw:
        return ""
    return "".join(filter(str.isdigit, raw))


def _valid_email(email: str) -> bool:
    """Very lightweight email validation without external libs."""
    if not email or "@" not in email:
        return False
    local, _, domain = email.partition("@")
    if not local or not domain or "." not in domain:
        return False
    # Avoid spaces and obvious invalid chars
    if " " in email or ".." in email:
        return False
    return True


def _debug(msg: str):
    if DEBUG:
        st.write(f"DEBUG: {msg}")


def _dup_exists(email: str, phone: str) -> Tuple[bool, Optional[str]]:
    """
    Check duplicates by email OR phone using get_all_candidates().
    Returns (exists, reason) where reason is "email" or "phone".
    """
    try:
        records = get_all_candidates() or []
    except Exception as e:
        # If DB helper fails, we surface but still allow form to continue;
        # however, safer to block create to avoid accidental duplicates.
        st.error(f"Error fetching candidates for duplicate check: {e}")
        return True, "db_error"

    email_lower = (email or "").strip().lower()
    phone_norm = (phone or "").strip()
    for c in records:
        # DB may store under top-level or within form_data
        c_email = (c.get("email") or (c.get("form_data") or {}).get("email") or "").strip().lower()
        c_phone = (c.get("phone") or (c.get("form_data") or {}).get("phone") or "").strip()
        if c_email and c_email == email_lower:
            return True, "email"
        if c_phone and c_phone == phone_norm:
            return True, "phone"
    return False, None


def _cv_uploader(candidate_id: str):
    """Reusable CV upload block for returning candidates."""
    st.markdown("### Upload/Replace CV")
    file = st.file_uploader(
        "Upload CV (PDF or DOC/DOCX preferred)",
        type=["pdf", "doc", "docx"],
        key=f"cv_{candidate_id}",
    )
    if file is not None:
        file_bytes = file.read()
        ok = save_candidate_cv(candidate_id, file_bytes, file.name)
        if ok:
            st.success("CV saved.")
        else:
            st.error("Failed to save CV.")


def _render_pdf_inline(cv_bytes: bytes):
    """Renders PDF (bytes) inline in an iframe for preview."""
    b64 = base64.b64encode(cv_bytes).decode("utf-8")
    st.markdown(
        f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="600"></iframe>',
        unsafe_allow_html=True,
    )


def _send_candidate_code_email(to_email: str, candidate_id: str) -> bool:
    """
    Sends the candidate code using smtp_mailer.send_email(to_email, subject, text, html=None).
    Returns True if send completed, else False.
    """
    try:
        from smtp_mailer import send_email

        body_text = f"""Hello,

Your candidate code is: {candidate_id}

Use this code to view/update your application if permitted.

Thanks,
BRV Recruitment
"""
        body_html = f"""
<p>Hello,</p>
<p>Your candidate code is: <b>{candidate_id}</b></p>
<p>Use this code to view/update your application if permitted.</p>
<p>Thanks,<br>BRV Recruitment</p>
"""

        send_email(
            to_email=to_email,
            subject="Your Candidate Code",
            text=body_text,
            html=body_html,
        )
        return True
    except Exception as e:
        st.warning(f"Email failed: {e}. Please note your code above.")
        return False


def _required_error_list(errors: List[str]):
    """Pretty print a vertical list of validation errors."""
    if not errors:
        return
    st.error("Please fix the following issues before submitting:")
    for e in errors:
        st.error(e)


def _summary_sidebar(form_data: Dict[str, Any]):
    """
    Display a small, read-only summary of the current inputs in the sidebar
    so candidates can double-check before submitting.
    """
    with st.sidebar:
        st.markdown("### Your Input Summary")
        st.caption("Review your details before submitting.")
        st.write(f"**Full Name:** {form_data.get('name', '') or '—'}")
        st.write(f"**Email:** {form_data.get('email', '') or '—'}")
        st.write(f"**Phone:** {form_data.get('phone', '') or '—'}")
        st.write(f"**DOB:** {form_data.get('dob', '') or '—'}")
        st.write(f"**Current Address:** {form_data.get('current_address', '') or '—'}")
        st.write(f"**Permanent Address:** {form_data.get('permanent_address', '') or '—'}")
        st.write(f"**Qualification:** {form_data.get('highest_qualification', '') or '—'}")
        st.write(f"**Work Experience:** {form_data.get('work_experience', '') or '—'}")
        st.write(f"**Referral:** {form_data.get('referral', '') or '—'}")


# ------------------------------------------------------------------------------
# FORM RENDERERS
# ------------------------------------------------------------------------------

def _render_new_candidate_form():
    """
    Render the New Candidate form inside a st.form. Handles:
      - Session-state persistence
      - Validation
      - Duplicate check
      - Record creation
      - CV upload
      - Email with candidate code
    """
    st.subheader("Pre-Interview Form")
    st.info(REQUIRED_NOTE)

    with st.form("candidate_form", clear_on_submit=False):
        # Initialize session state storage for in-progress form values
        if "form_data" not in st.session_state:
            st.session_state.form_data = {}

        initial = st.session_state.form_data

        # Basic Info
        name = st.text_input("Full Name *", value=initial.get("name", ""), help="Required field")
        email = st.text_input("Email *", value=initial.get("email", ""), help="Required field")
        phone = st.text_input("Phone *", value=initial.get("phone", ""), help="Required field - 10 digits minimum")

        # Addresses
        current_address = st.text_area(
            "Current Address *", value=initial.get("current_address", ""), help="Required field"
        )
        permanent_address = st.text_area(
            "Permanent Address *", value=initial.get("permanent_address", ""), help="Required field"
        )

        # Personal details row
        col1, col2, col3 = st.columns(3)
        with col1:
            # DOB
            dob_default = None
            if initial.get("dob"):
                try:
                    dob_default = datetime.fromisoformat(initial["dob"]).date()
                except Exception:
                    dob_default = None

            if dob_default:
                dob = st.date_input(
                    "Date of Birth *",
                    value=dob_default,
                    min_value=DOB_MIN,
                    max_value=DOB_MAX,
                    help="Required field",
                )
            else:
                dob = st.date_input(
                    "Date of Birth *",
                    min_value=DOB_MIN,
                    max_value=DOB_MAX,
                    help="Required field - Please select your date of birth",
                )

        with col2:
            caste = st.text_input("Caste", value=initial.get("caste", ""))

        with col3:
            sub_caste = st.text_input("Sub-caste", value=initial.get("sub_caste", ""))

        # Marital + Education
        col4, col5 = st.columns(2)
        with col4:
            m_index = MARITAL_OPTIONS.index(initial["marital_status"]) if initial.get("marital_status") in MARITAL_OPTIONS else 0
            marital_status = st.selectbox("Marital Status", options=MARITAL_OPTIONS, index=m_index)
        with col5:
            highest_qualification = st.text_input(
                "Highest Qualification *",
                value=initial.get("highest_qualification", ""),
                help="Required field",
            )

        # Work + Referral
        work_experience = st.text_area(
            "Work Experience (years/summary) *",
            value=initial.get("work_experience", ""),
            help="Required field - Describe your work experience",
        )
        referral = st.text_input(
            "Referral (if any) *",
            value=initial.get("referral", ""),
            help="Required field - How did you hear about us?",
        )

        # Availability
        col6, col7 = st.columns(2)
        with col6:
            festivals_index = 1 if initial.get("ready_festivals") == "Yes" else 0
            ready_festivals = st.selectbox(
                "Ready to work on festivals and national holidays?",
                options=["No", "Yes"],
                index=festivals_index,
            )
        with col7:
            nights_index = 1 if initial.get("ready_late_nights") == "Yes" else 0
            ready_late_nights = st.selectbox(
                "Ready to work late nights if needed?",
                options=["No", "Yes"],
                index=nights_index,
            )

        # CV
        st.markdown("### CV Upload *")
        uploaded_cv = st.file_uploader(
            "Upload Your Resume (PDF/DOC/DOCX preferred) — REQUIRED",
            type=["pdf", "doc", "docx"],
            help="This is a required field. Please upload your CV.",
        )

        submitted = st.form_submit_button("Submit Application", type="primary")

        # On submit, collect + validate
        if submitted:
            form_data = {
                "name": (name or "").strip(),
                "email": (email or "").strip(),
                "phone": _normalize_phone(phone),
                "current_address": (current_address or "").strip(),
                "permanent_address": (permanent_address or "").strip(),
                "dob": dob.isoformat() if isinstance(dob, date) else None,
                "caste": (caste or "").strip(),
                "sub_caste": (sub_caste or "").strip(),
                "marital_status": marital_status,
                "highest_qualification": (highest_qualification or "").strip(),
                "work_experience": (work_experience or "").strip(),
                "referral": (referral or "").strip(),
                "ready_festivals": "Yes" if ready_festivals == "Yes" else "No",
                "ready_late_nights": "Yes" if ready_late_nights == "Yes" else "No",
                "uploaded_cv": uploaded_cv,
                "updated_at": datetime.utcnow().isoformat(),
            }

            # Persist to session so user doesn't lose work on validation errors
            st.session_state.form_data = form_data

            # Show a quick summary in the sidebar
            _summary_sidebar(form_data)

            # Validation
            errors: List[str] = []

            if not form_data["name"]:
                errors.append("• Full Name is required")

            if not _valid_email(form_data["email"]):
                errors.append("• Please enter a valid Email address")

            if not form_data["phone"]:
                errors.append("• Phone number is required")
            elif len(form_data["phone"]) < PHONE_MIN_DIGITS:
                errors.append(f"• Phone number must be at least {PHONE_MIN_DIGITS} digits")

            if not form_data["dob"]:
                errors.append("• Date of Birth is required")

            if not form_data["current_address"]:
                errors.append("• Current Address is required")

            if not form_data["permanent_address"]:
                errors.append("• Permanent Address is required")

            if not form_data["highest_qualification"]:
                errors.append("• Highest Qualification is required")

            if not form_data["work_experience"]:
                errors.append("• Work Experience is required")

            if not form_data["referral"]:
                errors.append("• Referral is required")

            if not form_data["uploaded_cv"]:
                errors.append("• CV upload is required")

            # Duplicate check (email/phone)
            if not errors:
                exists, reason = _dup_exists(form_data["email"], form_data["phone"])
                if exists:
                    if reason == "email":
                        errors.append("• An application with this email already exists.")
                    elif reason == "phone":
                        errors.append("• An application with this phone number already exists.")
                    else:
                        errors.append("• Unable to verify duplicates due to a database error. Please try again.")

            if errors:
                _required_error_list(errors)
                return

            # Create record
            candidate_id = _gen_candidate_code()
            record = create_candidate_in_db(
                candidate_id=candidate_id,
                name=form_data["name"],
                address=form_data["current_address"],
                dob=form_data["dob"],
                caste=form_data["caste"],
                email=form_data["email"],
                phone=form_data["phone"],
                form_data=_safe_json(form_data),
                created_by="candidate",
            )

            if not record:
                st.error("Failed to create candidate record. Please try again.")
                return

            # Success UI
            st.success(f"✅ Application submitted! Your candidate code is: **{candidate_id}**")

            # Helpful copy widget for the code
            st.text_input("Copy your candidate code:", value=candidate_id, key="copy_code", help="Copy this code and keep it safe.")

            # Try emailing the code
            sent = _send_candidate_code_email(form_data["email"], candidate_id)
            if sent:
                st.info("📧 Candidate code has also been emailed to you.")

            # Save CV now
            cv_file = form_data.get("uploaded_cv")
            if cv_file:
                try:
                    file_bytes = cv_file.read()
                except Exception:
                    # Streamlit file-like objects can be re-read once; if None, ask re-upload
                    file_bytes = None

                if file_bytes:
                    ok = save_candidate_cv(candidate_id, file_bytes, cv_file.name)
                    if ok:
                        st.success("📄 CV uploaded successfully.")
                    else:
                        st.error("⚠️ Failed to save CV.")
                else:
                    st.warning("CV file stream not available; please re-upload from Returning Candidate section if needed.")

            # Optional: Offer a quick "Resend Email" button
            with st.expander("Need the email again?"):
                if st.button("Resend Candidate Code"):
                    if _send_candidate_code_email(form_data["email"], candidate_id):
                        st.success("Email re-sent successfully.")

            # Clear form data and rerun so the form resets cleanly
            st.session_state.form_data = {}
            st.rerun()


def _render_returning_candidate():
    """
    Render the Returning Candidate view:
      - Enter candidate code
      - View basic record
      - CV upload + secure fetch + PDF inline
      - If can_edit: edit with validation and save
    """
    st.caption("Enter your candidate code to view and edit your application (if permission is granted).")
    candidate_code = st.text_input("Candidate Code", key="cand_code")

    if not candidate_code.strip():
        return

    rec = get_candidate_by_id(candidate_code.strip())
    if not rec:
        st.error("No record found for the provided code.")
        return

    existing_form = rec.get("form_data") or {}
    st.info(f"Welcome back, {rec.get('name', 'Candidate')}")

    # Identity / actor for secure CV fetch
    try:
        from auth import get_current_user
        user = get_current_user()
        actor_id = (user.get("id") if user else 0)
    except Exception:
        actor_id = 0

    # Always allow CV upload
    _cv_uploader(candidate_code.strip())

    # Secure CV fetch + preview
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
                mime_type is None and (cv_name or "").lower().endswith(".pdf")
            ):
                _render_pdf_inline(cv_bytes)
    except Exception as e:
        st.error(f"Error fetching CV: {e}")

    # Allow editing only if permitted
    if not rec.get("can_edit", False):
        st.info("Editing is not enabled for your application at this time.")
        return

    st.success("Editing is enabled for your application.")

    with st.form("edit_candidate_form"):
        # Editable fields mirror the required ones
        name = st.text_input("Full Name *", value=existing_form.get("name", ""))
        email = st.text_input("Email *", value=existing_form.get("email", ""))
        phone = st.text_input("Phone *", value=existing_form.get("phone", ""))
        current_address = st.text_area("Current Address *", value=existing_form.get("current_address", ""))
        permanent_address = st.text_area("Permanent Address *", value=existing_form.get("permanent_address", ""))

        # DOB
        dob_default = None
        if existing_form.get("dob"):
            try:
                dob_default = datetime.fromisoformat(existing_form["dob"]).date()
            except Exception:
                dob_default = None
        dob = st.date_input("Date of Birth *", value=dob_default or date(1990, 1, 1), min_value=DOB_MIN, max_value=DOB_MAX)

        caste = st.text_input("Caste", value=existing_form.get("caste", ""))
        sub_caste = st.text_input("Sub-caste", value=existing_form.get("sub_caste", ""))

        m_index = MARITAL_OPTIONS.index(existing_form["marital_status"]) if existing_form.get("marital_status") in MARITAL_OPTIONS else 0
        marital_status = st.selectbox("Marital Status", options=MARITAL_OPTIONS, index=m_index)

        highest_qualification = st.text_input("Highest Qualification *", value=existing_form.get("highest_qualification", ""))
        work_experience = st.text_area("Work Experience *", value=existing_form.get("work_experience", ""))
        referral = st.text_input("Referral *", value=existing_form.get("referral", ""))

        festivals_index = 1 if existing_form.get("ready_festivals") == "Yes" else 0
        ready_festivals = st.selectbox("Ready to work on festivals?", options=["No", "Yes"], index=festivals_index)

        nights_index = 1 if existing_form.get("ready_late_nights") == "Yes" else 0
        ready_late_nights = st.selectbox("Ready to work late nights?", options=["No", "Yes"], index=nights_index)

        save_changes = st.form_submit_button("Save Changes")

        if save_changes:
            # Validate edits (same required set as create, except CV which is not re-required here)
            errors: List[str] = []

            name_v = (name or "").strip()
            email_v = (email or "").strip()
            phone_v = _normalize_phone(phone)
            current_address_v = (current_address or "").strip()
            permanent_address_v = (permanent_address or "").strip()
            dob_v = dob.isoformat() if isinstance(dob, date) else None
            qual_v = (highest_qualification or "").strip()
            work_v = (work_experience or "").strip()
            ref_v = (referral or "").strip()

            if not name_v:
                errors.append("• Full Name is required")
            if not _valid_email(email_v):
                errors.append("• Please enter a valid Email address")
            if not phone_v or len(phone_v) < PHONE_MIN_DIGITS:
                errors.append(f"• Phone number must be at least {PHONE_MIN_DIGITS} digits")
            if not dob_v:
                errors.append("• Date of Birth is required")
            if not current_address_v:
                errors.append("• Current Address is required")
            if not permanent_address_v:
                errors.append("• Permanent Address is required")
            if not qual_v:
                errors.append("• Highest Qualification is required")
            if not work_v:
                errors.append("• Work Experience is required")
            if not ref_v:
                errors.append("• Referral is required")

            if errors:
                _required_error_list(errors)
                return

            updated_data = {
                "name": name_v,
                "email": email_v,
                "phone": phone_v,
                "current_address": current_address_v,
                "permanent_address": permanent_address_v,
                "dob": dob_v,
                "caste": (caste or "").strip(),
                "sub_caste": (sub_caste or "").strip(),
                "marital_status": marital_status,
                "highest_qualification": qual_v,
                "work_experience": work_v,
                "referral": ref_v,
                "ready_festivals": "Yes" if ready_festivals == "Yes" else "No",
                "ready_late_nights": "Yes" if ready_late_nights == "Yes" else "No",
                "updated_at": datetime.utcnow().isoformat(),
            }

            ok = update_candidate_form_data(candidate_code.strip(), updated_data)
            if ok:
                st.success("Your application has been updated.")
            else:
                st.error("Failed to update your application.")


# ------------------------------------------------------------------------------
# PUBLIC ENTRYPOINTS
# ------------------------------------------------------------------------------

def candidate_form_view():
    """Top-level renderer; choose New vs Returning mode."""
    st.header(APP_TITLE)
    mode = st.radio("I am a…", ["New candidate", "Returning candidate"], horizontal=True)

    if mode == "New candidate":
        _render_new_candidate_form()
    else:
        _render_returning_candidate()


# Backward-compatible wrapper (if older imports expect candidate_view)
def candidate_view():
    candidate_form_view()
