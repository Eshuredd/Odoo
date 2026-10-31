import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import AuthenticationError, ServiceError
from app.core.principal import Principal
from app.core.security import (
    dummy_password_hash, hash_password, issue_access_token, signing_key, verify_password,
)
from app.core.validation import normalize_email, validate_password
from app.models import CustomerProfile, PasswordResetToken, User, UserRole
from app.schemas.auth import LoginResponse, PublicUser
from app.services.audit import record_event
from app.services.mailer import MailDeliveryError, Mailer, MailMessage

RESET_REQUEST_MESSAGE = "If the account exists, password reset instructions have been sent."


def check_principal(session: Session, principal: Principal, role: UserRole | None = None) -> User:
    """Recheck inside sensitive writes to cover concurrent revocation/role changes."""
    user = session.get(User, principal.id)
    if user is None or not user.is_active or user.auth_version != principal.auth_version:
        raise AuthenticationError()
    if role is not None and user.role != role:
        raise ServiceError(403, "Insufficient permissions")
    return user


def create_account(
    session: Session, *, email: str, password: str, role: UserRole, clock: Clock,
    actor: Principal | None = None, profile: dict | None = None,
) -> PublicUser:
    email = normalize_email(email)
    password_hash = hash_password(password)
    try:
        with session.begin():
            # Acquire the writer lock before checking an admin's current permissions.
            session.connection(execution_options={"sqlite_begin_mode": "IMMEDIATE"})
            if actor is not None:
                current = check_principal(session, actor)
                allowed = {UserRole.ADMIN, UserRole.STAFF} if role == UserRole.CUSTOMER else {UserRole.ADMIN}
                if current.role not in allowed:
                    raise ServiceError(403, "Insufficient permissions")
            elif role != UserRole.CUSTOMER:
                raise ServiceError(403, "Insufficient permissions")
            now = clock()
            user = User(email=email, password_hash=password_hash, role=role,
                        created_at=now, updated_at=now)
            session.add(user)
            session.flush()  # Database UNIQUE constraint arbitrates concurrent signup too.
            if role == UserRole.CUSTOMER:
                fields = {"company_name": "", "contact_name": email.split("@")[0], **(profile or {})}
                session.add(CustomerProfile(user_id=user.id, created_at=now, updated_at=now, **fields))
            record_event(
                session, actor_id=actor.id if actor else user.id, entity_id=user.id, now=now,
                action=("user.staff_created" if role == UserRole.STAFF else "user.customer_created") if actor else "user.signup",
                detail={"role": role.value},
            )
            result = PublicUser.model_validate(user)
    except IntegrityError as error:
        if "UNIQUE constraint failed: users.email" in str(error.orig):
            raise ServiceError(409, "An account with this email already exists") from None
        raise
    return result


def login(
    session: Session, *, email: str, password: str, settings: Settings, clock: Clock,
) -> LoginResponse:
    key = signing_key(settings)
    with session.begin():
        user = session.scalar(select(User).where(User.email == normalize_email(email)))
        candidate_hash = user.password_hash if user else dummy_password_hash()
        valid = verify_password(candidate_hash, password)
        if not valid or user is None or not user.is_active:
            raise ServiceError(401, "Invalid email or password")
        return LoginResponse(
            access_token=issue_access_token(user.id, user.auth_version, key, clock()),
            user=PublicUser.model_validate(user),
        )


def logout(session: Session, principal: Principal, clock: Clock) -> None:
    with session.begin():
        session.connection(execution_options={"sqlite_begin_mode": "IMMEDIATE"})
        user = check_principal(session, principal)
        now = clock()
        user.auth_version += 1
        user.updated_at = now
        record_event(session, actor_id=user.id, action="auth.logout", entity_id=user.id, now=now)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def request_password_reset(
    session: Session, *, email: str, settings: Settings, mailer: Mailer, clock: Clock,
) -> None:
    try:
        with session.begin():
            session.connection(execution_options={"sqlite_begin_mode": "IMMEDIATE"})
            user = session.scalar(select(User).where(User.email == normalize_email(email), User.is_active.is_(True)))
            if user is None:
                return
            now = clock()
            session.execute(update(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id, PasswordResetToken.consumed_at.is_(None),
            ).values(consumed_at=now))
            raw_token = secrets.token_urlsafe(32)
            session.add(PasswordResetToken(
                user_id=user.id, token_hash=token_digest(raw_token),
                created_at=now, expires_at=now + timedelta(minutes=30),
            ))
            reset_url = settings.password_reset_base_url + "?" + urlencode({"token": raw_token})
            mailer.send(MailMessage(
                recipient_email=user.email, subject="Reset your SubCadence password",
                body=f"Reset your password using this link:\n{reset_url}\n\n"
                     "This link expires in 30 minutes and can be used once. "
                     "If you did not request a reset, ignore this email.",
            ), session=session, now=now)
    except MailDeliveryError:
        # Roll back issuance/replacement on failed delivery; public response stays generic.
        return


def confirm_password_reset(session: Session, *, token: str, password: str, clock: Clock) -> None:
    password_hash = hash_password(password)
    with session.begin():
        session.connection(execution_options={"sqlite_begin_mode": "IMMEDIATE"})
        now = clock()
        reset = session.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_digest(token)))
        if reset is None or reset.consumed_at is not None or reset.expires_at <= now:
            raise ServiceError(400, "Invalid or expired reset token")
        user = session.get(User, reset.user_id)
        if user is None or not user.is_active:
            raise ServiceError(400, "Invalid or expired reset token")
        user.password_hash = password_hash
        user.auth_version += 1
        user.updated_at = now
        reset.consumed_at = now
        record_event(session, actor_id=user.id, action="auth.password_reset", entity_id=user.id, now=now)


def seed_admin(session: Session, *, email: str, password: str, clock: Clock) -> tuple[int, bool]:
    email = normalize_email(email)
    validate_password(password)
    with session.begin():
        session.connection(execution_options={"sqlite_begin_mode": "IMMEDIATE"})
        existing = session.scalar(select(User).where(User.email == email))
        if existing is not None:
            if existing.role != UserRole.ADMIN:
                raise ServiceError(409, "Email belongs to a non-admin account; no changes made")
            return existing.id, False
        now = clock()
        user = User(email=email, password_hash=hash_password(password), role=UserRole.ADMIN,
                    created_at=now, updated_at=now)
        session.add(user)
        session.flush()
        record_event(session, actor_id=user.id, action="user.admin_seeded", entity_id=user.id, now=now)
        return user.id, True
