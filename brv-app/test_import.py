#!/usr/bin/env python3
"""
Test script to verify that get_edit_link_by_candidate_id can be imported from edit_link_api.
"""

import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """
    Main function to test importing get_edit_link_by_candidate_id from edit_link_api.
    """
    logger.info("Testing import of get_edit_link_by_candidate_id from edit_link_api...")
    
    try:
        # Import the function
        from edit_link_api import get_edit_link_by_candidate_id
        logger.info("✅ Successfully imported get_edit_link_by_candidate_id from edit_link_api")
        
        # Test the function with a dummy candidate ID
        test_id = "TEST-0001"
        logger.info(f"Testing function with candidate ID: {test_id}")
        
        success, result = get_edit_link_by_candidate_id(test_id)
        
        if success:
            logger.info(f"✅ Function returned success with result: {result}")
        else:
            logger.info(f"⚠️ Function returned failure with message: {result}")
        
        logger.info("Import test completed successfully")
        return 0
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        return 1
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())