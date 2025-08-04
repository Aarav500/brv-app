import sqlite3

def reset_ceo_password_flag():
    """
    Reset the force_password_reset flag for the CEO user.
    This is a temporary fix for users stuck in a forced reset loop.
    """
    print("Resetting CEO's password reset flag...")
    
    conn = sqlite3.connect('data/brv_applicants.db')
    c = conn.cursor()
    
    # Disable forced reset for CEO
    c.execute("UPDATE users SET force_password_reset = 0 WHERE username = 'ceo'")
    
    # Check if the update was successful
    c.execute("SELECT force_password_reset FROM users WHERE username = 'ceo'")
    result = c.fetchone()
    
    conn.commit()
    conn.close()
    
    if result and result[0] == 0:
        print("✅ Reset CEO's password reset flag successfully.")
    else:
        print("❌ Failed to reset CEO's password reset flag.")

if __name__ == "__main__":
    reset_ceo_password_flag()