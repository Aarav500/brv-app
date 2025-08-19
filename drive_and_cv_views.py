import base64
import streamlit as st
from db_postgres import (
    save_candidate_cv,
    get_candidate_cv,
    delete_candidate_cv,
    get_total_cv_storage_usage,
)


def upload_cv_ui(candidate_id: str):
    """Streamlit UI for uploading and saving CV into PostgreSQL"""
    st.subheader("📤 Upload Candidate CV")

    uploaded_file = st.file_uploader(
        "Upload CV (PDF / DOC / DOCX / TXT / RTF)",
        type=["pdf", "doc", "docx", "txt", "rtf"],
        key=f"cv_{candidate_id}"
    )

    if uploaded_file is not None:
        file_bytes = uploaded_file.read()
        filename = uploaded_file.name

        ok = save_candidate_cv(candidate_id, file_bytes, filename)
        if ok:
            st.success(f"✅ CV uploaded successfully for {candidate_id}")
        else:
            st.error("❌ Failed to upload CV. Please try again.")


def preview_cv_ui(candidate_id: str, height: int = 620):
    """Preview candidate CV if PDF, otherwise provide download."""
    st.subheader("📄 Preview Candidate CV")

    file_bytes, filename = get_candidate_cv(candidate_id)
    if not file_bytes:
        st.info("No CV uploaded for this candidate.")
        return

    # Always allow download
    st.download_button(
        label="📥 Download CV",
        data=file_bytes,
        file_name=filename or f"{candidate_id}.cv",
        mime="application/octet-stream",
    )

    # Inline preview only for PDF
    if filename and filename.lower().endswith(".pdf"):
        b64 = base64.b64encode(file_bytes).decode()
        data_url = f"data:application/pdf;base64,{b64}"
        st.components.v1.html(
            f"<iframe src='{data_url}' width='100%' height='{height}'></iframe>",
            height=height + 10,
        )
    else:
        ext = filename.split(".")[-1].upper() if filename else "file"
        st.info(f"Preview not supported for `{ext}`. Please download instead.")


def delete_cv_ui(candidate_id: str):
    """Streamlit UI for deleting a candidate CV"""
    st.subheader("🗑️ Delete Candidate CV")

    if st.button("Delete CV", key=f"delete_cv_{candidate_id}"):
        ok = delete_candidate_cv(candidate_id)
        if ok:
            st.success("✅ CV deleted successfully")
        else:
            st.error("❌ Failed to delete CV. Please try again.")


def show_storage_usage():
    """Show PostgreSQL CV storage usage"""
    st.subheader("📊 CV Storage Usage")

    used_bytes = get_total_cv_storage_usage()
    used_mb = round(used_bytes / (1024 * 1024), 2)

    # Arbitrary limit (say 500 MB) for progress bar visualization
    limit_mb = 500
    usage_percent = min(100, int((used_mb / limit_mb) * 100))

    st.progress(usage_percent)
    st.write(f"Used: {used_mb} MB of {limit_mb} MB ({usage_percent}%)")
