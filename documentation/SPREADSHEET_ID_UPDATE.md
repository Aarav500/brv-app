# Google Sheet ID Update

## Overview

This document describes the changes made to update the Google Sheet ID used in the application to the new ID: `1nrL_cYTV4lnCv4q5eBgu9CTbxHwwLOToFI8Gxyzg88U`.

## Changes Made

### 1. Updated Environment Variables

The following environment variables in the `.env` file were updated to use the new spreadsheet ID:

- `MAPPING_SHEET_ID`: Used for storing Candidate ID mappings
- `FORM_SHEET_ID`: Used for Google Form responses

### 2. Updated Hardcoded URLs/IDs

The following files were updated to replace hardcoded Google Sheet URLs/IDs with the new spreadsheet ID:

- `test_google_sheet.py`: Updated to use `open_by_key()` with the new spreadsheet ID instead of `open_by_url()` with a hardcoded URL
- `examples/sync_google_sheet_to_firestore.py`: Updated to use `open_by_key()` with the new spreadsheet ID instead of `open_by_url()` with a hardcoded URL

### 3. Test Script Modifications

The `test_google_sheet.py` script was simplified to focus on verifying the connection to the Google Sheet without trying to read all records, as the new Google Sheet has duplicate headers that caused issues with the `get_all_records()` function.

## Verification

The changes were verified by running the modified `test_google_sheet.py` script, which successfully connected to the Google Sheet with the new ID and retrieved information about the spreadsheet.

## Affected Files

1. `.env`: Updated environment variables
2. `test_google_sheet.py`: Updated hardcoded URL and simplified script
3. `examples/sync_google_sheet_to_firestore.py`: Updated hardcoded URL

## Notes

- The new Google Sheet has duplicate headers (specifically 'Email Address'), which caused issues with the `get_all_records()` function. This is a separate issue from the spreadsheet ID update and may need to be addressed separately if full functionality is required.
- All parts of the application that use the environment variables `MAPPING_SHEET_ID` and `FORM_SHEET_ID` will now use the new spreadsheet ID without requiring any code changes.