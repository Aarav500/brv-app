# CV Matching by Candidate ID Implementation

## Overview

This document outlines the implementation of CV matching by Candidate ID in the BRV Applicant Management System. The goal is to ensure that every CV (PDF) uploaded by a candidate is stored and matched based on their unique Candidate ID, rather than on name or email.

## Changes Made

### 1. CV Filename Standardization

All CVs are now stored with a standardized filename format:

```
CV_<CandidateID>.pdf
```

For example: `CV_20250719102731.pdf`

This ensures that every CV is uniquely identified and can be easily matched to a candidate record.

### 2. CV Storage Location

CVs are now stored in a dedicated `cvs` directory at the root of the project. This centralizes all CV files in one location, making them easier to manage.

### 3. CV Retrieval by Candidate ID

A new utility function `get_cv_by_candidate_id` has been implemented to retrieve a CV based on the Candidate ID. This function handles both local files and Google Drive links.

### 4. CV Display in the App

The app now displays CVs based on Candidate ID, with a download button that uses the standardized filename format.

### 5. Google Drive Integration

The Google Drive integration has been updated to use the standardized naming convention when storing CV files.

## How to Use

### Retrieving a CV by Candidate ID

```python
from utils import get_cv_by_candidate_id

# Get the CV path for a candidate
cv_path = get_cv_by_candidate_id(candidate_id)

if cv_path:
    # CV found
    print(f"CV found at: {cv_path}")
else:
    # CV not found
    print("CV not found for this candidate")
```

### Displaying a CV in the App

```python
from cv_display import display_cv_by_candidate_id

# Display the CV for a candidate
display_cv_by_candidate_id(candidate_id, candidate_name)
```

### Uploading a CV with Candidate ID

```python
from cv_display import cv_uploader_with_candidate_id

# Upload a CV for a candidate
cv_uploader_with_candidate_id(candidate_id)
```

## Implementation Details

### 1. CV Filename Standardization

The following files were modified to implement the standardized filename format:

- `app.py`: Updated the upload logic to rename files as `CV_<CandidateID>.pdf`
- `resume_handler.py`: Updated the upload logic to use the same naming convention
- `gatekeeper.py`: Updated the `match_cv_with_candidate_id` function to use the new naming convention

### 2. CV Storage Location

The following changes were made to centralize CV storage:

- Created a `cvs` directory at the root of the project
- Updated all file paths to use this directory

### 3. CV Retrieval by Candidate ID

A new utility function was added to `utils.py`:

```python
def get_cv_by_candidate_id(candidate_id):
    """
    Get the CV file path for a candidate based on their Candidate ID.
    
    Args:
        candidate_id (str): The candidate ID to search for
        
    Returns:
        str: Path to the CV file if found, None otherwise
    """
    if not candidate_id:
        return None
    
    # Standardized path format: cvs/CV_<CandidateID>.pdf
    cv_path = f"cvs/CV_{candidate_id}.pdf"
    
    # Check if the file exists
    if os.path.exists(cv_path):
        return cv_path
    
    # Backward compatibility checks...
    
    return None
```

### 4. CV Display in the App

A new file `cv_display.py` was created with functions for displaying and uploading CVs:

- `display_cv_by_candidate_id(candidate_id, candidate_name)`: Displays a CV based on the Candidate ID
- `cv_uploader_with_candidate_id(candidate_id)`: Uploads a CV and renames it based on the Candidate ID

### 5. Google Drive Integration

The `fetch_cv_from_google_drive` function in `utils.py` was updated to use the standardized naming convention when retrieving CV files from Google Drive.

## Backward Compatibility

The implementation includes backward compatibility to ensure that existing CVs can still be accessed:

- The `get_cv_by_candidate_id` function checks multiple locations and naming formats
- The `match_cv_with_candidate_id` function in `gatekeeper.py` also includes fallback logic

## Testing

To test the implementation:

1. Upload a CV using the new uploader
2. Verify that the file is saved with the correct naming format in the `cvs` directory
3. Retrieve the CV using the `get_cv_by_candidate_id` function
4. Display the CV in the app using the `display_cv_by_candidate_id` function
5. Test with existing CVs to ensure backward compatibility