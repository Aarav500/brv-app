import streamlit as st
import pandas as pd
import time
import os
from mysql_db import get_all_candidates, get_candidate_by_id, search_candidates, update_candidate
from cloud_storage import download_cv

def check_cv_status(candidate_id):
    """
    Check if a CV exists for the given Candidate ID.
    Checks if the candidate has a resume_url in the MySQL database.
    
    Args:
        candidate_id (int): The Candidate ID to check
        
    Returns:
        bool: True if CV exists, False otherwise
    """
    if not candidate_id:
        return False
    
    try:
        # Convert candidate_id to integer if it's a string
        if isinstance(candidate_id, str):
            candidate_id = int(candidate_id)
        
        # Get candidate from MySQL database
        candidate = get_candidate_by_id(candidate_id)
        
        # Check if candidate has a resume_url
        if candidate and candidate.get('resume_url'):
            return True
        
        return False
    except ValueError:
        # If candidate_id is not a valid integer
        return False
    except Exception as e:
        print(f"Error checking CV status: {e}")
        return False

def get_edit_link_button(candidate_id):
    """
    Create an edit link button for the given Candidate ID.
    
    Args:
        candidate_id (str): The Candidate ID to get the edit link for
        
    Returns:
        str: HTML for the edit link button or a message if not available
    """
    if not candidate_id:
        return "No ID"
    
    success, result = get_edit_link_by_candidate_id(candidate_id)
    
    if success:
        return f'<a href="{result}" target="_blank" style="text-decoration: none;"><button style="background-color: #4CAF50; color: white; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer;">Edit Form</button></a>'
    else:
        return "Not available"

def add_remarks(candidate_id, remarks):
    """
    Add remarks for a candidate and store in session state.
    
    Args:
        candidate_id (str): The Candidate ID to add remarks for
        remarks (str): The remarks to add
    """
    if "candidate_remarks" not in st.session_state:
        st.session_state.candidate_remarks = {}
    
    # Skip adding remarks if candidate_id is empty or None
    if not candidate_id:
        return
    
    st.session_state.candidate_remarks[candidate_id] = remarks

def get_remarks(candidate_id):
    """
    Get remarks for a candidate from session state.
    
    Args:
        candidate_id (str): The Candidate ID to get remarks for
        
    Returns:
        str: The remarks for the candidate or an empty string if not found
    """
    if "candidate_remarks" not in st.session_state:
        st.session_state.candidate_remarks = {}
    
    return st.session_state.candidate_remarks.get(candidate_id, "")

