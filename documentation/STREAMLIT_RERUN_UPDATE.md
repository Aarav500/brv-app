# Streamlit Rerun Update

## Issue Description

The application was encountering the following error:

```
AttributeError: module 'streamlit' has no attribute 'experimental_rerun'
```

This error occurred because `st.experimental_rerun()` is deprecated or removed in newer versions of Streamlit. As of recent versions, Streamlit moved `st.experimental_rerun()` to `st.rerun()` officially.

## Changes Made

All occurrences of `st.experimental_rerun()` were replaced with `st.rerun()` in the codebase.

### Files Modified

1. `receptionist_panel.py`: 4 occurrences of `st.experimental_rerun()` were replaced with `st.rerun()`

### Specific Changes

In `receptionist_panel.py`:

1. Line 247: Used to refresh the page after successfully assigning a Candidate ID to a file in the `display_manual_id_assignment()` function.
2. Line 316: Used to refresh the page after assigning a Candidate ID to a manually selected file in the `display_manual_id_assignment()` function.
3. Line 331: Used to refresh the page when the user clicks the "Refresh Data" button in the `receptionist_panel()` function.
4. Line 479: Used for auto-refreshing the page every 5 minutes when the auto-refresh option is enabled in the `receptionist_panel()` function.

## Verification

The changes were verified by ensuring that all occurrences of `st.experimental_rerun()` were replaced with `st.rerun()` in the codebase. This is the recommended approach according to Streamlit's documentation, as `st.rerun()` is the official replacement for the deprecated `st.experimental_rerun()` function.

## Alternative Approach

For applications that need to support both older and newer versions of Streamlit, a more robust approach would be to use a try-except block:

```python
try:
    st.rerun()
except AttributeError:
    st.experimental_rerun()
```

However, since most applications should be using the latest version of Streamlit, the simpler approach of directly using `st.rerun()` was chosen.

## Conclusion

This update ensures that the application works correctly with newer versions of Streamlit by using the current API for page reloading.