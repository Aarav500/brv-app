# Controlled Editing Implementation

This document explains the implementation of two new features in the BRV Applicant Management System:

1. **Matching CVs with Form Entries via Candidate ID**
2. **Gatekeeper Form Logic (Receptionist Controlled Editing)**

## 1. Matching CVs with Form Entries via Candidate ID

### Overview

This feature allows the system to match CV files with Google Form entries using a unique Candidate ID. Each candidate is assigned a unique ID (e.g., CAND-001, CAND-002), which is used to name their CV file and link it to their form response.

### Implementation Details

- **CV Filename Format**: `CAND-001_CV.pdf` (where CAND-001 is the Candidate ID)
- **Storage Location**: All CVs are stored in the `data/resumes` directory
- **Matching Logic**: The system searches for CV files that start with the Candidate ID

### How It Works

1. When a candidate submits a form, they are assigned a unique Candidate ID
2. When their CV is uploaded, it is renamed to include their Candidate ID
3. The system can then match the CV with the form entry by searching for files that start with the Candidate ID

### Code Implementation

The matching functionality is implemented in the `match_cv_with_candidate_id` function in `gatekeeper.py`:

```python
def match_cv_with_candidate_id(candidate_id):
    """
    Match a CV file with a candidate ID by searching for files that start with that ID.
    
    Args:
        candidate_id (str): The candidate ID to search for
        
    Returns:
        str: Path to the CV file if found, None otherwise
    """
    if not candidate_id:
        return None
        
    # Check if the resumes directory exists
    if not os.path.exists("data/resumes"):
        return None
        
    # Get all files in the resumes directory
    resume_files = [f for f in os.listdir("data/resumes") if os.path.isfile(os.path.join("data/resumes", f))]
    
    # Look for files that start with the candidate ID
    matching_files = [f for f in resume_files if f.startswith(f"{candidate_id}_CV")]
    
    if matching_files:
        # Return the path to the first matching file
        return os.path.join("data/resumes", matching_files[0])
    
    return None
```

## 2. Gatekeeper Form Logic (Receptionist Controlled Editing)

### Overview

This feature allows receptionists to control who can edit their application form. The receptionist enters a Candidate ID and a secret passcode, and if valid, the system displays the edit link for the corresponding candidate's form.

### Implementation Details

- **Secret Passcode**: BRV123 (defined in `gatekeeper.py`)
- **Access Control**: Only receptionists with the correct passcode can retrieve edit links
- **Edit Link Storage**: Edit links are stored in the Google Sheet in a column named "Edit URL"

### How It Works

1. The receptionist navigates to the Gatekeeper Form in the receptionist interface
2. They enter the Candidate ID and the secret passcode
3. If the passcode is valid and the Candidate ID exists, the system displays the edit link
4. The receptionist can then share the edit link with the candidate or send it via email

### Code Implementation

The Gatekeeper Form is implemented in the `gatekeeper_form` function in `gatekeeper.py`:

```python
def gatekeeper_form():
    """
    Display the gatekeeper form for receptionist-controlled editing.
    """
    st.title("🔐 Gatekeeper Form")
    st.subheader("Control access to candidate form editing")
    
    st.markdown("""
    This form allows receptionists to control who can edit their application form.
    Enter the Candidate ID and the secret passcode to retrieve the edit link.
    """)
    
    # Create the form
    with st.form("gatekeeper_form"):
        candidate_id = st.text_input("Candidate ID", placeholder="e.g., CAND-001 or BRV2025_00123")
        passcode = st.text_input("Secret Passcode", type="password")
        
        submitted = st.form_submit_button("Verify and Get Edit Link")
    
    # Process the form submission
    if submitted:
        if not candidate_id:
            st.error("Please enter a Candidate ID")
        elif not passcode:
            st.error("Please enter the secret passcode")
        elif passcode != SECRET_PASSCODE:
            st.error("Invalid passcode. Please try again.")
        else:
            # Passcode is correct, try to get the edit URL
            success, result = get_edit_url_by_candidate_id(candidate_id)
            
            if success:
                edit_url = result
                st.success(f"✅ Access granted for Candidate ID: {candidate_id}")
                
                # Display the edit link
                st.markdown("### 🔗 Edit Link")
                st.markdown(f"[Edit your form here]({edit_url})")
                
                # Option to send the edit link via email
                # ...
```

## Setup Instructions

### 1. Setting up Google Form with Candidate IDs

1. Open your Google Form
2. Add a new question of type "Short answer"
3. Set the question title to "Candidate ID"
4. Make the question required
5. Add a description explaining the format (e.g., "Your unique candidate ID in the format CAND-XXX")

### 2. Setting up Google Apps Script for Edit URLs

1. Open your Google Sheet linked to the form
2. Go to Extensions > Apps Script
3. Copy and paste the code from `google_form_edit_urls.js`
4. Save and run the script

### 3. Matching CVs with Candidate IDs

1. When saving CVs, use the format: `CAND-XXX_CV.pdf`
2. Store all CVs in the `data/resumes` directory

## Receptionist Guide

### Accessing the Gatekeeper Form

1. Log in to the BRV Applicant Management System as a receptionist
2. In the navigation menu, select "Gatekeeper Form"

### Using the Gatekeeper Form

1. Enter the Candidate ID (e.g., CAND-001 or BRV2025_00123)
2. Enter the secret passcode (BRV123)
3. Click "Verify and Get Edit Link"
4. If valid, the edit link will be displayed
5. You can either:
   - Copy the edit link and share it with the candidate
   - Click "Send Edit Link via Email" to send it directly to the candidate's email

### Viewing Matching CVs

If a CV file matching the Candidate ID is found, it will be displayed in the "Matching CV Found" section. You can download the CV by clicking the "Download CV" button.

## Troubleshooting

### No Edit URL Found

If no edit URL is found for a candidate, ensure that:
1. The Google Form is set up correctly with the "Allow response editing" option enabled
2. The Google Apps Script is running and has added the "Edit URL" column to the Google Sheet
3. The candidate has submitted a form response

### No Matching CV Found

If no matching CV is found for a candidate, ensure that:
1. The CV file is named correctly with the format `CAND-XXX_CV.pdf`
2. The CV file is stored in the `data/resumes` directory
3. The Candidate ID entered matches the one used in the CV filename