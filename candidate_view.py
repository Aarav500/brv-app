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
    get_candidate_cv_secure,   # ✅ REPLACE
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
# Replace _pre_interview_fields starting at line 36
# ------------------------------
def _pre_interview_fields(initial: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Renders the Pre-Interview form, returning a dict with keys that match the DB layer:
      - name, email, phone
      - current_address (stored as address), permanent_address
      - dob (ISO string)
      - caste, sub_caste, marital_status
      - highest_qualification, work_experience, referral
      - ready_festivals (Yes/No), ready_late_nights (Yes/No)
    NOTE: Accepts older keys in `initial` (e.g. 'full_name') for backwards compatibility.
    """
    data = initial or {}

    st.subheader("Pre-Interview Form")

    # pick up name (backwards-compatible: prefer 'name', fallback to 'full_name')
    initial_name = data.get("name") or data.get("full_name") or ""

    # Basics
    name = st.text_input("Full Name", value=initial_name)
    email = st.text_input("Email", value=data.get("email", ""))
    phone = st.text_input("Phone", value=data.get("phone", ""))

    # Addresses
    current_address = st.text_area("Current Address", value=data.get("current_address", "") or data.get("address",""))
    permanent_address = st.text_area("Permanent Address", value=data.get("permanent_address", ""))

    # Personal details
    col1, col2, col3 = st.columns(3)
    with col1:
        # parse DOB if necessary to a date object for st.date_input
        dob_default = None
        dob_raw = data.get("dob") or data.get("date_of_birth")
        if dob_raw:
            try:
                # handle isoformat / yyyy-mm-dd strings
                from datetime import datetime as _dt
                dob_default = _dt.fromisoformat(dob_raw).date()
            except Exception:
                try:
                    # fallback: parse date-only
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
        m_index = 0
        if data.get("marital_status") in marital_options:
            try:
                m_index = marital_options.index(data["marital_status"])
            except Exception:
                m_index = 0
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
            index=1 if str(data.get("ready_festivals","")).lower() == "yes" else 0
        )
    with col7:
        ready_late_nights = st.selectbox(
            "Ready to work late nights if needed?",
            options=["No", "Yes"],
            index=1 if str(data.get("ready_late_nights","")).lower() == "yes" else 0
        )

    # Build returned dict with keys matching DB update expectations
    form = {
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
        "updated_at": datetime.utcnow().isoformat(),
    }
    return _safe_json(form)

def _cv_uploader(candidate_id: str):
    st.markdown("### Upload/Replace CV")
    file = st.file_uploader("Upload CV (PDF or DOC/DOCX preferred)", type=["pdf", "doc", "docx"])
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
    """
    Main Candidate flow:
      - New candidate: fill Pre-Interview form, system generates candidate code and creates record.
      - Returning candidate: enter code; if candidate has can_edit=True, update form data and upload CV.
    """
    st.header("Candidate — Pre-Interview Application")

    mode = st.radio("I am a…", ["New candidate", "Returning candidate"], horizontal=True)

    if mode == "New candidate":
        form_data = _pre_interview_fields()
        st.markdown("---")
        if st.button("Submit Application"):
            # Basic validations
            if not form_data.get("name") or not form_data.get("phone"):
                st.error("Full Name and Phone are required.")
                return

            candidate_id = _gen_candidate_code()
            rec = create_candidate_in_db(
                candidate_id=candidate_id,
                name=form_data.get("name", ""),
                address=form_data.get("current_address", ""),  # store current as base address column
                dob=form_data.get("dob", None),
                caste=form_data.get("caste", ""),
                email=form_data.get("email", ""),
                phone=form_data.get("phone", ""),
                form_data=form_data,
                created_by="candidate",
            )
            if rec:
                st.success(f"Application submitted. Your candidate code is: **{candidate_id}**")
                st.info("Please save this code to edit or upload your CV later (if permitted).")
                st.markdown("---")
                _cv_uploader(candidate_id)
            else:
                st.error("Failed to create your application. Please try again.")

    else:
        st.caption("Enter your candidate code to view and edit your application (if permission is granted).")
        
        # ---------- candidate_view.py : patched Returning candidate block ----------
        # Note: ensure these imports exist at file top:
        # import base64
        # from db_postgres import get_candidate_by_id, get_candidate_cv_secure, update_candidate_form_data

        def _ensure_candidate_cache():
            if "candidates_cache" not in st.session_state:
                st.session_state.candidates_cache = None
            if "candidate_selected_ids" not in st.session_state:
                st.session_state.candidate_selected_ids = set()
            if "expanded_candidates" not in st.session_state:
                st.session_state.expanded_candidates = set()

        @st.cache_data(ttl=60)
        def _load_all_candidates():
            # replace/get your get_all_candidates() call here
            try:
                return get_all_candidates()
            except Exception:
                return []

        # Use _ensure_candidate_cache() at top of candidate_list UI
        _ensure_candidate_cache()
        # ---------------- Returning candidate logic ----------------
        candidate_code = st.text_input("Candidate Code", key="cand_code")
        if candidate_code.strip():
            rec = get_candidate_by_id(candidate_code.strip())
            if not rec:
                st.error("No record found for the provided code.")
            else:
                # show data
                existing_form = rec.get("form_data") or {}
                st.info(f"Welcome back, {rec.get('name','Candidate')}")
                from auth import get_current_user
                user = get_current_user()
                actor_id = (user.get("id") if user else 0)

                # If editing disabled, show read-only details + uploader + cv preview (permission aware)
                if not rec.get("can_edit", False):
                    st.warning("Editing is currently disabled for your application. You may upload a CV if permitted.")
                    _cv_uploader(candidate_code.strip())

                    # NOTE: DB helper may return 4-tuple (bytes, filename, mime_type, reason)
                    # or older 3-tuple (bytes, filename, reason). Handle both shapes defensively.
                    res = get_candidate_cv_secure(candidate_code.strip(), actor_id)
                    # normalize shapes:
                    file_bytes = filename = mime_type = None
                    reason = "not_found"
                    try:
                        if isinstance(res, tuple) or isinstance(res, list):
                            if len(res) == 4:
                                file_bytes, filename, mime_type, reason = res
                            elif len(res) == 3:
                                # old shape: (bytes, filename, reason)
                                file_bytes, filename, reason = res
                                mime_type = None
                        elif isinstance(res, (bytes, bytearray)):
                            file_bytes = bytes(res)
                            filename = f"{candidate_code}_cv.bin"
                            mime_type = None
                            reason = "ok"
                        else:
                            reason = "not_found"
                    except Exception:
                        reason = "error"

                    if reason == "no_permission":
                        st.warning("🚫 You don’t have permission to view this CV.")
                    elif reason == "not_found":
                        st.info("No CV uploaded yet.")
                    elif file_bytes:
                        st.download_button(
                            "Download CV",
                            data=file_bytes,
                            file_name=filename or f"{candidate_code}_cv.bin",
                            mime=mime_type or "application/octet-stream",
                            key=f"cand_dlcv_{candidate_code}",
                        )
                        # Inline preview for PDF
                        if (mime_type == "application/pdf") or (mime_type is None and (filename or "").lower().endswith(".pdf")):
                            import base64
                            b64 = base64.b64encode(file_bytes).decode("utf-8")
                            st.markdown(
                                f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="600"></iframe>',
                                unsafe_allow_html=True,
                            )
                else:
                    # Editing enabled branch
                    st.success("Editing is enabled for your application.")
                    updated = _pre_interview_fields(initial=existing_form)
                    st.markdown("---")
                    _cv_uploader(candidate_code.strip())

                    if st.button("Save Changes"):
                        ok = update_candidate_form_data(candidate_code.strip(), updated)
                        if ok:
                            st.success("Your application has been updated.")
                        else:
                            st.error("Failed to update your application.")


# Backward-compatible wrapper some codebases import
def candidate_view():
    """Main candidate view function (backward compatibility)"""
    candidate_form_view()
