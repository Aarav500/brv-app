# Time-Based CV Matching

## Overview

This document describes the time-based CV matching functionality implemented in the BRV Walk-in System. This feature allows receptionists to match CV uploads in Google Drive with form submissions based on timestamps, names, and emails.

## How It Works

### Matching Algorithm

The system uses a sophisticated matching algorithm that considers multiple factors:

1. **Time Proximity**: The primary matching criterion is the time difference between form submission and CV upload. Files uploaded close to the form submission time are more likely to be matches.

2. **Name Similarity**: The system compares the candidate's name from the form with the filename of the CV. Higher similarity scores increase the match confidence.

3. **Email Detection**: If the candidate's email appears in the filename, this significantly increases the match confidence.

These factors are combined into a confidence score that indicates how likely a CV belongs to a particular candidate.

### Confidence Scoring

Confidence scores range from 0.0 to 1.0:

- **High Confidence (0.7-1.0)**: Shown in green. Very likely to be the correct match.
- **Medium Confidence (0.5-0.7)**: Shown in yellow. Probably the correct match, but verify.
- **Low Confidence (0.3-0.5)**: Shown in orange. Possible match, but requires careful verification.

## Receptionist Workflow

### 1. Accessing the CV Matching Interface

1. Navigate to the "Candidate ID Panel" in the receptionist view.
2. Click on the "Manual Candidate ID Assignment" expander.

### 2. Viewing Potential Matches

The system will automatically:

1. Fetch form submissions from Google Sheets.
2. Fetch CV uploads from Google Drive.
3. Match form submissions with CV uploads based on timestamps, names, and emails.
4. Display potential matches in a tabbed interface.

Each tab represents a form submission with potential CV matches. For each match, you'll see:

- Form submission details (name, email, timestamp)
- Potential CV matches with confidence scores
- File details (name, upload time, time difference)
- A link to view the file in Google Drive

### 3. Assigning Candidate IDs

For each potential match:

1. Enter a Candidate ID in the format CAND-XXXX (e.g., CAND-0001).
2. Choose whether to rename the file to BRV-CID-XXXX format.
3. Click "Confirm Match & Assign ID" to assign the ID and update the mapping.

### 4. Manual Assignment

If the system doesn't find a match, or if you need to assign an ID to a file that wasn't matched:

1. Scroll down to the "Manual Assignment (Unmatched Files)" section.
2. Select a file from the dropdown.
3. Enter a Candidate ID.
4. Choose whether to rename the file.
5. Click "Assign Candidate ID" to assign the ID and update the mapping.

## Best Practices

### For Receptionists

1. **Verify High-Confidence Matches**: Even for high-confidence matches (green), quickly verify that the name and timing make sense before assigning an ID.

2. **Check File Contents**: For medium or low confidence matches, open the file in Google Drive to verify its contents before assigning an ID.

3. **Consider Timing**: Pay attention to the time difference between form submission and CV upload. A smaller time difference usually indicates a better match.

4. **Use Consistent Naming**: When manually assigning IDs, use the BRV-CID-XXXX format for consistency.

5. **Batch Processing**: Process matches in batches during quiet periods rather than one at a time during busy periods.

### For Candidates

Instruct candidates to:

1. **Upload Immediately**: Upload their CV to Google Drive immediately after submitting the form.

2. **Include Name in Filename**: Save their CV with their full name in the filename (e.g., "John_Smith_Resume.pdf").

3. **Include Email in Filename**: Optionally include their email in the filename for better matching.

## Troubleshooting

### Common Issues

1. **No Matches Found**: 
   - Check if the form submissions are being correctly fetched from Google Sheets.
   - Verify that the Google Drive folder ID is correctly set in the .env file.
   - Ensure that candidates are uploading their CVs to the correct folder.

2. **Low Confidence Scores**:
   - Large time gaps between form submission and CV upload can result in low confidence scores.
   - Filenames that don't include the candidate's name or email will have lower confidence scores.
   - Encourage candidates to follow the naming conventions and upload timing guidelines.

3. **File Renaming Fails**:
   - Check that the Google service account has write permissions for the Google Drive folder.
   - Verify that the Google API credentials are correctly set up.
   - Check the logs for specific error messages.

4. **Duplicate Candidate IDs**:
   - The system prevents assigning the same Candidate ID twice.
   - If you need to reassign an ID, you'll need to manually update the mapping sheet.

### Technical Troubleshooting

If the matching system isn't working correctly:

1. Check the `.env` file to ensure all required environment variables are set:
   - `DRIVE_FOLDER_ID`: ID of the Google Drive folder containing CV uploads
   - `MAPPING_SHEET_ID`: ID of the Google Sheet for storing Candidate ID mappings
   - `FORM_SHEET_ID`: ID of the Google Sheet containing form responses

2. Verify that the Google service account has the necessary permissions:
   - Read access to the form responses sheet
   - Read/write access to the mapping sheet
   - Read/write access to the Google Drive folder

3. Run the test script to verify the matching algorithm is working correctly:
   ```
   python test_cv_matching.py
   ```

## Technical Details

### File Renaming

When a Candidate ID is assigned to a CV file, the system can optionally rename the file in Google Drive to follow the format:

```
BRV-CID-CAND-XXXX.pdf
```

This makes it easy to identify files that have been processed and assigned a Candidate ID.

### Mapping Storage

The mapping between Candidate IDs and Google Drive file IDs is stored in a Google Sheet with the following columns:

| Candidate ID | File Name | Google Drive File ID |
|--------------|-----------|----------------------|
| CAND-0001    | BRV-CID-CAND-0001.pdf | 1a2b3c4d5e6f7g8h9i |
| CAND-0002    | BRV-CID-CAND-0002.pdf | 2b3c4d5e6f7g8h9i0j |

This mapping is used to retrieve CVs by Candidate ID throughout the system.

## Conclusion

The time-based CV matching functionality streamlines the process of matching CV uploads with form submissions, making it easier for receptionists to assign Candidate IDs and manage walk-in candidates. By leveraging timestamps, name similarity, and email detection, the system can automatically suggest matches with confidence scores, reducing manual effort and potential errors.