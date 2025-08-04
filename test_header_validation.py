#!/usr/bin/env python3
"""
Test script to verify the strict header validation logic in utils.py.
"""

import sys
import logging
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_header_validation():
    """
    Test the strict header validation logic in utils.py.
    """
    logger.info("Testing strict header validation logic...")
    
    try:
        # Import the function
        from utils import fetch_google_form_responses
        logger.info("Successfully imported fetch_google_form_responses from utils")
        
        # Test both scenarios: matching headers and missing headers
        import utils
        original_func = utils.fetch_google_form_responses
        
        # First test: Missing headers scenario
        # Create a mock DataFrame with missing columns to test validation
        mock_data_missing = {
            "Timestamp": ["2023-01-01 12:00:00"],
            "Email Address": ["test@example.com"],
            # Missing "Full Name( First-middle-last)" column
            "Current Address": ["123 Main St"],
            # Missing other required columns
        }
        mock_df_missing = pd.DataFrame(mock_data_missing)
        
        # Create a mock DataFrame with all required headers
        mock_data_complete = {
            "Timestamp": ["2023-01-01 12:00:00"],
            "Email Address": ["test@example.com"],
            "Full Name( First-middle-last)": ["John Doe"],
            "Current Address": ["123 Main St"],
            "Permanent Address": ["456 Oak Ave"],
            "Phone number": ["1234567890"],
            "Additional Phone Number (NA if none)": ["NA"],
            "Date Of birth": ["1990-01-01"],
            "Caste": ["General"],
            "Sub Caste": ["NA"],
            "Marital Status": ["Single"],
            "Highest Qualification": ["Bachelor's"],
            "Work Experience ": ["2 years"],
            "Referral ": ["None"],
            "Upload your Resume": ["https://example.com/resume.pdf"]
        }
        mock_df_complete = pd.DataFrame(mock_data_complete)
        
        # Flag to control which mock data to use
        use_missing_headers = True
        
        def mock_fetch(*args, **kwargs):
            nonlocal use_missing_headers
            if use_missing_headers:
                logger.info("Using mock data with missing headers")
                return mock_df_missing
            else:
                logger.info("Using mock data with complete headers")
                return mock_df_complete
        
        # Replace the function temporarily
        utils.fetch_google_form_responses = mock_fetch
        
        # Test the validation logic directly without using receptionist module
        try:
            # Create a streamlit mock to avoid dependency
            import sys
            import importlib
            
            # Mock streamlit
            class SessionState(dict):
                def __setattr__(self, key, value):
                    self[key] = value
                
                def __getattr__(self, key):
                    if key in self:
                        return self[key]
                    raise AttributeError(f"'{type(self).__name__}' object has no attribute '{key}'")
            
            class MockStreamlit:
                def __init__(self):
                    self.session_state = SessionState()
                
                def error(self, msg):
                    logger.info(f"Mock streamlit error: {msg}")
                
                def warning(self, msg):
                    logger.info(f"Mock streamlit warning: {msg}")
                
                def write(self, *args, **kwargs):
                    pass
                
                def dataframe(self, *args, **kwargs):
                    pass
                
                def expander(self, *args, **kwargs):
                    return self
                
                def __enter__(self):
                    return self
                
                def __exit__(self, *args):
                    pass
                
                def success(self, *args, **kwargs):
                    pass
            
            # Add mock to sys.modules
            sys.modules['streamlit'] = MockStreamlit()
            
            # Reload utils to use our mock
            importlib.reload(utils)
            
            # Test both scenarios: missing headers and complete headers
            
            # Scenario 1: Missing headers
            logger.info("Testing scenario 1: Missing headers")
            use_missing_headers = True
            
            # Create a flag to track if the error was detected
            error_detected = False
            
            # Define a custom error handler to capture the error
            def custom_error(msg):
                nonlocal error_detected
                logger.info(f"Mock streamlit error: {msg}")
                if "Missing required columns" in msg:
                    error_detected = True
            
            # Replace the error method in our mock
            sys.modules['streamlit'].error = custom_error
            
            # Test the missing headers scenario
            try:
                # This should trigger validation errors that will be caught by our custom error handler
                utils.fetch_google_form_responses()
                
                # Check if the error was detected
                if not error_detected:
                    logger.error("❌ Test failed: No error was detected for missing columns")
                    return False
                else:
                    logger.info("✅ Test passed: Correctly detected missing columns")
            except ValueError as e:
                # If a ValueError is raised directly, that's also a success
                if "Missing required columns" in str(e):
                    logger.info("✅ Test passed: Correctly detected missing columns")
                    logger.info(f"Error message: {e}")
                else:
                    logger.error(f"❌ Test failed: Unexpected error: {e}")
                    return False
            
            # Scenario 2: Complete headers
            logger.info("Testing scenario 2: Complete headers")
            use_missing_headers = False
            error_detected = False  # Reset the flag
            
            # Test the complete headers scenario
            try:
                # This should NOT trigger validation errors
                result_df = utils.fetch_google_form_responses()
                
                # Check if the error was detected (it shouldn't be)
                if error_detected:
                    logger.error("❌ Test failed: Error was detected for complete headers")
                    return False
                else:
                    logger.info("✅ Test passed: No error was detected for complete headers")
                    
                # Verify that the result is a DataFrame with the expected columns
                if not isinstance(result_df, pd.DataFrame):
                    logger.error("❌ Test failed: Result is not a DataFrame")
                    return False
                
                # Check if all required columns are present
                for col in mock_data_complete.keys():
                    if col not in result_df.columns:
                        logger.error(f"❌ Test failed: Column '{col}' is missing in the result")
                        return False
                
                logger.info("✅ Test passed: Result contains all expected columns")
                return True
            except Exception as e:
                logger.error(f"❌ Test failed: Unexpected error in complete headers scenario: {e}")
                return False
        except Exception as e:
            logger.error(f"❌ Test failed: Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # Restore the original function
            utils.fetch_google_form_responses = original_func
    
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """
    Main function to run the tests.
    """
    logger.info("Starting header validation tests...")
    
    success = test_header_validation()
    
    if success:
        logger.info("✅ All tests passed!")
        return 0
    else:
        logger.error("❌ Tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())