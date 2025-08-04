# Column Name Detection Update

## Issue Description

The application was encountering the following error:

```
The 'Full Name( First-middle-last)' column was not found in the Google Sheet data.
```

This error occurred because the application was expecting a column with the exact name "Full Name( First-middle-last)" in the Google Sheet, but the actual sheet had a column named "Full Name" instead.

## Changes Made

### 1. Updated Full Name Column Detection in `receptionist.py`

The code in `receptionist.py` was modified to use a more flexible approach for finding the full name column. Instead of requiring an exact match for "Full Name( First-middle-last)", it now:

1. Tries multiple possible column names in order: "Full Name( First-middle-last)", "Full Name", "Name"
2. If none of these exact columns are found, it uses the `find_matching_column` function from `utils.py` to find the best matching column name based on normalized names
3. If still no matching column is found, it shows a clear error message and returns
4. Adds an informational message to show which column is being used as the full name column

**Before:**
```python
# Use the exact column name for "Full Name" as specified
name_column = "Full Name( First-middle-last)"
if name_column not in form_df.columns:
    st.error(f"❌ The '{name_column}' column was not found in the Google Sheet data.")
    st.write("Available columns:", form_df.columns.tolist())
    st.warning("Please ensure the Google Sheet has all required columns with exact names.")
    return
```

**After:**
```python
# Try multiple possible column names for the full name field
possible_name_columns = ["Full Name( First-middle-last)", "Full Name", "Name"]
name_column = None

for col in possible_name_columns:
    if col in form_df.columns:
        name_column = col
        break

# If none of the possible columns are found, try using find_matching_column
if name_column is None:
    from utils import find_matching_column
    name_column = find_matching_column(form_df.columns, "Full Name")

# If still no matching column, show error and return
if name_column is None:
    st.error("❌ No suitable column for full name was found in the Google Sheet data.")
    st.write("Available columns:", form_df.columns.tolist())
    st.warning("Please ensure the Google Sheet has a column for full name (e.g., 'Full Name', 'Name').")
    return

st.info(f"Using '{name_column}' as the full name column.")
```

### 2. Other Column Names

Other column names like "Email Address" and "Phone number" were already being handled in a way that gracefully handles missing columns:

```python
email = selected_applicant.get("Email Address", "")
phone = selected_applicant.get("Phone number", "")
```

These uses of the `.get()` method with a default value ensure that the code doesn't fail if the column is not found.

## How It Works

The updated code uses a multi-step approach to find the best matching column for the full name:

1. **Exact Match**: First, it tries to find an exact match for any of the predefined column names: "Full Name( First-middle-last)", "Full Name", or "Name".

2. **Normalized Match**: If no exact match is found, it uses the `find_matching_column` function from `utils.py`, which normalizes column names by removing spaces, underscores, parentheses, and converting to lowercase. This helps match column names that might have slight variations.

3. **Fallback**: If still no matching column is found, it shows a clear error message and returns.

## Testing

To test these changes, you can:

1. **Test with "Full Name( First-middle-last)" column**: The application should work as before.

2. **Test with "Full Name" column**: The application should now use this column instead of showing an error.

3. **Test with "Name" column**: The application should now use this column if neither "Full Name( First-middle-last)" nor "Full Name" are present.

4. **Test with a similar column name**: If you have a column with a name like "Full_Name" or "FullName", the application should be able to match it using the normalized name matching.

5. **Test with no matching column**: The application should show a clear error message and return.

## Benefits

This update makes the application more robust and user-friendly by:

1. **Flexibility**: Supporting multiple column name variations instead of requiring an exact match.

2. **Transparency**: Showing which column is being used as the full name column.

3. **Graceful Degradation**: Providing clear error messages if no suitable column is found.

## Affected Files

1. `receptionist.py`: Updated to use a more flexible approach for finding the full name column.

## Conclusion

This update addresses the issue described in the issue description by making the application more flexible in how it detects column names. It now supports variations like "Full Name", "Full Name (First-middle-last)", or "Name", and falls back gracefully if none of these columns are found.