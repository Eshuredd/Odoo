"""Import all models here so Alembic sees the complete metadata."""

from app.models.audit import AuditLog
from app.models.user import User, UserRole
from app.models.password_reset import PasswordResetToken
from app.models.email_outbox import EmailOutbox

__all__ = ["AuditLog", "User", "UserRole", "PasswordResetToken", "EmailOutbox"]
