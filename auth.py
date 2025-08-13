# auth.py
from db_postgres import get_user_by_email, hash_password, verify_password, get_conn
import os
import jwt
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging
import smtplib
from email.message import EmailMessage

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
RESET_TOKEN_EXP_MIN = 30

logger = logging.getLogger(__name__)


def create_user(email: str, password: str, role: str = "candidate"):
    """Create user using PostgreSQL database"""
    try:
        conn = get_conn()
        with conn:
            with conn.cursor() as cur:
                # Check if user already exists
                cur.execute("SELECT id FROM users WHERE email=%s", (email,))
                if cur.fetchone():
                    return None, "User already exists"

                # Create new user
                password_hash = hash_password(password)
                cur.execute("""
                            INSERT INTO users (email, password_hash, role)
                            VALUES (%s, %s, %s) RETURNING id, email, role
                            """, (email, password_hash, role))

                result = cur.fetchone()
                user_dict = {
                    'id': result[0],
                    'email': result[1],
                    'role': result[2]
                }
        conn.close()
        return user_dict, None
    except Exception as e:
        logger.exception("create_user failed")
        return None, str(e)


def authenticate_user(email: str, password: str):
    """Authenticate user using PostgreSQL database"""
    user = get_user_by_email(email)
    if user and verify_password(password, user['password_hash']):
        return user
    return None


def create_access_token(user_id: int, expires_minutes: int = 60):
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(minutes=expires_minutes)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    return token


def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub")
    except Exception:
        return None


# --- Password reset ---
def create_reset_token(email: str, expires_min: int = RESET_TOKEN_EXP_MIN):
    payload = {
        "email": email,
        "exp": datetime.utcnow() + timedelta(minutes=expires_min)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def verify_reset_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("email")
    except Exception as e:
        logger.debug("reset token invalid: %s", e)
        return None


def update_user_password_by_email(email: str, new_password: str):
    """Update user password by email"""
    from db_postgres import update_user_password
    return update_user_password(email, new_password)


def send_reset_email(to_email: str, reset_token: str):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    from_email = os.getenv("FROM_EMAIL", "no-reply@example.com")

    reset_link = f"RESET_TOKEN:{reset_token}"  # For console fallback. In production you'd send a URL.
    body = f"Use this token to reset your password (expires in {RESET_TOKEN_EXP_MIN} minutes):\n\n{reset_link}"

    if smtp_host and smtp_port and smtp_user and smtp_pass:
        try:
            msg = EmailMessage()
            msg["Subject"] = "BRV Password Reset"
            msg["From"] = from_email
            msg["To"] = to_email
            msg.set_content(body)

            with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            logger.info("Password reset email sent to %s", to_email)
            return True, "Email sent"
        except Exception as e:
            logger.exception("Failed to send reset email")
            return False, str(e)
    else:
        # Fallback: print token to console so you can copy it
        logger.warning("SMTP not configured — printing reset token to console")
        print("---------- PASSWORD RESET TOKEN (console fallback) ----------")
        print(body)
        print("------------------------------------------------------------")
        return True, "Printed to console"