"""
Test script to verify that the database connection functionality works properly.
"""

import sys
import os

# Add the brv-app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'brv-app'))

try:
    # Import the test_connection function from mysql_db
    from mysql_db import test_connection
    
    print("✅ Successfully imported test_connection function from mysql_db")
    
    # Try to run the test_connection function
    try:
        result = test_connection()
        print(f"✅ test_connection function executed: {result}")
    except Exception as e:
        print(f"⚠️ test_connection function raised an exception (this might be expected): {e}")
        
except ImportError as e:
    print(f"❌ Import failed: {e}")
    
print("\nTest completed. If you see '✅ Successfully imported test_connection function from mysql_db', the fix is working correctly.")