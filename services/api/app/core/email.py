"""Minimal SMTP email sender (Mailpit in dev).

Kept behind one function so it can later be swapped for a provider (SES,
Resend, etc.) without touching call sites.
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("email")


def send_email(to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings.email_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            if settings.smtp_user:
                smtp.starttls()
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        log.info("email_sent", to=to, subject=subject)
    except Exception as exc:  # pragma: no cover - dev convenience
        # In dev we don't want a missing SMTP server to break flows; log and move on.
        log.warning("email_failed", to=to, subject=subject, error=str(exc))
