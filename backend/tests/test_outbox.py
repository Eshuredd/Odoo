import smtplib
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select

from app.core.config import Settings
from app.main import create_app
from app.models import EmailOutbox, PasswordResetToken, UserRole
from app.services.mailer import create_mailer
from conftest import ManualClock


@pytest.mark.parametrize("role,status", [(UserRole.ADMIN, 200), (UserRole.STAFF, 403), (UserRole.CUSTOMER, 403)])
def test_outbox_permissions_and_pagination(auth_client: TestClient, make_user, bearer_headers, role: UserRole, status: int) -> None:
    user = make_user(role)
    headers = bearer_headers(user)
    for _ in range(3):
        assert auth_client.post("/api/v1/auth/password-reset/request", json={"email": user.email}).status_code == 200
    response = auth_client.get("/api/v1/dev/email-outbox?limit=1&offset=1", headers=headers)
    assert response.status_code == status
    if status == 200:
        data = response.json()
        assert data["total"] == 3
        assert data["limit"] == data["offset"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == 2
        assert "reset-password?token=" in data["items"][0]["body"]
        assert response.headers["cache-control"] == "no-store"
        assert auth_client.get("/api/v1/dev/email-outbox?limit=101", headers=headers).status_code == 422
        assert auth_client.get("/api/v1/dev/email-outbox?offset=-1", headers=headers).status_code == 422


def test_outbox_requires_authentication(auth_client: TestClient) -> None:
    assert auth_client.get("/api/v1/dev/email-outbox").status_code == 401


@pytest.mark.parametrize("environment", ["test", "production"])
def test_outbox_route_is_absent_outside_development(auth_settings: Settings, make_user, bearer_headers, environment: str) -> None:
    headers = bearer_headers(make_user(UserRole.ADMIN))
    settings = auth_settings.model_copy(update={"app_env": environment})
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/dev/email-outbox", headers=headers).status_code == 404
        assert "/api/v1/dev/email-outbox" not in client.get("/openapi.json").json()["paths"]


def smtp_settings(auth_settings: Settings) -> Settings:
    return auth_settings.model_copy(update={
        "smtp_host": "smtp.example.com", "smtp_port": 587, "smtp_username": "mailer@example.com",
        "smtp_password": SecretStr("synthetic-smtp-test-value"), "smtp_from_email": "mailer@example.com",
    })


def test_smtp_sends_with_starttls_and_never_contacts_real_server(auth_client: TestClient, auth_settings: Settings, make_user) -> None:
    user = make_user()
    auth_client.app.state.mailer = create_mailer(smtp_settings(auth_settings))
    with patch("app.services.mailer.smtplib.SMTP", autospec=True) as constructor:
        smtp = constructor.return_value.__enter__.return_value
        smtp.send_message.return_value = {}
        response = auth_client.post("/api/v1/auth/password-reset/request", json={"email": user.email})
        assert response.status_code == 200
        constructor.assert_called_once_with("smtp.example.com", 587, timeout=5.0)
        smtp.starttls.assert_called_once()
        smtp.login.assert_called_once_with("mailer@example.com", "synthetic-smtp-test-value")
        message = smtp.send_message.call_args.args[0]
        assert "reset-password?token=" in message.get_content()
        assert message["To"] == user.email
    with auth_client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(EmailOutbox)) == 0
        assert session.scalar(select(func.count()).select_from(PasswordResetToken)) == 1


def test_smtp_failure_is_generic_and_rolls_back_token_replacement(auth_client: TestClient, auth_settings: Settings, make_user) -> None:
    user = make_user()
    assert auth_client.post("/api/v1/auth/password-reset/request", json={"email": user.email}).status_code == 200
    auth_client.app.state.mailer = create_mailer(smtp_settings(auth_settings))
    with patch("app.services.mailer.smtplib.SMTP", side_effect=smtplib.SMTPException("private delivery error")):
        known = auth_client.post("/api/v1/auth/password-reset/request", json={"email": user.email})
        unknown = auth_client.post("/api/v1/auth/password-reset/request", json={"email": "unknown@example.com"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert "private" not in known.text
    with auth_client.app.state.session_factory() as session:
        resets = session.scalars(select(PasswordResetToken)).all()
        assert len(resets) == 1
        assert resets[0].consumed_at is None


def test_smtp_credentials_cannot_be_sent_without_tls(auth_client: TestClient, auth_settings: Settings, make_user) -> None:
    user = make_user()
    settings = smtp_settings(auth_settings).model_copy(update={"smtp_starttls": False})
    auth_client.app.state.mailer = create_mailer(settings)
    with patch("app.services.mailer.smtplib.SMTP") as constructor:
        assert auth_client.post("/api/v1/auth/password-reset/request", json={"email": user.email}).status_code == 200
        constructor.assert_not_called()
