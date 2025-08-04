import streamlit as st
import os
import re
import requests
from io import BytesIO
import base64
from PIL import Image
from datetime import datetime

def show_resume_handler():
    """
    Main function for the resume handler interface.
    This is called from main.py.
    """
    st.title("📄 Resume Handler")
    st.subheader("Process Candidate Resumes")

    # Add tabs for different resume handling functions
    tab1, tab2 = st.tabs(["Upload Resume", "View Resumes"])

    with tab1:
        st.write("Upload a new candidate resume:")

        # Add tabs for different search methods
        search_tab1, search_tab2, search_tab3 = st.tabs(["Search by Email", "Search by Application ID", "Search by Name"])

        with search_tab1:
            # Get candidate email
            candidate_email = st.text_input("Candidate Email", placeholder="john.doe@example.com", key="email_search")
            search_by_email = st.button("Search by Email")

        with search_tab2:
            # Get candidate application ID
            application_id = st.text_input("Application ID", placeholder="BRV2025_00123", key="application_id_search")
            search_by_application_id = st.button("Search by Application ID")

        with search_tab3:
            # Get candidate name
            candidate_name = st.text_input("Candidate Name", placeholder="John Doe", key="name_search")
            search_by_name = st.button("Search by Name")

        # Initialize session state for candidate search
        if "candidate_found" not in st.session_state:
            st.session_state.candidate_found = False
            st.session_state.candidate_data = None

        # Search for candidate by email
        if search_by_email and candidate_email:
            from firebase_candidates import get_candidate_by_email
            candidate = get_candidate_by_email(candidate_email)
            if candidate:
                st.session_state.candidate_found = True
                st.session_state.candidate_data = candidate
                st.success(f"Found candidate: {candidate_email} (Application ID: {candidate.get('application_id', 'N/A')})")
            else:
                st.error(f"Candidate with email {candidate_email} not found.")
                st.session_state.candidate_found = False
                st.session_state.candidate_data = None

        # Search for candidate by application ID
        if search_by_application_id and application_id:
            from firebase_candidates import db
            candidate_ref = db.collection("candidates").document(application_id)
            candidate_doc = candidate_ref.get()
            if candidate_doc.exists:
                candidate = candidate_doc.to_dict()
                st.session_state.candidate_found = True
                st.session_state.candidate_data = candidate
                email = candidate.get("email", "N/A")
                st.success(f"Found candidate with Application ID: {application_id} (Email: {email})")
            else:
                # Try searching by application_id field
                candidates_ref = db.collection("candidates")
                query = candidates_ref.where("application_id", "==", application_id)
                candidates = list(query.stream())
                if candidates:
                    candidate = candidates[0].to_dict()
                    st.session_state.candidate_found = True
                    st.session_state.candidate_data = candidate
                    email = candidate.get("email", "N/A")
                    st.success(f"Found candidate with Application ID: {application_id} (Email: {email})")
                else:
                    st.error(f"Candidate with Application ID {application_id} not found.")
                    st.session_state.candidate_found = False
                    st.session_state.candidate_data = None

        # Search for candidate by name
        if search_by_name and candidate_name:
            from firebase_candidates import db
            candidates_ref = db.collection("candidates")
            # Try exact match on full_name field
            query = candidates_ref.where("full_name", "==", candidate_name)
            candidates = list(query.stream())
            if not candidates:
                # Try searching in form_data
                all_candidates = list(candidates_ref.stream())
                candidates = []
                for doc in all_candidates:
                    cand_data = doc.to_dict()
                    form_data = cand_data.get("form_data", {})
                    for key, value in form_data.items():
                        if "name" in key.lower() and candidate_name.lower() in str(value).lower():
                            candidates.append(doc)
                            break

            if candidates:
                if len(candidates) == 1:
                    candidate = candidates[0].to_dict()
                    st.session_state.candidate_found = True
                    st.session_state.candidate_data = candidate
                    email = candidate.get("email", "N/A")
                    application_id = candidate.get("application_id", "N/A")
                    st.success(f"Found candidate: {candidate_name} (Email: {email}, Application ID: {application_id})")
                else:
                    st.warning(f"Found {len(candidates)} candidates with name '{candidate_name}'. Please select one:")
                    for i, doc in enumerate(candidates):
                        cand_data = doc.to_dict()
                        email = cand_data.get("email", "N/A")
                        application_id = cand_data.get("application_id", "N/A")
                        if st.button(f"Select: {candidate_name} (Email: {email}, Application ID: {application_id})", key=f"select_{i}"):
                            st.session_state.candidate_found = True
                            st.session_state.candidate_data = cand_data
                            st.success(f"Selected candidate: {candidate_name} (Email: {email}, Application ID: {application_id})")
            else:
                st.error(f"Candidate with name {candidate_name} not found.")
                st.session_state.candidate_found = False
                st.session_state.candidate_data = None

        uploaded_file = st.file_uploader("Choose a file", type=["pdf", "docx", "doc", "jpg", "jpeg", "png"])

        if uploaded_file is not None:
            # Display file details
            file_details = {"Filename": uploaded_file.name, "FileType": uploaded_file.type, "FileSize": f"{uploaded_file.size / 1024:.2f} KB"}
            st.write(file_details)

            # Display a preview of the resume
            st.write("Resume Preview:")
            if uploaded_file.type.startswith("image"):
                st.image(uploaded_file, width=500)
            elif uploaded_file.type == "application/pdf":
                st.write("PDF preview not available. Please use the download button.")

            # Create directory if it doesn't exist
            if not os.path.exists("cvs"):
                os.makedirs("cvs")

            # Check if a candidate has been found
            if st.session_state.candidate_found and st.session_state.candidate_data:
                candidate = st.session_state.candidate_data

                # Get candidate ID for standardized filename
                candidate_id = None
                
                # First try to get application_id
                if "application_id" in candidate:
                    candidate_id = candidate["application_id"]
                # Then try to get id
                elif "id" in candidate:
                    candidate_id = candidate["id"]
                # If still no ID, generate one using timestamp
                else:
                    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                    candidate_id = timestamp
                
                # Standardized filename format: CV_<CandidateID>.pdf
                new_filename = f"CV_{candidate_id}.pdf"
                
                file_path = os.path.join("cvs", new_filename)

                # Save the file
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                # Update candidate with resume path
                from firebase_candidates import update_candidate
                update_candidate(candidate["id"], resume_link=new_filename)

                # Display success message with appropriate information
                email = candidate.get("email", "N/A")
                application_id = candidate.get("application_id", "N/A")
                full_name = candidate.get("full_name", "")
                if not full_name:
                    # Try to get name from form_data
                    form_data = candidate.get("form_data", {})
                    for key, value in form_data.items():
                        if "name" in key.lower():
                            full_name = str(value)
                            break

                success_message = f"Resume uploaded and linked to candidate successfully!\n"
                if email != "N/A":
                    success_message += f"Email: {email}\n"
                if application_id != "N/A":
                    success_message += f"Application ID: {application_id}\n"
                if full_name:
                    success_message += f"Name: {full_name}"

                st.success(success_message)
            else:
                st.warning("Please search for and select a candidate before uploading a resume.")

    with tab2:
        st.write("View existing candidate resumes:")

        # Check if there are any resumes in the data/resumes directory
        if os.path.exists("data/resumes"):
            resume_files = [f for f in os.listdir("data/resumes") if os.path.isfile(os.path.join("data/resumes", f))]
            if resume_files:
                # Sort files by modification time (newest first)
                resume_files.sort(key=lambda x: os.path.getmtime(os.path.join("data/resumes", x)), reverse=True)

                # Create a more user-friendly display for each resume file
                display_names = []
                for file in resume_files:
                    # Check if file follows the application_id format
                    if "_CV" in file:
                        # Extract application_id
                        application_id = file.split("_CV")[0]
                        display_name = f"{application_id} - {file}"

                        # Try to get candidate info from Firestore
                        from firebase_candidates import db
                        candidate_ref = db.collection("candidates").document(application_id)
                        candidate_doc = candidate_ref.get()
                        if candidate_doc.exists:
                            candidate = candidate_doc.to_dict()
                            email = candidate.get("email", "")
                            full_name = candidate.get("full_name", "")
                            if not full_name:
                                # Try to get name from form_data
                                form_data = candidate.get("form_data", {})
                                for key, value in form_data.items():
                                    if "name" in key.lower():
                                        full_name = str(value)
                                        break

                            if full_name and email:
                                display_name = f"{full_name} ({email}) - {application_id}"
                            elif full_name:
                                display_name = f"{full_name} - {application_id}"
                            elif email:
                                display_name = f"{email} - {application_id}"
                    else:
                        # For older format files
                        display_name = file

                    display_names.append((file, display_name))

                # Create a dictionary mapping display names to actual filenames
                file_dict = {display: file for file, display in display_names}

                # Show the selectbox with display names
                selected_display = st.selectbox("Select a resume", [display for _, display in display_names])

                if selected_display:
                    # Get the actual filename
                    selected_resume = file_dict[selected_display]
                    resume_path = os.path.join("data/resumes", selected_resume)

                    # Extract candidate name for display
                    candidate_name = "Selected Candidate"
                    if "_CV" in selected_resume:
                        application_id = selected_resume.split("_CV")[0]
                        # Try to get candidate info from Firestore
                        from firebase_candidates import db
                        candidate_ref = db.collection("candidates").document(application_id)
                        candidate_doc = candidate_ref.get()
                        if candidate_doc.exists:
                            candidate = candidate_doc.to_dict()
                            full_name = candidate.get("full_name", "")
                            if not full_name:
                                # Try to get name from form_data
                                form_data = candidate.get("form_data", {})
                                for key, value in form_data.items():
                                    if "name" in key.lower():
                                        full_name = str(value)
                                        break

                            if full_name:
                                candidate_name = full_name

                    display_resume(resume_path, candidate_name)
            else:
                st.info("No resume files found in data/resumes directory.")
        else:
            st.info("data/resumes directory not found.")

