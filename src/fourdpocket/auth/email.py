"""Pluggable email sender.

Default: log to console (good for self-hosters until they wire SMTP).
Configure via FDP_EMAIL__SMTP_HOST env var to switch to real delivery.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def _wrap_html(subject: str, body_text: str) -> str:
    """Auto-wrap plain text into a minimal HTML email."""
    safe = body_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    lines = safe.replace("\n", "<br>")
    return (
        f"<!DOCTYPE html><html><body>"
        f"<h2>{subject}</h2><p>{lines}</p>"
        f"</body></html>"
    )


def send_email(
    to: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
) -> bool:
    """Send an email via SMTP if configured, else log to console.

    Returns True when the email was dispatched (real SMTP) or logged
    (unconfigured). Returns False only on SMTP delivery failure.
    """
    from fourdpocket.config import get_settings

    cfg = get_settings().email

    if not cfg.smtp_host:
        logger.info(
            "EMAIL[unconfigured] to=%s subject=%s body=%s",
            to,
            subject,
            body_text,
        )
        return True

    html = body_html or _wrap_html(subject, body_text)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{cfg.from_name} <{cfg.from_address}>" if cfg.from_address else cfg.from_name
    msg["To"] = to
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port) as smtp:
            if cfg.smtp_use_tls:
                smtp.starttls()
            if cfg.smtp_user:
                smtp.login(cfg.smtp_user, cfg.smtp_password)
            smtp.sendmail(msg["From"], [to], msg.as_string())
        return True
    except Exception as exc:
        logger.error("EMAIL[send_failed] to=%s subject=%s error=%s", to, subject, exc)
        return False
