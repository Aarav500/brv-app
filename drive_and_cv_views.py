# drive_and_cv_views.py
import os
import mimetypes
import streamlit as st
from db_postgres import save_candidate_cv, get_candidate_cv, delete_candidate_cv


# --------- Upload CV

def upload_cv_ui(candidate_id: str):
    """Streamlit UI to upload a CV/resume file."""
    st.markdown("**Upload CV/Resume**")
    uploaded = st.file_uploader("Choose a file", type=["pdf", "doc", "docx", "png", "jpg", "jpeg"], key=f"cv_{candidate_id}")
    if uploaded and st.button("Upload CV", key=f"uploadbtn_{candidate_id}"):
        try:
            data = uploaded.read()
            save_candidate_cv(candidate_id, data, uploaded.name)
            st.success(f"Uploaded {uploaded.name}")
            st.rerun()
        except Exception as e:
            st.error(f"Error uploading CV: {e}")


# --------- Download CV

def download_cv_ui(candidate_id: str):
    """Streamlit UI to download candidate CV."""
    try:
        cv_file, cv_filename = get_candidate_cv(candidate_id)
        if cv_file:
            st.download_button(
                "📥 Download CV",
                data=cv_file,
                file_name=cv_filename or "resume.pdf",
                mime=mimetypes.guess_type(cv_filename or "resume.pdf")[0] or "application/octet-stream",
                key=f"download_{candidate_id}"
            )
    except Exception as e:
        st.error(f"Error fetching CV: {e}")


# --------- Delete CV

def delete_cv_ui(candidate_id: str):
    """Streamlit UI to delete candidate CV."""
    if st.button("🗑️ Delete CV", key=f"delcv_{candidate_id}"):
        try:
            if delete_candidate_cv(candidate_id):
                st.success("CV deleted successfully.")
                st.rerun()
            else:
                st.warning("No CV to delete.")
        except Exception as e:
            st.error(f"Error deleting CV: {e}")


# --------- Preview CV

def preview_cv_ui(candidate_id: str):
    """Preview the CV file (PDF, DOCX, or image) inside Streamlit."""
    try:
        cv_file, cv_filename = get_candidate_cv(candidate_id)
        if not cv_file:
            st.info("No CV uploaded.")
            upload_cv_ui(candidate_id)
            return

        # Show download button
        download_cv_ui(candidate_id)
        delete_cv_ui(candidate_id)

        # File type detection
        mime_type, _ = mimetypes.guess_type(cv_filename or "")
        if not mime_type:
            mime_type = "application/octet-stream"

        st.markdown("#### CV Preview")

        if mime_type == "application/pdf":
            # Embed PDF in iframe
            import base64
            b64_pdf = base64.b64encode(cv_file).decode("utf-8")
            pdf_display = f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="600"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)

        elif mime_type in ["image/png", "image/jpeg"]:
            # Show image
            from PIL import Image
            import io
            st.image(Image.open(io.BytesIO(cv_file)), caption=cv_filename, use_container_width=True)

        elif mime_type in ["application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
            st.info("DOC/DOCX preview not supported inline. Please download to view.")
        else:
            st.info(f"Preview not available for this file type ({mime_type}). Please download to view.")

    except Exception as e:
        st.error(f"Error previewing CV: {e}")
