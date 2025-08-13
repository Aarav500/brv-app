# receptionist.py
import streamlit as st
from db_postgres import find_candidates_by_name, update_candidate_form_data, update_candidate_resume_link, \
    set_candidate_permission, create_candidate_in_db, get_all_candidates
from google_drive import smart_resume_upload, show_drive_config_status
from datetime import datetime
import json
import uuid


def receptionist_view():
    st.header("Receptionist — Manage Candidates & Grant Edit Permission")

    # Show Google Drive configuration status
    with st.expander("🔧 Google Drive Configuration", expanded=False):
        show_drive_config_status()

    # Tab layout for better organization
    tab1, tab2, tab3, tab4 = st.tabs(["Search Candidates", "Create Walk-in", "All Candidates", "Quick Stats"])

    with tab1:
        st.subheader("🔍 Search Candidates")
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
                            with st.expander(f"📋 {candidate['candidate_id']} — {candidate.get('name', 'No Name')}"):
                                # Display candidate info
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.write(f"**Name:** {candidate.get('name', 'N/A')}")
                                    st.write(f"**Email:** {candidate.get('email', 'N/A')}")
                                    st.write(f"**Phone:** {candidate.get('phone', 'N/A')}")
                                with col2:
                                    st.write(f"**Can Edit:** {'✅ Yes' if candidate.get('can_edit', False) else '❌ No'}")
                                    st.write(f"**Created:** {candidate.get('created_at', 'N/A')}")
                                    if candidate.get('resume_link'):
                                        st.markdown(f"**Resume:** [View Resume]({candidate['resume_link']})")
                                    else:
                                        st.write("**Resume:** ❌ Not uploaded")

                                # Permission management
                                st.markdown("---")
                                st.subheader("🔐 Edit Permission")

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
                                        st.success(f"✅ Edit permission {action} for {candidate['candidate_id']}")

                                        # Update form_data with history
                                        form_data = candidate.get('form_data') or {}
                                        if isinstance(form_data, str):
                                            try:
                                                form_data = json.loads(form_data)
                                            except:
                                                form_data = {}

                                        form_data.setdefault('history', []).append({
                                            "action": f"permission_{action}",
                                            "by": "receptionist",
                                            "at": datetime.utcnow().isoformat()
                                        })

                                        update_candidate_form_data(candidate['candidate_id'], form_data)
                                        st.rerun()
                                    else:
                                        st.error("❌ Failed to update permission.")

                                # Resume upload
                                st.markdown("---")
                                st.subheader("📄 Resume Management")

                                uploaded_file = st.file_uploader(
                                    f"Upload/Replace resume for {candidate['candidate_id']}",
                                    key=f"resume_{candidate['candidate_id']}",
                                    type=["pdf", "doc", "docx"],
                                    help="Upload a PDF or Word document"
                                )

                                if uploaded_file is not None:
                                    file_bytes = uploaded_file.read()
                                    st.info("📤 Uploading resume...")

                                    with st.spinner("Uploading..."):
                                        success, webview_url, message = smart_resume_upload(
                                            candidate['candidate_id'],
                                            file_bytes,
                                            uploaded_file.name
                                        )

                                        if success:
                                            # Update the resume link in database
                                            if update_candidate_resume_link(candidate['candidate_id'], webview_url):
                                                st.success("✅ Resume uploaded and linked successfully!")
                                                st.markdown(f"[📎 View Resume]({webview_url})")
                                                st.info(f"Upload details: {message}")

                                                # Add to history
                                                form_data = candidate.get('form_data') or {}
                                                if isinstance(form_data, str):
                                                    try:
                                                        form_data = json.loads(form_data)
                                                    except:
                                                        form_data = {}

                                                form_data.setdefault('history', []).append({
                                                    "action": "resume_uploaded_by_receptionist",
                                                    "filename": uploaded_file.name,
                                                    "at": datetime.utcnow().isoformat()
                                                })

                                                update_candidate_form_data(candidate['candidate_id'], form_data)
                                            else:
                                                st.error("⚠️ Resume uploaded but failed to update database link")
                                        else:
                                            st.error(f"❌ Upload failed: {message}")

                                # Display form data if available
                                if candidate.get('form_data'):
                                    st.markdown("---")
                                    st.subheader("📋 Application Data")
                                    form_data = candidate['form_data']
                                    if isinstance(form_data, str):
                                        try:
                                            form_data = json.loads(form_data)
                                        except:
                                            st.text("Invalid JSON format")
                                            form_data = {}

                                    if isinstance(form_data, dict):
                                        # Show key fields nicely formatted
                                        if form_data.get('skills'):
                                            st.write(f"**Skills:** {form_data['skills']}")
                                        if form_data.get('experience'):
                                            st.write(f"**Experience:** {form_data['experience']}")
                                        if form_data.get('education'):
                                            st.write(f"**Education:** {form_data['education']}")

                                        # Show history if available
                                        if form_data.get('history'):
                                            with st.expander("📜 History"):
                                                for entry in form_data['history']:
                                                    st.write(
                                                        f"• {entry.get('action', 'Unknown')} at {entry.get('at', 'Unknown time')}")
                                    else:
                                        st.json(form_data)

                except Exception as e:
                    st.error(f"Error searching candidates: {str(e)}")

    with tab2:
        st.subheader("🚶 Create Walk-in Candidate")

        col1, col2 = st.columns(2)
        with col1:
            walkin_name = st.text_input("Full Name", key="walkin_name")
            walkin_email = st.text_input("Email Address", key="walkin_email")
            walkin_phone = st.text_input("Phone Number", key="walkin_phone")

        with col2:
            walkin_skills = st.text_area("Skills", key="walkin_skills", placeholder="Key skills and technologies")
            walkin_experience = st.text_area("Experience", key="walkin_experience", placeholder="Work experience")
            walkin_education = st.text_area("Education", key="walkin_education", placeholder="Educational background")

        walkin_file = st.file_uploader("Upload CV (Optional)", key="walkin_cv", type=["pdf", "doc", "docx"])

        col1, col2 = st.columns(2)
        with col1:
            allow_edit = st.checkbox("Allow candidate to edit later", value=True, key="walkin_allow_edit")
        with col2:
            if st.button("Create Walk-in Candidate", type="primary"):
                if not walkin_name.strip():
                    st.error("❌ Name is required")
                else:
                    try:
                        new_id = str(uuid.uuid4())[:8].upper()

                        form_data = {
                            "skills": walkin_skills.strip(),
                            "experience": walkin_experience.strip(),
                            "education": walkin_education.strip(),
                            "allowed_edit": allow_edit,
                            "history": [{
                                "action": "created_by_receptionist",
                                "at": datetime.utcnow().isoformat()
                            }]
                        }

                        # Create candidate
                        rec = create_candidate_in_db(
                            candidate_id=new_id,
                            name=walkin_name.strip(),
                            email=walkin_email.strip() if walkin_email.strip() else None,
                            phone=walkin_phone.strip() if walkin_phone.strip() else None,
                            form_data=form_data,
                            created_by="receptionist"
                        )

                        if rec:
                            st.success(f"✅ Created candidate {new_id}")

                            # Set edit permission
                            set_candidate_permission(new_id, allow_edit)

                            # Handle file upload if provided
                            if walkin_file:
                                file_bytes = walkin_file.read()
                                with st.spinner("Uploading resume..."):
                                    ok, link, msg = smart_resume_upload(new_id, file_bytes, walkin_file.name)
                                    if ok:
                                        update_candidate_resume_link(new_id, link)
                                        st.success(f"✅ Resume uploaded: [View Resume]({link})")
                                        st.info(f"Upload details: {msg}")
                                    else:
                                        st.error(f"❌ Resume upload failed: {msg}")

                            st.info(f"📝 Candidate ID: **{new_id}** (Share with candidate for future edits)")
                        else:
                            st.error("❌ Failed to create candidate")

                    except Exception as e:
                        st.error(f"❌ Error creating walk-in candidate: {str(e)}")

    with tab3:
        st.subheader("👥 All Candidates")

        if st.button("Refresh All Candidates"):
            st.rerun()

        try:
            all_candidates = get_all_candidates()

            if all_candidates:
                # Search filter
                filter_text = st.text_input("Filter candidates", placeholder="Search by name or email...")

                if filter_text:
                    all_candidates = [
                        c for c in all_candidates
                        if filter_text.lower() in str(c.get('name', '')).lower() or
                           filter_text.lower() in str(c.get('email', '')).lower()
                    ]

                st.info(f"Showing {len(all_candidates)} candidates")

                # Create a summary table
                for candidate in all_candidates:
                    with st.container():
                        col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 1, 1])

                        with col1:
                            st.write(f"**{candidate.get('name', 'No Name')}**")
                            st.write(f"ID: {candidate['candidate_id']}")

                        with col2:
                            st.write(f"Email: {candidate.get('email', 'N/A')}")
                            st.write(f"Phone: {candidate.get('phone', 'N/A')}")

                        with col3:
                            if candidate.get('resume_link'):
                                st.markdown("✅ Resume")
                            else:
                                st.markdown("❌ No Resume")

                        with col4:
                            if candidate.get('can_edit'):
                                st.markdown("🔓 Can Edit")
                            else:
                                st.markdown("🔒 No Edit")

                        with col5:
                            st.write(f"Created: {str(candidate.get('created_at', 'N/A'))[:10]}")

                        st.divider()

            else:
                st.info("No candidates found")

        except Exception as e:
            st.error(f"Error loading candidates: {str(e)}")

    with tab4:
        st.subheader("📊 Quick Statistics")

        try:
            all_candidates = get_all_candidates()

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Total Candidates", len(all_candidates))

            with col2:
                with_resume = len([c for c in all_candidates if c.get('resume_link')])
                st.metric("With Resume", with_resume)

            with col3:
                can_edit = len([c for c in all_candidates if c.get('can_edit')])
                st.metric("Can Edit", can_edit)

            with col4:
                today = datetime.now().date()
                today_candidates = len([
                    c for c in all_candidates
                    if c.get('created_at') and c['created_at'].date() == today
                ])
                st.metric("Created Today", today_candidates)

        except Exception as e:
            st.error(f"Error loading statistics: {str(e)}")

    # Quick actions section
    st.markdown("---")
    st.subheader("⚡ Quick Actions")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🔄 Refresh View"):
            st.rerun()

    with col2:
        if st.button("🗑️ Clear Search"):
            st.session_state.clear()
            st.rerun()

    with col3:
        if st.button("📊 Show Statistics"):
            st.balloons()
            st.success("Statistics refreshed!")