def is_google_drive_link(url):
    """
    Check if a URL is a Google Drive link.

    Args:
        url (str): The URL to check

    Returns:
        bool: True if the URL is a Google Drive link, False otherwise
    """
    if not url:
        return False

    # Common Google Drive URL patterns
    patterns = [
        r'drive\.google\.com/file/d/([a-zA-Z0-9_-]+)',
        r'drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)',
        r'docs\.google\.com/document/d/([a-zA-Z0-9_-]+)'
    ]

    for pattern in patterns:
        if re.search(pattern, url):
            return True

    return False

def extract_file_id(url):
    """
    Extract the file ID from a Google Drive URL.

    Args:
        url (str): The Google Drive URL

    Returns:
        str: The file ID, or None if not found
    """
    if not url:
        return None

    # Extract file ID from various Google Drive URL formats
    patterns = [
        r'drive\.google\.com/file/d/([a-zA-Z0-9_-]+)',
        r'drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)',
        r'docs\.google\.com/document/d/([a-zA-Z0-9_-]+)'
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None

def get_direct_download_url(file_id):
    """
    Get a direct download URL for a Google Drive file.

    Args:
        file_id (str): The Google Drive file ID

    Returns:
        str: The direct download URL
    """
    return f"https://drive.google.com/uc?export=download&id={file_id}"

def display_resume(resume_path, candidate_name="Candidate"):
    """
    Display a resume with fallback options.

    Args:
        resume_path (str): Path to the resume file or Google Drive URL
        candidate_name (str): Name of the candidate

    Returns:
        bool: True if the resume was displayed successfully, False otherwise
    """
    import streamlit.components.v1 as components

    if not resume_path:
        st.warning("⚠️ No resume available for this candidate.")
        return False

    # Check if it's a Google Drive link
    if is_google_drive_link(resume_path):
        file_id = extract_file_id(resume_path)
        if file_id:
            download_url = get_direct_download_url(file_id)

            st.subheader("📄 Candidate Resume (Preview)")

            # Create a preview URL for Google Drive
            preview_url = f"https://drive.google.com/file/d/{file_id}/preview"

            # Embed the Google Drive preview in an iframe
            components.iframe(preview_url, height=800, width=1000)

            # Add download links
            st.markdown(f"[📄 View in Google Drive]({resume_path}) | [📥 Download Resume]({download_url})", unsafe_allow_html=True)

            # Add notes section
            st.subheader("📝 Interview Notes")

            # Check if notes already exist in session state
            if f"notes_{file_id}" not in st.session_state:
                st.session_state[f"notes_{file_id}"] = ""

            notes = st.text_area(
                "Add your notes about this resume here. These will be saved for your reference.",
                value=st.session_state[f"notes_{file_id}"],
                height=200,
                key=f"notes_input_{file_id}"
            )

            # Save notes to session state when changed
            if notes != st.session_state[f"notes_{file_id}"]:
                st.session_state[f"notes_{file_id}"] = notes
                st.success("Notes saved!")

            return True
        else:
            st.warning("⚠️ Invalid Google Drive link.")
            return False

    # Check if it's a local file
    elif os.path.exists(resume_path):
        file_name = os.path.basename(resume_path)
        file_extension = os.path.splitext(file_name)[1].lower()

        st.subheader("📄 Candidate Resume (Preview)")

        # Handle different file types
        if file_extension in ['.pdf', '.doc', '.docx']:
            # For document files, provide a download button
            with open(resume_path, "rb") as f:
                file_content = f.read()
                st.download_button(
                    label="📥 Download Resume",
                    data=file_content,
                    file_name=file_name,
                    mime=f"application/{file_extension[1:]}"
                )

            # Try to display PDF preview if it's a PDF
            if file_extension == '.pdf':
                try:
                    # Create a base64 encoded version of the PDF
                    base64_pdf = base64.b64encode(file_content).decode('utf-8')
                    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf"></iframe>'
                    st.markdown(pdf_display, unsafe_allow_html=True)
                except:
                    st.info("PDF preview not available. Please download the file.")

            # Add notes section
            st.subheader("📝 Interview Notes")

            # Use file path as key for session state
            if f"notes_{resume_path}" not in st.session_state:
                st.session_state[f"notes_{resume_path}"] = ""

            notes = st.text_area(
                "Add your notes about this resume here. These will be saved for your reference.",
                value=st.session_state[f"notes_{resume_path}"],
                height=200,
                key=f"notes_input_{resume_path}"
            )

            # Save notes to session state when changed
            if notes != st.session_state[f"notes_{resume_path}"]:
                st.session_state[f"notes_{resume_path}"] = notes
                st.success("Notes saved!")

            return True

        elif file_extension in ['.jpg', '.jpeg', '.png', '.gif']:
            # For image files, display the image
            try:
                image = Image.open(resume_path)
                st.image(image, caption=f"{candidate_name}'s Resume", width=1000)

                # Also provide a download button
                with open(resume_path, "rb") as f:
                    st.download_button(
                        label="📥 Download Resume Image",
                        data=f,
                        file_name=file_name,
                        mime=f"image/{file_extension[1:]}"
                    )

                # Add notes section
                st.subheader("📝 Interview Notes")

                # Use file path as key for session state
                if f"notes_{resume_path}" not in st.session_state:
                    st.session_state[f"notes_{resume_path}"] = ""

                notes = st.text_area(
                    "Add your notes about this resume here. These will be saved for your reference.",
                    value=st.session_state[f"notes_{resume_path}"],
                    height=200,
                    key=f"notes_input_{resume_path}"
                )

                # Save notes to session state when changed
                if notes != st.session_state[f"notes_{resume_path}"]:
                    st.session_state[f"notes_{resume_path}"] = notes
                    st.success("Notes saved!")

                return True
            except:
                st.warning("⚠️ Could not display the resume image.")
                return False

        else:
            # For other file types, just provide a download button
            with open(resume_path, "rb") as f:
                st.download_button(
                    label="📥 Download Resume",
                    data=f,
                    file_name=file_name
                )

            # Add notes section
            st.subheader("📝 Interview Notes")

            # Use file path as key for session state
            if f"notes_{resume_path}" not in st.session_state:
                st.session_state[f"notes_{resume_path}"] = ""

            notes = st.text_area(
                "Add your notes about this resume here. These will be saved for your reference.",
                value=st.session_state[f"notes_{resume_path}"],
                height=200,
                key=f"notes_input_{resume_path}"
            )

            # Save notes to session state when changed
            if notes != st.session_state[f"notes_{resume_path}"]:
                st.session_state[f"notes_{resume_path}"] = notes
                st.success("Notes saved!")

            return True

    else:
        st.warning("⚠️ Resume file not found.")
        return False

def display_resume_from_url(resume_url, candidate_name="Candidate"):
    """
    Display a resume from a URL.

    Args:
        resume_url (str): URL to the resume
        candidate_name (str): Name of the candidate

    Returns:
        bool: True if the resume was displayed successfully, False otherwise
    """
    import streamlit.components.v1 as components

    if not resume_url:
        st.warning("⚠️ No resume URL provided.")
        return False

    # Check if it's a Google Drive link
    if is_google_drive_link(resume_url):
        file_id = extract_file_id(resume_url)
        if file_id:
            # Create a preview URL for Google Drive
            preview_url = f"https://drive.google.com/file/d/{file_id}/preview"

            st.subheader("📄 Candidate Resume (Preview)")

            # Embed the Google Drive preview in an iframe
            components.iframe(preview_url, height=800, width=1000)

            # Add a download link
            st.markdown(f"[📥 Download Resume]({resume_url})", unsafe_allow_html=True)

            # Add notes section
            st.subheader("📝 Interview Notes")

            # Check if notes already exist in session state
            if f"notes_{file_id}" not in st.session_state:
                st.session_state[f"notes_{file_id}"] = ""

            notes = st.text_area(
                "Add your notes about this resume here. These will be saved for your reference.",
                value=st.session_state[f"notes_{file_id}"],
                height=200,
                key=f"notes_input_{file_id}"
            )

            # Save notes to session state when changed
            if notes != st.session_state[f"notes_{file_id}"]:
                st.session_state[f"notes_{file_id}"] = notes
                st.success("Notes saved!")

            return True
        else:
            st.warning("⚠️ Could not extract file ID from Google Drive link.")
            return False

    # Try to fetch the file from the URL
    try:
        response = requests.get(resume_url)
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            file_extension = '.pdf'  # Default to PDF

            # Determine file extension from content type
            if 'pdf' in content_type:
                file_extension = '.pdf'
            elif 'word' in content_type or 'docx' in content_type:
                file_extension = '.docx'
            elif 'image' in content_type:
                if 'jpeg' in content_type or 'jpg' in content_type:
                    file_extension = '.jpg'
                elif 'png' in content_type:
                    file_extension = '.png'
                else:
                    file_extension = '.img'

            # Create a filename
            file_name = f"{candidate_name.replace(' ', '_')}_resume{file_extension}"

            st.subheader("📄 Candidate Resume (Preview)")

            # Provide a download button
            st.download_button(
                label="📥 Download Resume",
                data=response.content,
                file_name=file_name,
                mime=content_type
            )

            # Try to display preview based on content type
            if 'pdf' in content_type:
                try:
                    base64_pdf = base64.b64encode(response.content).decode('utf-8')
                    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf"></iframe>'
                    st.markdown(pdf_display, unsafe_allow_html=True)
                except:
                    st.info("PDF preview not available. Please download the file.")

            elif 'image' in content_type:
                try:
                    image = Image.open(BytesIO(response.content))
                    st.image(image, caption=f"{candidate_name}'s Resume", width=1000)
                except:
                    st.warning("⚠️ Could not display the resume image.")

            # Add notes section
            st.subheader("📝 Interview Notes")

            # Use URL as key for session state
            if f"notes_{resume_url}" not in st.session_state:
                st.session_state[f"notes_{resume_url}"] = ""

            notes = st.text_area(
                "Add your notes about this resume here. These will be saved for your reference.",
                value=st.session_state[f"notes_{resume_url}"],
                height=200,
                key=f"notes_input_{resume_url}"
            )

            # Save notes to session state when changed
            if notes != st.session_state[f"notes_{resume_url}"]:
                st.session_state[f"notes_{resume_url}"] = notes
                st.success("Notes saved!")

            return True

        else:
            st.warning(f"⚠️ Could not fetch resume from URL (Status code: {response.status_code}).")
            return False

    except Exception as e:
        st.warning(f"⚠️ Error fetching resume from URL: {str(e)}")
        return False

# Example usage
if __name__ == "__main__":
    st.set_page_config(
        page_title="Resume Handler Test",
        page_icon="📄",
        layout="wide"
    )

    st.title("Resume Handler Test")

    # Test with a local file
    st.subheader("Local File Test")
    if os.path.exists("data/resumes"):
        resume_files = [f for f in os.listdir("data/resumes") if os.path.isfile(os.path.join("data/resumes", f))]
        if resume_files:
            test_file = os.path.join("data/resumes", resume_files[0])
            display_resume(test_file, "Test Candidate")
        else:
            st.info("No resume files found in data/resumes directory.")
    else:
        st.info("data/resumes directory not found.")

    # Test with a Google Drive link
    st.subheader("Google Drive Link Test")
    test_drive_link = "https://drive.google.com/file/d/1234567890abcdef/view"
    st.text_input("Test Google Drive Link", value=test_drive_link, key="drive_link")
    if st.button("Test Drive Link"):
        display_resume(st.session_state.drive_link, "Drive Test Candidate")

    # Test with a direct URL
    st.subheader("Direct URL Test")
    test_url = "https://example.com/resume.pdf"
    st.text_input("Test Direct URL", value=test_url, key="direct_url")
    if st.button("Test Direct URL"):
        display_resume_from_url(st.session_state.direct_url, "URL Test Candidate")
