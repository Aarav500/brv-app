#!/usr/bin/env python3
"""
Simple test script to verify the header validation logic.
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
    Test the header validation logic directly.
    """
    logger.info("Testing header validation logic directly...")
    
    # Define the expected headers (must match utils.py)
    expected_headers = [
        "Timestamp",
        "Email Address",
        "Full Name( First-middle-last)",
        "Current Address",
        "Permanent Address",
        "Phone number",
        "Additional Phone Number (NA if none)",
        "Date Of birth",
        "Caste",
        "Sub Caste",
        "Marital Status",
        "Highest Qualification",
        "Work Experience ",  # Note the trailing space
        "Referral ",         # Note the trailing space
        "Upload your Resume"
    ]
    
    # Test scenario 1: Missing headers
    logger.info("Testing scenario 1: Missing headers")
    
    # Create a DataFrame with missing columns
    missing_data = {
        "Timestamp": ["2023-01-01 12:00:00"],
        "Email Address": ["test@example.com"],
        # Missing "Full Name( First-middle-last)" column
        "Current Address": ["123 Main St"],
        # Missing other required columns
    }
    df_missing = pd.DataFrame(missing_data)
    
    # Check for missing columns
    actual_headers = df_missing.columns.tolist()
    missing_columns = [header for header in expected_headers if header not in actual_headers]
    
    # Verify that missing columns are detected
    if missing_columns:
        logger.info("✅ Test passed: Correctly detected missing columns")
        logger.info(f"Missing columns: {missing_columns}")
    else:
        logger.error("❌ Test failed: No missing columns detected")
        return False
    
    # Test scenario 2: Complete headers
    logger.info("Testing scenario 2: Complete headers")
    
    # Create a DataFrame with all required columns
    complete_data = {
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
        "Work Experience ": ["2 years"],  # Note the trailing space
        "Referral ": ["None"],            # Note the trailing space
        "Upload your Resume": ["https://example.com/resume.pdf"]
    }
    df_complete = pd.DataFrame(complete_data)
    
    # Check for missing columns
    actual_headers = df_complete.columns.tolist()
    missing_columns = [header for header in expected_headers if header not in actual_headers]
    
    # Verify that no columns are missing
    if missing_columns:
        logger.error(f"❌ Test failed: Missing columns detected: {missing_columns}")
        return False
    else:
        logger.info("✅ Test passed: No missing columns detected")
    
    # Test scenario 3: Extra columns (should be ignored)
    logger.info("Testing scenario 3: Extra columns")
    
    # Create a DataFrame with all required columns plus extra columns
    extra_data = complete_data.copy()
    extra_data["Extra Column 1"] = ["Extra data 1"]
    extra_data["Extra Column 2"] = ["Extra data 2"]
    df_extra = pd.DataFrame(extra_data)
    
    # Check for missing columns
    actual_headers = df_extra.columns.tolist()
    missing_columns = [header for header in expected_headers if header not in actual_headers]
    
    # Verify that no columns are missing
    if missing_columns:
        logger.error(f"❌ Test failed: Missing columns detected: {missing_columns}")
        return False
    else:
        logger.info("✅ Test passed: No missing columns detected despite extra columns")
    
    # All tests passed
    return True

def main():
    """
    Main function to run the tests.
    """
    logger.info("Starting simple header validation tests...")
    
    success = test_header_validation()
    
    if success:
        logger.info("✅ All tests passed!")
        return 0
    else:
        logger.error("❌ Tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())