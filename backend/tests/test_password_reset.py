import hashlib
import re
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.errors import ServiceError
from app.db.session import create_db_engine
from app.models import AuditLog, EmailOutbox, PasswordResetToken, User
from app.services.auth import confirm_password_reset
from conftest import TEST_PASSWORD, ManualClock

NEW_PASSWORD = "Updated!abc"


def request_token(client: TestClient, email: str) -> str:
    response = client.post("/api/v1/auth/password-reset/request", json={"email": email})
    assert response.status_code == 200
    with client.app.state.session_factory() as session:
        message = session.scalar(select(EmailOutbox).order_by(EmailOutbox.id.desc()))
        url = re.search(r"http[^\s]+", message.body).group()
        parsed = urlsplit(url)
        assert parsed.scheme == "http"
        assert parsed.netloc == "localhost:3000"
        assert parsed.path == "/reset-password"
        token = parse_qs(parsed.query)["token"][0]
        assert token not in response.text
        return token


def test_reset_response_is_generic_and_table_contains_only_digest(auth_client: TestClient, make_user, clock: ManualClock) -> None:
    user = make_user()
    known = auth_client.post("/api/v1/auth/password-reset/request", json={"email": " CUSTOMER@EXAMPLE.COM "})
    unknown = auth_client.post("/api/v1/auth/password-reset/request", json={"email": "unknown@example.com"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert set(known.json()) == {"message"}
    with auth_client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(EmailOutbox)) == 1
        message = session.scalar(select(EmailOutbox))
        token = parse_qs(urlsplit(re.search(r"http[^\s]+", message.body).group()).query)["token"][0]
        reset = session.scalar(select(PasswordResetToken))
        assert len(token) >= 43  # token_urlsafe(32): at least 256 random bits.
        assert reset.token_hash == hashlib.sha256(token.encode()).hexdigest()
        assert reset.token_hash != token
        assert reset.user_id == user.id
        assert (reset.expires_at - reset.created_at).total_seconds() == 1800
        assert reset.created_at == clock()
        assert "token" not in {column.name for column in PasswordResetToken.__table__.columns}


def test_reset_changes_password_revokes_jwts_and_audits(auth_client: TestClient, make_user, bearer_headers) -> None:
    user = make_user()
    headers = bearer_headers(user)
    token = request_token(auth_client, user.email)
    response = auth_client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": NEW_PASSWORD})
    assert response.status_code == 200
    assert token not in response.text
    assert auth_client.get("/api/v1/auth/me", headers=headers).status_code == 401
    for password, status in [(TEST_PASSWORD, 401), (NEW_PASSWORD, 200)]:
        login = auth_client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
        assert login.status_code == status
    with auth_client.app.state.session_factory() as session:
        assert session.get(User, user.id).auth_version == 1
        assert session.scalar(select(PasswordResetToken.consumed_at)) is not None
        audits = session.scalars(select(AuditLog)).all()
        assert len(audits) == 1
        assert audits[0].action == "auth.password_reset"
        assert token not in str(audits[0].detail)
        assert NEW_PASSWORD not in str(audits[0].detail)
        assert "password_hash" not in audits[0].detail
    assert auth_client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": NEW_PASSWORD}).status_code == 400


def test_reset_expires_at_thirty_minutes(auth_client: TestClient, make_user, clock: ManualClock) -> None:
    token = request_token(auth_client, make_user().email)
    clock.advance(minutes=30)
    response = auth_client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": NEW_PASSWORD})
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid or expired reset token"}
    with auth_client.app.state.session_factory() as session:
        assert session.scalar(select(PasswordResetToken.consumed_at)) is None
        assert session.scalar(select(func.count()).select_from(AuditLog)) == 0


def test_replacement_reset_invalidates_old_token(auth_client: TestClient, make_user) -> None:
    user = make_user()
    first = request_token(auth_client, user.email)
    second = request_token(auth_client, user.email)
    assert first != second
    for token, status in [(first, 400), (second, 200)]:
        assert auth_client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": NEW_PASSWORD}).status_code == status


def test_unknown_reset_token_is_rejected(auth_client: TestClient) -> None:
    response = auth_client.post("/api/v1/auth/password-reset/confirm", json={"token": "unknown-test-token", "new_password": NEW_PASSWORD})
    assert response.status_code == 400


def test_reset_validation_is_safe_and_does_not_consume_token(auth_client: TestClient, make_user) -> None:
    token = request_token(auth_client, make_user().email)
    response = auth_client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": "weak"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "new_password"
    assert token not in response.text
    assert "weak" not in response.text
    assert auth_client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": NEW_PASSWORD}).status_code == 200


def test_inactive_account_does_not_receive_or_consume_reset(auth_client: TestClient, make_user) -> None:
    user = make_user()
    token = request_token(auth_client, user.email)
    with auth_client.app.state.session_factory() as session, session.begin():
        session.execute(update(User).where(User.id == user.id).values(is_active=False))
    assert auth_client.post("/api/v1/auth/password-reset/request", json={"email": user.email}).status_code == 200
    assert auth_client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": NEW_PASSWORD}).status_code == 400
    with auth_client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(EmailOutbox)) == 1


def test_two_real_connections_cannot_consume_one_token_twice(auth_client: TestClient, make_user, migrated_url: str, clock: ManualClock) -> None:
    user = make_user()
    token = request_token(auth_client, user.email)
    barrier = Barrier(2)

    def attempt() -> tuple[int, int]:
        engine = create_db_engine(migrated_url)
        try:
            with engine.connect() as connection:
                connection_id = id(connection.connection.dbapi_connection)
                barrier.wait(timeout=10)
                with Session(bind=connection, expire_on_commit=False) as session:
                    try:
                        confirm_password_reset(session, token=token, password=NEW_PASSWORD, clock=clock)
                        return 200, connection_id
                    except ServiceError as error:
                        return error.status_code, connection_id
        finally:
            engine.dispose()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: attempt(), range(2)))
    assert sorted(status for status, _ in results) == [200, 400]
    assert len({connection for _, connection in results}) == 2
    with auth_client.app.state.session_factory() as session:
        assert session.get(User, user.id).auth_version == 1
        assert session.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "auth.password_reset")) == 1


def test_audit_failure_rolls_back_reset_and_revocation(auth_client: TestClient, make_user, monkeypatch) -> None:
    from app.services import auth

    user = make_user()
    token = request_token(auth_client, user.email)

    def broken_audit(*args, **kwargs) -> None:
        raise ServiceError(503, "Test audit failure")

    monkeypatch.setattr(auth, "record_event", broken_audit)
    response = auth_client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": NEW_PASSWORD})
    assert response.status_code == 503
    with auth_client.app.state.session_factory() as session:
        assert session.get(User, user.id).auth_version == 0
        assert session.scalar(select(PasswordResetToken.consumed_at)) is None
    assert auth_client.post("/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD}).status_code == 200
