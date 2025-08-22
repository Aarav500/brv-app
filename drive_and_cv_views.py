"""
Drive & CV views — safe to import (no top-level Streamlit calls).
Use the small helpers (preview_cv_ui / upload_cv_ui / delete_cv_ui) inside your pages.
Or open the full manager via drive_and_cv_view().
"""

import mimetypes
import streamlit as st

from db_postgres import (
    get_user_permissions,
    get_all_candidates,
    get_candidate_cv,
    save_candidate_cv,
    delete_candidate,   # make sure this exists in db_postgres.py
    get_candidate_by_id,
)

# ---------- Permission helpers

def _is_admin_or_ceo(perms: dict) -> bool:
    return (perms.get("role") or "").lower() in ("admin", "ceo")

def _can_view_cv(perms: dict) -> bool:
    # DB-backed flag is can_view_cvs
    return bool(perms.get("can_view_cvs")) or _is_admin_or_ceo(perms)

def _can_upload_cv(perms: dict) -> bool:
    # No dedicated DB flag; allow upload if can_view_cvs or admin/ceo
    return bool(perms.get("can_view_cvs")) or _is_admin_or_ceo(perms)

def _can_delete_cv(perms: dict) -> bool:
    # Use delete candidate/grant delete or admin/ceo
    return bool(perms.get("can_delete_records")) or bool(perms.get("can_grant_delete")) or _is_admin_or_ceo(perms)

def _can_edit_cv(perms: dict) -> bool:
    # No dedicated DB flag; reuse view/admin rights
    return bool(perms.get("can_view_cvs")) or _is_admin_or_ceo(perms)


# ---------- Full-page CV manager

def drive_and_cv_view():
    """Standalone CV manager page."""
    user = st.session_state.get("user", {}) or {}
    if not user:
        st.error("No active session.")
        return

    perms = get_user_permissions(user.get("id")) or {}
    if not _can_view_cv(perms):
        st.error("🚫 You do not have permission to view CVs.")
        return

    st.header("CV / Drive Management")

    # Load candidates
    try:
        candidates = get_all_candidates() or []
    except Exception as e:
        st.error(f"Failed to load candidates: {e}")
        return

    # Select candidate
    options = [f"{c.get('candidate_id')} — {c.get('name') or 'Unnamed'}" for c in candidates]
    sel = st.selectbox("Select candidate", [""] + options)
    if not sel:
        st.info("Choose a candidate to proceed.")
        return

    candidate_id = sel.split(" — ")[0]

    # Current CV state
    try:
        cv_bytes, cv_name = get_candidate_cv(candidate_id)
    except Exception as e:
        st.error(f"Error fetching CV: {e}")
        return

    st.subheader("Current CV")
    if not cv_bytes:
        st.write("No CV uploaded for this candidate.")
    else:
        st.write(f"Filename: {cv_name or 'unknown'}")
        mime = mimetypes.guess_type(cv_name or "")[0] or "application/octet-stream"
        st.download_button("Download CV", data=cv_bytes, file_name=cv_name or f"{candidate_id}_cv", mime=mime)

        if _can_delete_cv(perms):
            if st.button("🗑️ Delete CV for candidate"):
                try:
                    ok = delete_candidate(candidate_id, user.get("id"))
                    if ok:
                        st.success("CV deleted.")
                        st.rerun()
                    else:
                        st.error("Failed to delete CV (no rows changed).")
                except Exception as e:
                    st.error(f"Error deleting CV: {e}")
        else:
            st.info("You do not have permission to delete CVs.")

    st.subheader("Upload / Replace CV")
    if _can_upload_cv(perms) or _can_edit_cv(perms):
        up = st.file_uploader("Upload CV (pdf/doc/docx)", type=["pdf", "doc", "docx"])
        if up and st.button("Save CV"):
            try:
                ok = save_candidate_cv(candidate_id, up.read(), up.name)
                if ok:
                    st.success("CV saved.")
                    st.rerun()
                else:
                    st.error("Failed to save CV.")
            except Exception as e:
                st.error(f"Save failed: {e}")
    else:
        st.info("You do not have permission to upload/replace CVs.")


# ---------- Lightweight building blocks (reuse these in other pages)

def preview_cv_ui(candidate_id: str):
    """Show minimal CV preview + download button (permission checks should be done by the caller).
    If no blob is stored, fall back to displaying resume_link (if present).
    """
    try:
        file_bytes, filename = get_candidate_cv(candidate_id)
    except Exception as e:
        st.error(f"Error fetching CV: {e}")
        return

    if not file_bytes:
        # Fallback: try resume_link from candidate row
        try:
            rec = get_candidate_by_id(candidate_id)
        except Exception as e:
            rec = None
        link = (rec or {}).get("resume_link") if isinstance(rec, dict) else None
        if link:
            st.success("CV link available")
            st.link_button("Open CV (external)", url=link)
            st.caption("Note: This CV is stored externally (e.g., Drive). Download preview is not available.")
            return
        st.info("No CV uploaded.")
        return

    st.success(f"CV found: {filename or 'unnamed'}")
    mime = mimetypes.guess_type(filename or "")[0] or "application/octet-stream"
    st.download_button("Download CV", file_bytes, file_name=filename or f"{candidate_id}.pdf", mime=mime)


def upload_cv_ui(candidate_id: str):
    """Upload/replace CV (caller should have checked upload permissions)."""
    up = st.file_uploader("Upload CV", type=["pdf", "doc", "docx"], key=f"up_{candidate_id}")
    if up and st.button("Save CV", key=f"savecv_{candidate_id}"):
        ok = save_candidate_cv(candidate_id, up.read(), up.name)
        if ok:
            st.success("CV saved.")
        else:
            st.error("Failed to save CV.")


def delete_cv_ui(candidate_id: str):
    """Delete CV (caller should have checked delete permissions).
    Note: This project does not implement a standalone 'delete CV' endpoint; use candidate deletion in privileged panels.
    """
    st.info("CV deletion is managed by admin/CEO via candidate deletion. No direct CV delete available here.")


# Optional: used by delete flow elsewhere; kept as a no-op hook for external storage
def delete_cv_from_drive(candidate_id: str):
    return True
