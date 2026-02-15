"""Email utility for sending OTP verification emails via SMTP."""

import smtplib
import random
import string
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from shared.config import settings

logger = logging.getLogger("email_utils")


def generate_otp(length: int = 6) -> str:
    """Generate a random numeric OTP."""
    return "".join(random.choices(string.digits, k=length))


def send_otp_email(to_email: str, otp: str, full_name: str = "") -> bool:
    """Send OTP verification email. Returns True on success."""
    subject = f"SignalForge – Your verification code is {otp}"
    greeting = f"Hi {full_name}," if full_name else "Hi,"

    html_body = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 480px; margin: auto;
                padding: 32px; border: 1px solid #e0e0e0; border-radius: 12px;">
        <h2 style="color: #1976d2; margin-bottom: 4px;">SignalForge</h2>
        <p style="color: #888; font-size: 13px; margin-top: 0;">AI-Powered Stock Trading Signals</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p>{greeting}</p>
        <p>Your one-time verification code is:</p>
        <div style="text-align: center; margin: 24px 0;">
            <span style="font-size: 32px; letter-spacing: 8px; font-weight: 700;
                         color: #1976d2; background: #f5f5f5; padding: 12px 28px;
                         border-radius: 8px; display: inline-block;">{otp}</span>
        </div>
        <p style="color: #666; font-size: 13px;">
            This code expires in <strong>{settings.OTP_EXPIRE_MINUTES} minutes</strong>.
            Do not share it with anyone.
        </p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #aaa; font-size: 11px;">
            If you didn't request this, please ignore this email.<br>
            &copy; SignalForge &middot; ThinkhiveLabs
        </p>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_USER}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_USER, to_email, msg.as_string())
        logger.info(f"OTP email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send OTP email to {to_email}: {e}")
        return False
