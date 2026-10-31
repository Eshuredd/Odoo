import smtplib
import ssl
from dataclasses import dataclass, field
from datetime import datetime
from email.message import EmailMessage as SMTPMessage
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.validation import normalize_email
from app.models import EmailOutbox


class MailDeliveryError(Exception):
    """Delivery failed; never expose the underlying SMTP exception publicly."""


@dataclass(frozen=True)
class MailMessage:
    recipient_email: str
    subject: str
    body: str = field(repr=False)


class Mailer(Protocol):
    def send(self, message: MailMessage, *, session: Session, now: datetime) -> None: ...


class DatabaseOutboxMailer:
    def send(self, message: MailMessage, *, session: Session, now: datetime) -> None:
        session.add(EmailOutbox(
            recipient_email=message.recipient_email, subject=message.subject,
            body=message.body, created_at=now,
        ))


class SMTPMailer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send(self, message: MailMessage, *, session: Session, now: datetime) -> None:
        settings = self.settings
        username = settings.smtp_username or ""
        password = settings.smtp_password.get_secret_value() if settings.smtp_password else ""
        try:
            if not settings.smtp_host or bool(username) != bool(password):
                raise ValueError("Incomplete SMTP configuration")
            if username and not settings.smtp_starttls:
                raise ValueError("SMTP credentials require STARTTLS")
            sender = normalize_email(settings.smtp_from_email or username)
            email = SMTPMessage()
            email["From"] = sender
            email["To"] = normalize_email(message.recipient_email)
            email["Subject"] = message.subject
            email.set_content(message.body)
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout) as smtp:
                smtp.ehlo()
                if settings.smtp_starttls:
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.ehlo()
                if username:
                    smtp.login(username, password)
                if smtp.send_message(email):
                    raise MailDeliveryError("Email delivery failed")
        except (smtplib.SMTPException, OSError, ValueError):
            raise MailDeliveryError("Email delivery failed") from None


def create_mailer(settings: Settings) -> Mailer:
    if any((settings.smtp_host, settings.smtp_username, settings.smtp_password, settings.smtp_from_email)):
        return SMTPMailer(settings)
    return DatabaseOutboxMailer()
