# receptionist.py
import streamlit as st
from db_postgres import find_candidates_by_name, update_candidate_form_data, update_candidate_resume_link, \
    set_candidate_permission
from datetime import datetime
import json


def upload_resume_to_drive(candidate_id: str, file_bytes: bytes, filename: str):
    """
    Placeholder function for Google Drive upload
    Replace this with your actual Google Drive integration
    """
    # This is a placeholder - implement your actual Drive upload logic here
    st.warning("Google Drive upload not implemented yet")
    return False, "", "Drive upload not configured"


def receptionist_view():
    st.header("Receptionist — Manage Candidates & Grant Edit Permission")

    # Search section
    st.subheader("Search Candidates")
    search_name = st.text_input("Search by name (partial match)")

    if st.button("Search") or search_name:
        if not search_name.strip():
            st.warning("Please enter a name to search.")
        else:
            try:
                results = find_candidates_by_name(search_name.strip())
                if not results:
                    st.info("No candidates found with that name.")
                else:
                    st.success(f"Found {len(results)} candidate(s)")

                    for candidate in results:
                        with st.expander(f"{candidate['candidate_id']} — {candidate.get('name', 'No Name')}"):
                            # Display candidate info
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**Name:** {candidate.get('name', 'N/A')}")
                                st.write(f"**Email:** {candidate.get('email', 'N/A')}")
                                st.write(f"**Phone:** {candidate.get('phone', 'N/A')}")
                            with col2:
                                st.write(f"**Can Edit:** {candidate.get('can_edit', False)}")
                                st.write(f"**Created:** {candidate.get('created_at', 'N/A')}")
                                if candidate.get('resume_link'):
                                    st.markdown(f"**Resume:** [View Resume]({candidate['resume_link']})")
                                else:
                                    st.write("**Resume:** Not uploaded")

                            # Permission management
                            st.markdown("---")
                            st.subheader("Edit Permission")

                            current_permission = candidate.get('can_edit', False)
                            new_permission = st.checkbox(
                                "Allow this candidate to edit their application",
                                value=current_permission,
                                key=f"allow_{candidate['candidate_id']}"
                            )

                            if st.button("Update Permission", key=f"update_perm_{candidate['candidate_id']}"):
                                success = set_candidate_permission(candidate['candidate_id'], new_permission)
                                if success:
                                    action = "granted" if new_permission else "revoked"
                                    st.success(f"Edit permission {action} for {candidate['candidate_id']}")

                                    # Update form_data with history
                                    form_data = candidate.get('form_data') or {}
                                    if isinstance(form_data, str):
                                        form_data = json.loads(form_data)

                                    form_data.setdefault('history', []).append({
                                        "action": action,
                                        "by": "receptionist",
                                        "at": datetime.utcnow().isoformat()
                                    })

                                    update_candidate_form_data(candidate['candidate_id'], form_data)
                                    st.rerun()
                                else:
                                    st.error("Failed to update permission.")

                            # Resume upload
                            st.markdown("---")
                            st.subheader("Resume Management")

                            uploaded_file = st.file_uploader(
                                f"Upload/Replace resume for {candidate['candidate_id']}",
                                key=f"resume_{candidate['candidate_id']}",
                                type=["pdf", "doc", "docx"],
                                help="Upload a PDF or Word document"
                            )

                            if uploaded_file is not None:
                                file_bytes = uploaded_file.read()
                                st.info("Uploading resume...")

                                # Call your resume upload function
                                success, webview_url, message = upload_resume_to_drive(
                                    candidate['candidate_id'],
                                    file_bytes,
                                    uploaded_file.name
                                )

                                if success:
                                    # Update the resume link in database
                                    if update_candidate_resume_link(candidate['candidate_id'], webview_url):
                                        st.success("Resume uploaded and linked successfully!")
                                        st.markdown(f"[View Resume]({webview_url})")
                                    else:
                                        st.error("Resume uploaded but failed to update database link")
                                else:
                                    st.error(f"Upload failed: {message}")

                            # Display form data if available
                            if candidate.get('form_data'):
                                st.markdown("---")
                                st.subheader("Application Data")
                                form_data = candidate['form_data']
                                if isinstance(form_data, str):
                                    try:
                                        form_data = json.loads(form_data)
                                    except:
                                        st.text(form_data)
                                else:
                                    st.json(form_data)

            except Exception as e:
                st.error(f"Error searching candidates: {str(e)}")

    # Quick stats
    st.markdown("---")
    st.subheader("Quick Actions")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Refresh View"):
            st.rerun()

    with col2:
        if st.button("Clear Search"):
            st.session_state.clear()
            st.rerun()