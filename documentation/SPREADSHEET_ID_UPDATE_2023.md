# Google Sheet ID Update (2023)

## Overview

This document describes the changes made to update the Google Sheet ID used in the application to the new ID: `1V0Sf65ZVrebpopBfg2vwk-_PjRxgqlbytIX-L2GImAE` and to update the worksheet name from "Form Responses 1" to "Form Responses 2".

## Changes Made

### 1. Updated Environment Variables

The following environment variables in the `.env` file were updated to use the new spreadsheet ID:

- `MAPPING_SHEET_ID`: Used for storing Candidate ID mappings
- `FORM_SHEET_ID`: Used for Google Form responses

### 2. Updated Hardcoded URLs/IDs

The following files were updated to replace hardcoded Google Sheet URLs/IDs with the new spreadsheet ID:

- `examples/sync_google_sheet_to_firestore.py`: Updated to use the new spreadsheet ID
- `test_google_sheet.py`: Updated to use the new spreadsheet ID

### 3. Updated Worksheet Names

The following files were updated to use the new worksheet name "Form Responses 2" instead of "Form Responses 1":

- `utils.py`: Updated worksheet name in `fetch_google_form_responses` function
- `utils_update.py`: Updated worksheet name in `update_google_sheet_by_candidate_id` function
- `utils_update.py`: Updated worksheet name in `get_google_sheet_row_by_candidate_id` function
- `google_form_edit_urls.js`: Updated worksheet name in `generateEditUrls` function

### 4. Test Script Modifications

The changes were tested by running:

1. `test_google_sheet.py`: Verified connection to the new spreadsheet and confirmed the worksheet name is "Form Responses 2"
2. `examples/sync_google_sheet_to_firestore.py`: Verified the script can read data from the new spreadsheet and sync it to Firestore

## Verification

The changes were verified by running the test scripts mentioned above. Both scripts successfully connected to the new spreadsheet and performed their intended functions.

## Affected Files

1. `.env`: Updated environment variables
2. `examples/sync_google_sheet_to_firestore.py`: Updated spreadsheet ID
3. `test_google_sheet.py`: Updated spreadsheet ID
4. `utils.py`: Updated worksheet name
5. `utils_update.py`: Updated worksheet name in two functions
6. `google_form_edit_urls.js`: Updated worksheet name

## Notes

- The `google_form_edit_urls.js` file contains a JavaScript error (attempting to reassign a const variable on line 27), but this is an issue with the original code, not with the changes made. This file is a Google Apps Script that needs to be manually deployed to the Google Sheet, so it's not directly executed by our Python application.
- The new Google Sheet has a worksheet named "Form Responses 2", which matches the worksheet name mentioned in the issue description (with a space instead of an underscore).
- All parts of the application that use the environment variables `MAPPING_SHEET_ID` and `FORM_SHEET_ID` will now use the new spreadsheet ID without requiring any code changes.
- The application was tested and confirmed to work correctly with the new spreadsheet ID and worksheet name.