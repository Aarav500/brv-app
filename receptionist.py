import streamlit as st
from db import find_candidates_by_name, update_candidate_form_data, upload_resume_to_drive, update_candidate_resume_link
from datetime import datetime

def receptionist_view():
    st.header("Receptionist — Manage Candidates & Grant Edit Permission (by name)")

    search_name = st.text_input("Search name (partial)")
    if st.button("Search"):
        if not search_name:
            st.warning("Type a name to search.")
        else:
            results = find_candidates_by_name(search_name)
            if not results:
                st.info("No candidates found with that name.")
            else:
                st.success(f"{len(results)} candidate(s) found")
                for c in results:
                    with st.expander(f"{c['candidate_id']} — {c.get('name')}"):
                        st.write("Name:", c.get('name'))
                        st.write("Email:", c.get('email'))
                        st.write("Allowed Edit:", c.get('form_data', {}).get('allowed_edit', False))

                        allow = st.checkbox(
                            "Allow this candidate to edit their application",
                            value=c.get('form_data', {}).get('allowed_edit', False),
                            key=f"allow_{c['candidate_id']}"
                        )

                        if st.button("Apply permission", key=f"applyperm_{c['candidate_id']}"):
                            fd = c.get('form_data') or {}
                            fd['allowed_edit'] = bool(allow)
                            fd.setdefault('history', []).append({
                                "action": ("granted" if allow else "revoked"),
                                "by": "receptionist",
                                "at": datetime.utcnow().isoformat()
                            })
                            ok = update_candidate_form_data(c['candidate_id'], fd)
                            if ok:
                                st.success(f"Permission {'granted' if allow else 'revoked'} for {c['candidate_id']}")
                            else:
                                st.error("Failed to update permission.")

                        st.markdown("**Upload / replace resume for this candidate**")
                        up = st.file_uploader(
                            f"Upload resume for {c['candidate_id']}",
                            key=f"up_{c['candidate_id']}",
                            type=["pdf"]
                        )
                        if up:
                            bytes_ = up.read()
                            st.info("Uploading resume to Drive...")
                            success, webview, msg = upload_resume_to_drive(c['candidate_id'], bytes_, up.name)
                            if success:
                                update_candidate_resume_link(c['candidate_id'], webview)
                                st.success("Resume uploaded and linked.")
                                st.markdown(f"[Open Resume]({webview})")
                            else:
                                st.error("Upload failed: " + str(msg))
