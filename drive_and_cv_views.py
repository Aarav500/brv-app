# drive_and_cv_views.py
import base64
import io
import os
import mimetypes
import streamlit as st
from db_postgres import get_candidate_cv

# ---- helpers ---------------------------------------------------------------

def _safe_mime(filename: str | None, fallback: str = "application/octet-stream") -> str:
    if not filename:
        return fallback
    m, _ = mimetypes.guess_type(filename)
    return m or fallback

def _data_url(mime: str, content: bytes) -> str:
    b64 = base64.b64encode(content).decode()
    return f"data:{mime};base64,{b64}"

def _is_text(mime: str) -> bool:
    return mime.startswith("text/") or mime in {"application/json", "application/xml"}

def _ext(name: str | None) -> str:
    return (os.path.splitext(name or "")[1] or "").lower()

# ---- public UI pieces ------------------------------------------------------

def preview_cv_ui(candidate_id: str, prefix: str = "cv") -> None:
    """
    Show an inline preview (when possible) and a download button.
    Use unique keys via `prefix` to avoid Streamlit key collisions.
    """
    try:
        file_data, filename = get_candidate_cv(candidate_id)
    except Exception as e:
        st.error(f"Error fetching CV: {e}")
        return

    if not file_data:
        st.info("No CV uploaded.")
        return

    # Always show download
    st.download_button(
        "⬇️ Download file",
        data=file_data,
        file_name=filename or f"{candidate_id}",
        key=f"dl_{prefix}_{candidate_id}",
    )

    mime = _safe_mime(filename)
    ext = _ext(filename)

    # ---- Preview matrix (best-effort, no external services) ----
    try:
        if mime == "application/pdf" or ext == ".pdf":
            st.markdown(
                f'<iframe src="{_data_url("application/pdf", file_data)}" width="100%" height="640" style="border:0;"></iframe>',
                unsafe_allow_html=True,
            )
            return

        if mime.startswith("image/"):
            st.image(file_data, caption=filename or "image")
            return

        if mime.startswith("audio/"):
            st.audio(io.BytesIO(file_data))
            return

        if mime.startswith("video/"):
            st.video(io.BytesIO(file_data))
            return

        if _is_text(mime):
            # Try to decode as UTF-8; fall back to latin-1 for robustness
            try:
                text = file_data.decode("utf-8")
            except UnicodeDecodeError:
                text = file_data.decode("latin-1", errors="replace")
            st.code(text, language="text")
            return

        # Word/Office files: show quick note + size, still downloadable above.
        if ext in {".doc", ".docx", ".rtf", ".odt", ".ppt", ".pptx", ".xls", ".xlsx"}:
            st.info("Preview not supported in-app for Office files. Please download to view.")
            return

        # Default fallback
        st.caption(f"No inline preview for {filename or 'file'} (type: {mime}).")

    except Exception as e:
        st.warning(f"Preview error: {e}")

def download_cv_ui(candidate_id: str, prefix: str = "cvdl") -> None:
    """Download-only widget with unique key to avoid collisions."""
    try:
        file_data, filename = get_candidate_cv(candidate_id)
    except Exception as e:
        st.error(f"Error preparing download: {e}")
        return

    if not file_data:
        st.info("No file available.")
        return

    st.download_button(
        "⬇️ Download file",
        data=file_data,
        file_name=filename or f"{candidate_id}",
        key=f"dl_only_{prefix}_{candidate_id}",
    )
def upload_cv_ui(candidate_id: str) -> None:
    """UI to upload a CV for a candidate."""
    uploaded_file = st.file_uploader("Upload CV", type=["pdf", "doc", "docx"], key=f"upload_{candidate_id}")
    if uploaded_file is not None:
        try:
            conn = get_conn()
            with conn, conn.cursor() as cur:
                cur.execute("""
                    UPDATE candidates
                    SET cv_file = %s, cv_filename = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE candidate_id = %s
                """, (uploaded_file.read(), uploaded_file.name, candidate_id))
            conn.close()
            st.success("CV uploaded successfully.")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to upload CV: {e}")

def delete_cv_ui(candidate_id: str) -> None:
    """UI to delete a CV for a candidate."""
    try:
        conn = get_conn()
        with conn, conn.cursor() as cur:
            cur.execute("""
                UPDATE candidates
                SET cv_file = NULL, cv_filename = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE candidate_id = %s
            """, (candidate_id,))
        conn.close()
        st.success("CV deleted successfully.")
        st.rerun()
    except Exception as e:
        st.error(f"Failed to delete CV: {e}")

