from firebase_db import authenticate

# Test CEO login
print("Testing CEO login...")
user = authenticate("ceo@bluematrixit.com", "123")
if user:
    print("✅ CEO login successful!")
    print("User data:", user)
else:
    print("❌ CEO login failed!")

# Test Reception login
print("\nTesting Reception login...")
user = authenticate("reception@bluematrixit.com", "234")
if user:
    print("✅ Reception login successful!")
    print("User data:", user)
else:
    print("❌ Reception login failed!")

# Test Interview login
print("\nTesting Interview login...")
user = authenticate("interview@bluematrixit.com", "345")
if user:
    print("✅ Interview login successful!")
    print("User data:", user)
else:
    print("❌ Interview login failed!")

# Test invalid login
print("\nTesting invalid login...")
user = authenticate("invalid@example.com", "wrongpassword")
if user:
    print("❌ Invalid login succeeded when it should have failed!")
    print("User data:", user)
else:
    print("✅ Invalid login correctly failed!")