from email.message import EmailMessage
import smtplib
import ssl

from app.core.config import settings


def send_password_reset_email(to_email: str, full_name: str, reset_url: str) -> None:
    if not settings.smtp_host or not settings.smtp_from_email:
        raise RuntimeError("SMTP email delivery is not configured.")
    message = EmailMessage()
    message["Subject"] = "Reset your VEXION password"
    message["From"] = settings.smtp_from_email
    message["To"] = to_email
    message.set_content(
        f"Hello {full_name},\n\n"
        "We received a request to reset your VEXION password. Use the secure link below "
        "within 30 minutes:\n\n"
        f"{reset_url}\n\n"
        "If you did not request this change, you can ignore this email. Your current "
        "password will remain unchanged.\n"
    )
    if settings.smtp_port == 465:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15, context=ssl.create_default_context()) as smtp:
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
