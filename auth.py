# auth.py
from database import SessionLocal
from models import User, RoleEnum
import bcrypt
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

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_user(email: str, password: str, role: str = "candidate"):
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            return None, "User already exists"
        user = User(email=email, password_hash=hash_password(password), role=RoleEnum(role))
        db.add(user); db.commit(); db.refresh(user)
        return user, None
    except Exception as e:
        logger.exception("create_user failed")
        return None, str(e)
    finally:
        db.close()

def authenticate_user(email: str, password: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return None
        if verify_password(password, user.password_hash):
            return user
        return None
    finally:
        db.close()

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