def display_manual_id_assignment():
    """
    Display the UI for manual Candidate ID assignment with time-based matching.
    """
    st.subheader("Manual Candidate ID Assignment")
    st.markdown("Assign Candidate IDs to CV files in Google Drive using time-based matching")
    
    # Set up credentials
    drive_service, sheet_client = setup_credentials()
    if not drive_service or not sheet_client:
        st.error("Failed to set up credentials. Please check your Google API configuration.")
        return
    
    # Get the Drive folder ID from environment variables
    drive_folder_id = os.getenv('DRIVE_FOLDER_ID')
    if not drive_folder_id:
        st.error("DRIVE_FOLDER_ID environment variable is not set. Please check your .env file.")
        return
    
    # List files in the Drive folder
    with st.spinner("Fetching files from Google Drive..."):
        files = list_drive_files(drive_service, drive_folder_id)
    
    if not files:
        st.warning("No files found in the specified Google Drive folder.")
        return
    
    # Get existing mappings
    sheet_id = os.getenv('MAPPING_SHEET_ID')
    if not sheet_id:
        st.error("MAPPING_SHEET_ID environment variable is not set. Please check your .env file.")
        return
    
    sheet_name = os.getenv('MAPPING_SHEET_NAME', 'Candidate ID Mapping')
    
    try:
        spreadsheet = sheet_client.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        existing_data = worksheet.get_all_records()
        existing_file_ids = {row['Google Drive File ID']: row['Candidate ID'] for row in existing_data}
        existing_candidate_ids = [row['Candidate ID'] for row in existing_data]
    except Exception as e:
        st.error(f"Error getting existing mappings: {e}")
        return
    
    # Filter out files that already have Candidate IDs assigned
    unassigned_files = [f for f in files if f['id'] not in existing_file_ids]
    
    if not unassigned_files:
        st.success("All files in the Drive folder have been assigned Candidate IDs.")
        return
    
    # Fetch form submissions
    with st.spinner("Fetching form submissions..."):
        from utils import fetch_google_form_responses, match_cvs_with_form_submissions
        form_df = fetch_google_form_responses(force_refresh=False)
    
    if form_df.empty:
        st.warning("No form submissions found. Please check your Google Sheet configuration.")
        # Continue with manual assignment without matching
    else:
        # Match form submissions with CV uploads
        with st.spinner("Matching form submissions with CV uploads..."):
            matches = match_cvs_with_form_submissions(form_df, unassigned_files)
        
        if matches:
            st.success(f"Found {len(matches)} potential matches between form submissions and CV uploads.")
            
            # Display matches in tabs
            st.subheader("Potential Matches")
            
            # Create tabs for each form submission with matches
            tabs = st.tabs([f"Submission {i+1}" for i in range(len(matches))])
            
            for i, (tab, match) in enumerate(zip(tabs, matches)):
                with tab:
                    form_data = match['form_data']
                    potential_matches = match['potential_matches']
                    
                    # Find name and email columns
                    name_col = next((col for col in form_data.index if 'name' in col.lower()), None)
                    email_col = next((col for col in form_data.index if 'email' in col.lower()), None)
                    timestamp_col = next((col for col in form_data.index if 'timestamp' in col.lower()), None)
                    
                    # Display form submission details
                    st.markdown("### Form Submission Details")
                    if name_col:
                        st.markdown(f"**Name:** {form_data[name_col]}")
                    if email_col:
                        st.markdown(f"**Email:** {form_data[email_col]}")
                    if timestamp_col:
                        st.markdown(f"**Submitted:** {form_data[timestamp_col]}")
                    
                    # Display other form fields in an expander
                    with st.expander("View all form fields"):
                        for field, value in form_data.items():
                            if field not in [name_col, email_col, timestamp_col]:
                                st.markdown(f"**{field}:** {value}")
                    
                    # Display potential CV matches
                    st.markdown("### Potential CV Matches")
                    
                    for j, match_data in enumerate(potential_matches):
                        cv_file = match_data['cv_file']
                        confidence = match_data['confidence']
                        time_diff = match_data['time_difference_hours']
                        
                        # Create a colored box based on confidence
                        if confidence >= 0.7:
                            box_color = "rgba(0, 255, 0, 0.1)"  # Green for high confidence
                        elif confidence >= 0.5:
                            box_color = "rgba(255, 255, 0, 0.1)"  # Yellow for medium confidence
                        else:
                            box_color = "rgba(255, 165, 0, 0.1)"  # Orange for low confidence
                        
                        # Display match in a colored box
                        st.markdown(f"""
                        <div style="background-color: {box_color}; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                            <h4>Match {j+1} - Confidence: {confidence:.2f}</h4>
                            <p><strong>File Name:</strong> {cv_file['name']}</p>
                            <p><strong>Uploaded:</strong> {cv_file.get('createdTime', 'Unknown')}</p>
                            <p><strong>Time Difference:</strong> {time_diff:.2f} hours</p>
                            <p><a href="{cv_file.get('webViewLink', '#')}" target="_blank">View in Google Drive</a></p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Add a button to assign this CV to the candidate
                        col1, col2 = st.columns([1, 2])
                        with col1:
                            # Input for Candidate ID
                            candidate_id = st.text_input(
                                "Enter Candidate ID (CAND-XXXX)",
                                key=f"candidate_id_input_{i}_{j}",
                                help="Candidate ID must be in the format CAND-XXXX, e.g., CAND-0001"
                            )
                        
                        with col2:
                            # Checkbox for renaming the file
                            rename_file = st.checkbox(
                                "Rename file to BRV-CID-XXXX format",
                                value=True,
                                key=f"rename_checkbox_{i}_{j}"
                            )
                        
                        # Validate and assign
                        if candidate_id:
                            if not is_valid_candidate_id(candidate_id):
                                st.error("Invalid Candidate ID format. Must be in the format CAND-XXXX.")
                            elif candidate_id in existing_candidate_ids:
                                st.error(f"Candidate ID {candidate_id} is already in use.")
                            else:
                                if st.button("Confirm Match & Assign ID", key=f"assign_button_{i}_{j}"):
                                    with st.spinner("Assigning Candidate ID..."):
                                        success, message = assign_manual_candidate_id(
                                            cv_file['id'],
                                            cv_file['name'],
                                            candidate_id,
                                            rename_file=rename_file
                                        )
                                    
                                    if success:
                                        st.success(message)
                                        # Clear the selection and refresh the list
                                        st.rerun()
                                    else:
                                        st.error(message)
    
    # Display unmatched files for manual assignment
    st.subheader("Manual Assignment (Unmatched Files)")
    st.markdown(f"Found {len(unassigned_files)} unassigned files in Google Drive")
    
    # Create a selectbox to choose a file
    file_options = [f"{f['name']} ({f['id']})" for f in unassigned_files]
    selected_file = st.selectbox("Select a file to assign a Candidate ID", file_options, key="file_select")
    
    if selected_file:
        # Extract the file ID from the selected option
        selected_file_id = selected_file.split("(")[-1].split(")")[0]
        selected_file_name = selected_file.split(" (")[0]
        
        # Find the file object
        selected_file_obj = next((f for f in unassigned_files if f['id'] == selected_file_id), None)
        
        if selected_file_obj:
            st.markdown(f"**Selected File:** {selected_file_obj['name']}")
            
            # Display file details
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Created:** {selected_file_obj.get('createdTime', 'Unknown')}")
            with col2:
                st.markdown(f"**Modified:** {selected_file_obj.get('modifiedTime', 'Unknown')}")
            
            # Display a preview of the file if possible
            st.markdown(f"[View File in Google Drive]({selected_file_obj['webViewLink']})")
            
            # Input for manual Candidate ID entry
            candidate_id = st.text_input(
                "Enter Candidate ID (format: CAND-XXXX)",
                key="candidate_id_input",
                help="Candidate ID must be in the format CAND-XXXX, e.g., CAND-0001"
            )
            
            # Checkbox for renaming the file
            rename_file = st.checkbox(
                "Rename file to BRV-CID-XXXX format",
                value=True,
                key="rename_checkbox"
            )
            
            # Validate the Candidate ID
            if candidate_id:
                if not is_valid_candidate_id(candidate_id):
                    st.error("Invalid Candidate ID format. Must be in the format CAND-XXXX.")
                elif candidate_id in existing_candidate_ids:
                    st.error(f"Candidate ID {candidate_id} is already in use.")
                else:
                    # Assign the Candidate ID
                    if st.button("Assign Candidate ID", key="assign_id_button"):
                        with st.spinner("Assigning Candidate ID..."):
                            success, message = assign_manual_candidate_id(
                                selected_file_id,
                                selected_file_obj['name'],
                                candidate_id,
                                rename_file=rename_file
                            )
                        
                        if success:
                            st.success(message)
                            # Clear the selection and refresh the list
                            st.session_state.file_select = None
                            st.session_state.candidate_id_input = ""
                            st.rerun()
                        else:
                            st.error(message)

def receptionist_panel():
    """
    Display the Receptionist Panel with Candidate ID integration.
    """
    st.title("Receptionist Panel")
    st.subheader("Candidate Management")
    
    # Add refresh button and auto-refresh option
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("🔄 Refresh Data", key="refresh_button"):
            st.rerun()
    
    with col2:
        auto_refresh = st.checkbox("Auto-refresh every 5 minutes", value=False, key="auto_refresh")
    
    # Add manual Candidate ID assignment section
    with st.expander("Manual Candidate ID Assignment", expanded=False):
        display_manual_id_assignment()
    
    # Add filter options
    st.subheader("Filter Options")
    filter_col1, filter_col2 = st.columns(2)
    
    with filter_col1:
        filter_by_id = st.text_input("Filter by Candidate ID (e.g., CAND-)", key="filter_id")
    
    with filter_col2:
        filter_by_name = st.text_input("Filter by Name", key="filter_name")
    
    # Fetch data from Google Sheets
    with st.spinner("Fetching candidate data..."):
        df = fetch_google_form_responses(force_refresh=False)
    
    if df.empty:
        st.error("No candidate data found. Please check your Google Sheet configuration.")
        return
    
    # Find the relevant columns
    name_col = None
    email_col = None
    phone_col = None
    candidate_id_col = None
    
    for col in df.columns:
        if 'name' in col.lower():
            name_col = col
        elif 'email' in col.lower():
            email_col = col
        elif 'phone' in col.lower() or 'mobile' in col.lower():
            phone_col = col
        elif 'candidate id' in col.lower() or 'application id' in col.lower():
            candidate_id_col = col
    
    # If Candidate ID column is not found, try to find it in column Z
    if not candidate_id_col:
        if len(df.columns) >= 26:  # Check if column Z exists
            z_col = df.columns[25]  # Column Z (0-indexed)
            candidate_id_col = z_col
            st.info(f"Using column {z_col} as Candidate ID column")
    
    # If still not found, create a temporary Candidate ID column
    if not candidate_id_col:
        df['Candidate ID'] = [f"BRV-{i+1:04d}" for i in range(len(df))]
        candidate_id_col = 'Candidate ID'
        st.warning("No Candidate ID column found. Created temporary IDs.")
    
    # Ensure we have the necessary columns
    if not name_col:
        st.error("No name column found in the data.")
        return
    
    if not email_col:
        st.error("No email column found in the data.")
        return
    
    if not phone_col:
        # Create a dummy phone column if not found
        df['Phone Number'] = ""
        phone_col = 'Phone Number'
        st.warning("No phone column found in the data.")
    
    # Create a new DataFrame with just the columns we need
    display_df = pd.DataFrame({
        'Candidate Name': df[name_col],
        'Email ID': df[email_col],
        'Phone Number': df[phone_col],
        'Candidate ID': df[candidate_id_col]
    })
    
    # Apply filters
    if filter_by_id:
        display_df = display_df[display_df['Candidate ID'].str.contains(filter_by_id, case=False, na=False)]
    
    if filter_by_name:
        display_df = display_df[display_df['Candidate Name'].str.contains(filter_by_name, case=False, na=False)]
    
    # Sort by Candidate ID
    display_df = display_df.sort_values('Candidate ID')
    
    # Add CV status and Edit Link columns
    display_df['CV Status'] = display_df['Candidate ID'].apply(
        lambda x: "✅" if check_cv_status(x) else "❌"
    )
    
    # Create the main table
    st.subheader("Candidate List")
    st.markdown(f"Showing {len(display_df)} candidates")
    
    # Create an expander for each candidate
    for i, row in display_df.iterrows():
        candidate_id = row['Candidate ID']
        candidate_name = row['Candidate Name']
        email = row['Email ID']
        phone = row['Phone Number']
        cv_status = row['CV Status']
        
        # Get edit link and remarks
        edit_link_html = get_edit_link_button(candidate_id)
        current_remarks = get_remarks(candidate_id)
        
        # Create an expander for each candidate
        with st.expander(f"{candidate_name} ({candidate_id}) - CV: {cv_status}"):
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                st.markdown(f"**Email:** {email}")
                st.markdown(f"**Phone:** {phone}")
            
            with col2:
                st.markdown(f"**Candidate ID:** {candidate_id}")
                st.markdown(f"**CV Status:** {cv_status}")
            
            with col3:
                st.markdown(edit_link_html, unsafe_allow_html=True)
            
            # Add remarks section
            st.markdown("**Remarks:**")
            # Ensure unique key by using index as fallback if candidate_id is empty or null
            safe_candidate_id = candidate_id if candidate_id else f"NA_{i}"
            new_remarks = st.text_area("", value=current_remarks, key=f"remarks_{safe_candidate_id}")
            
            if new_remarks != current_remarks:
                add_remarks(candidate_id, new_remarks)
                st.success("Remarks updated!")
    
    # Create a table view as well
    st.subheader("Table View")
    
    # Add Edit Link and Remarks columns to the display DataFrame
    table_df = display_df.copy()
    table_df['Edit Link'] = "Available"  # Placeholder, we'll use buttons in the expander view
    table_df['Remarks'] = table_df['Candidate ID'].apply(lambda x: get_remarks(x)[:20] + "..." if len(get_remarks(x)) > 20 else get_remarks(x))
    
    st.dataframe(table_df)
    
    # Auto-refresh logic
    if auto_refresh:
        time.sleep(300)  # 5 minutes
        st.rerun()

if __name__ == "__main__":
    receptionist_panel()