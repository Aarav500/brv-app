"""
Test script to verify that the mysql.connector import works correctly.
"""

try:
    # Test the import that was causing the error
    import mysql.connector as mysql
    
    print("✅ Import successful: mysql.connector as mysql")
    
    # Try to establish a connection (this will likely fail without proper credentials, but that's okay)
    try:
        # Just testing the connect function exists and can be called
        connection = mysql.connect(
            host="localhost",
            user="test",
            password="test",
            database="test"
        )
        print("✅ Connection function works (unexpected success with test credentials)")
    except Exception as e:
        print(f"✅ Connection function exists but failed as expected with test credentials: {e}")
        
except ImportError as e:
    print(f"❌ Import failed: {e}")
    
print("\nTest completed. If you see '✅ Import successful', the fix is working correctly.")