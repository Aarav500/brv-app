# smtp_mailer.py
import os
import smtplib
from email.message import EmailMessage

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)

def send_email(to_email, subject, text, html=None):
    msg = EmailMessage()
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)
    return True
