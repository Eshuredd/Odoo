from dataclasses import FrozenInstanceError
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from app.core.config import Settings
from app.core.principal import Principal
from app.core.security import AUDIENCE, ISSUER, password_hasher, signing_key
from app.core.validation import validate_password
from app.main import create_app
from app.models import AuditLog, User, UserRole
from conftest import TEST_PASSWORD, ManualClock


@pytest.mark.parametrize("password", ["Abcdefgh!", "Abcdefghi!", "Abcdefghij!", " SpacePass! ", "Aa!" + "x" * 125])
def test_accepted_passwords_are_not_modified(password: str) -> None:
    assert validate_password(password) == password


@pytest.mark.parametrize("password,reason", [
    ("Abcdefg!", "9–128"), ("abcdefgh!", "uppercase"), ("ABCDEFGH!", "lowercase"),
    ("Abcdefghi", "special"), ("Abcdefgh ", "special"), ("Aa!" + "x" * 126, "9–128"),
])
def test_password_rules(password: str, reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        validate_password(password)


def test_signup_hashes_password_and_returns_safe_fields(auth_client: TestClient) -> None:
    response = auth_client.post("/api/v1/auth/signup", json={"email": " Customer@EXAMPLE.com ", "password": TEST_PASSWORD})
    assert response.status_code == 201
    user = response.json()
    assert set(user) == {"id", "email", "role", "is_active", "created_at"}
    assert user["email"] == "customer@example.com"
    assert user["role"] == "customer"
    assert response.headers["cache-control"] == "no-store"
    with auth_client.app.state.session_factory() as session:
        stored = session.get(User, user["id"])
        assert stored.password_hash.startswith("$argon2id$")
        assert password_hasher.verify(stored.password_hash, TEST_PASSWORD)
        audit = session.scalar(select(AuditLog))
        assert audit.action == "user.signup"
        assert audit.actor_id == stored.id
        assert audit.detail == {"role": "customer"}


def test_signup_duplicate_email_returns_conflict(auth_client: TestClient) -> None:
    body = {"email": "Customer@example.com", "password": TEST_PASSWORD}
    assert auth_client.post("/api/v1/auth/signup", json=body).status_code == 201
    body["email"] = "CUSTOMER@EXAMPLE.COM"
    assert auth_client.post("/api/v1/auth/signup", json=body).status_code == 409
    with auth_client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 1
        assert session.scalar(select(func.count()).select_from(AuditLog)) == 1


@pytest.mark.parametrize("extra", [{"role": "admin"}, {"role": "staff"}, {"is_active": True}, {"auth_version": 0}])
def test_signup_rejects_privilege_fields(auth_client: TestClient, extra: dict) -> None:
    response = auth_client.post("/api/v1/auth/signup", json={"email": "bad@example.com", "password": TEST_PASSWORD, **extra})
    assert response.status_code == 422
    assert TEST_PASSWORD not in response.text


@pytest.mark.parametrize("email", ["invalid", "a@@example.com", "user@éxample.com", "üser@example.com"])
@pytest.mark.parametrize("path", ["signup", "login", "password-reset/request"])
def test_email_validation_is_shared(auth_client: TestClient, email: str, path: str) -> None:
    body = {"email": email}
    if path != "password-reset/request":
        body["password"] = TEST_PASSWORD
    response = auth_client.post("/api/v1/auth/" + path, json=body)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "email"


@pytest.mark.parametrize("password", ["Abcdefg!", "abcdefgh!", "ABCDEFGH!", "Abcdefghi", "Aa!" + "x" * 126])
def test_signup_password_errors_are_field_specific_and_sanitized(auth_client: TestClient, password: str) -> None:
    response = auth_client.post("/api/v1/auth/signup", json={"email": "invalid@example.com", "password": password})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "password"
    assert all("input" not in error for error in response.json()["detail"])
    assert password not in response.text


def test_login_and_me(auth_client: TestClient, auth_settings: Settings, make_user, clock: ManualClock) -> None:
    user = make_user()
    response = auth_client.post("/api/v1/auth/login", json={"email": " CUSTOMER@EXAMPLE.COM ", "password": TEST_PASSWORD})
    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 7200
    claims = jwt.decode(data["access_token"], signing_key(auth_settings), algorithms=["HS256"], audience=AUDIENCE, issuer=ISSUER)
    assert claims["sub"] == str(user.id)
    assert claims["auth_version"] == 0
    assert claims["exp"] - claims["iat"] == 7200
    assert claims["iat"] == int(clock().timestamp())
    assert "role" not in claims
    me = auth_client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + data["access_token"]})
    assert me.status_code == 200
    assert me.json() == data["user"]
    assert "password_hash" not in me.text


def test_login_failures_are_generic(auth_client: TestClient, make_user) -> None:
    user = make_user()
    responses = [auth_client.post("/api/v1/auth/login", json={"email": email, "password": "Incorrect!"})
                 for email in (user.email, "unknown@example.com")]
    assert [response.status_code for response in responses] == [401, 401]
    assert responses[0].json() == responses[1].json() == {"detail": "Invalid email or password"}
    assert responses[0].headers["www-authenticate"] == "Bearer"


def test_inactive_user_cannot_login_or_use_existing_token(auth_client: TestClient, make_user, bearer_headers) -> None:
    user = make_user()
    headers = bearer_headers(user)
    with auth_client.app.state.session_factory() as session, session.begin():
        session.execute(update(User).where(User.id == user.id).values(is_active=False))
    assert auth_client.get("/api/v1/auth/me", headers=headers).status_code == 401
    response = auth_client.post("/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


def test_jwt_expires_exactly_at_two_hours(auth_client: TestClient, make_user, bearer_headers, clock: ManualClock) -> None:
    headers = bearer_headers(make_user())
    clock.advance(seconds=7199)
    assert auth_client.get("/api/v1/auth/me", headers=headers).status_code == 200
    clock.advance(seconds=1)
    assert auth_client.get("/api/v1/auth/me", headers=headers).status_code == 401


@pytest.mark.parametrize("algorithm", ["HS384", "HS512", "none"])
def test_unsupported_jwt_algorithms(auth_client: TestClient, auth_settings: Settings, make_user, clock: ManualClock, algorithm: str) -> None:
    user = make_user()
    claims = {"sub": str(user.id), "iat": int(clock().timestamp()), "exp": int(clock().timestamp()) + 7200,
              "auth_version": 0, "iss": ISSUER, "aud": AUDIENCE}
    token = jwt.encode(claims, "" if algorithm == "none" else signing_key(auth_settings), algorithm=algorithm)
    assert auth_client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token}).status_code == 401


@pytest.mark.parametrize("change", [
    {"sub": None}, {"sub": "-1"}, {"sub": "9999999999999999999"}, {"sub": "9999"},
    {"auth_version": True}, {"auth_version": 1}, {"exp": None}, {"iat": "now"},
    {"iss": "other"}, {"aud": "other"}, {"exp": "remove"},
])
def test_jwt_claims_are_required_and_validated(auth_client: TestClient, auth_settings: Settings, make_user, clock: ManualClock, change: dict) -> None:
    user = make_user()
    claims = {"sub": str(user.id), "iat": int(clock().timestamp()), "exp": int(clock().timestamp()) + 7200,
              "auth_version": 0, "iss": ISSUER, "aud": AUDIENCE}
    claims.update(change)
    if claims.get("exp") == "remove":
        del claims["exp"]
    token = jwt.encode(claims, signing_key(auth_settings), algorithm="HS256")
    assert auth_client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token}).status_code == 401


def test_tampered_token_rejected(auth_client: TestClient, make_user, bearer_headers) -> None:
    token = bearer_headers(make_user())["Authorization"].split()[1]
    header, payload, signature = token.split(".")
    signature = ("a" if signature[0] != "a" else "b") + signature[1:]
    assert auth_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {header}.{payload}.{signature}"}).status_code == 401


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Basic xyz"}, {"Authorization": "Bearer invalid"}])
def test_missing_or_malformed_auth(auth_client: TestClient, headers: dict) -> None:
    assert auth_client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_logout_revokes_all_tokens_and_audits(auth_client: TestClient, make_user, bearer_headers) -> None:
    user = make_user()
    first, second = bearer_headers(user), bearer_headers(user)
    assert auth_client.post("/api/v1/auth/logout", headers=first).status_code == 200
    assert auth_client.get("/api/v1/auth/me", headers=first).status_code == 401
    assert auth_client.get("/api/v1/auth/me", headers=second).status_code == 401
    assert auth_client.get("/api/v1/auth/me", headers=bearer_headers(user)).status_code == 200
    with auth_client.app.state.session_factory() as session:
        assert session.get(User, user.id).auth_version == 1
        assert session.scalar(select(AuditLog.action)) == "auth.logout"


@pytest.mark.parametrize("role,expected", [(UserRole.ADMIN, 201), (UserRole.STAFF, 403), (UserRole.CUSTOMER, 403)])
def test_staff_creation_permissions(auth_client: TestClient, make_user, bearer_headers, role: UserRole, expected: int) -> None:
    actor = make_user(role)
    response = auth_client.post("/api/v1/users/staff", headers=bearer_headers(actor),
                                json={"email": "newstaff@example.com", "password": TEST_PASSWORD})
    assert response.status_code == expected
    with auth_client.app.state.session_factory() as session:
        if expected == 201:
            assert response.json()["role"] == "staff"
            audit = session.scalar(select(AuditLog))
            assert audit.actor_id == actor.id
            assert audit.action == "user.staff_created"
        else:
            assert session.scalar(select(func.count()).select_from(User)) == 1
            assert session.scalar(select(func.count()).select_from(AuditLog)) == 0


def test_anonymous_cannot_create_staff(auth_client: TestClient) -> None:
    response = auth_client.post("/api/v1/users/staff", json={"email": "staff@example.com", "password": TEST_PASSWORD})
    assert response.status_code == 401


def test_permissions_use_current_database_role(auth_client: TestClient, make_user, bearer_headers) -> None:
    user = make_user(UserRole.ADMIN)
    headers = bearer_headers(user)
    with auth_client.app.state.session_factory() as session, session.begin():
        session.execute(update(User).where(User.id == user.id).values(role=UserRole.CUSTOMER))
    response = auth_client.post("/api/v1/users/staff", headers=headers,
                                json={"email": "staff@example.com", "password": TEST_PASSWORD})
    assert response.status_code == 403
    assert auth_client.get("/api/v1/auth/me", headers=headers).json()["role"] == "customer"


def test_signed_role_claim_cannot_grant_privileges(
    auth_client: TestClient, auth_settings: Settings, make_user, clock: ManualClock,
) -> None:
    user = make_user()
    now = int(clock().timestamp())
    token = jwt.encode({
        "sub": str(user.id), "iat": now, "exp": now + 7200, "auth_version": 0,
        "iss": ISSUER, "aud": AUDIENCE, "role": "admin",
    }, signing_key(auth_settings), algorithm="HS256")
    response = auth_client.post(
        "/api/v1/users/staff", headers={"Authorization": "Bearer " + token},
        json={"email": "staff@example.com", "password": TEST_PASSWORD},
    )
    assert response.status_code == 403


def test_staff_validation_and_duplicate_conflict_do_not_write_failed_audits(
    auth_client: TestClient, make_user, bearer_headers,
) -> None:
    headers = bearer_headers(make_user(UserRole.ADMIN))
    invalid = auth_client.post("/api/v1/users/staff", headers=headers,
                               json={"email": "staff@example.com", "password": "weak"})
    assert invalid.status_code == 422
    assert invalid.json()["detail"][0]["loc"][-1] == "password"
    valid_body = {"email": "Staff@example.com", "password": TEST_PASSWORD}
    assert auth_client.post("/api/v1/users/staff", headers=headers, json=valid_body).status_code == 201
    valid_body["email"] = "STAFF@EXAMPLE.COM"
    assert auth_client.post("/api/v1/users/staff", headers=headers, json=valid_body).status_code == 409
    with auth_client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 2
        assert session.scalar(select(func.count()).select_from(AuditLog)) == 1


@pytest.mark.parametrize("missing", ["sub", "iat", "exp", "auth_version", "iss", "aud"])
def test_every_expected_jwt_claim_is_mandatory(
    auth_client: TestClient, auth_settings: Settings, make_user, clock: ManualClock, missing: str,
) -> None:
    user = make_user()
    now = int(clock().timestamp())
    claims = {"sub": str(user.id), "iat": now, "exp": now + 7200, "auth_version": 0,
              "iss": ISSUER, "aud": AUDIENCE}
    del claims[missing]
    token = jwt.encode(claims, signing_key(auth_settings), algorithm="HS256")
    assert auth_client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token}).status_code == 401


def test_principal_is_immutable_and_auth_does_not_begin_business_transaction(auth_client: TestClient, make_user, bearer_headers, monkeypatch) -> None:
    from app.api.v1 import users

    user = make_user(UserRole.ADMIN)
    headers = bearer_headers(user)
    original = users.create_account
    captured = []

    def instrument(session, **kwargs):
        assert not session.in_transaction()
        captured.append(kwargs["actor"])
        return original(session, **kwargs)

    monkeypatch.setattr(users, "create_account", instrument)
    response = auth_client.post("/api/v1/users/staff", headers=headers,
                                json={"email": "staff@example.com", "password": TEST_PASSWORD})
    assert response.status_code == 201
    assert isinstance(captured[0], Principal)
    with pytest.raises(FrozenInstanceError):
        captured[0].role = UserRole.CUSTOMER


@pytest.mark.parametrize("secret", [None, "", "short", "x" * 40])
def test_auth_fails_closed_without_strong_secret(auth_settings: Settings, secret: str | None) -> None:
    settings = auth_settings.model_copy(update={"auth_secret_key": None})
    if secret is not None:
        from pydantic import SecretStr
        settings.auth_secret_key = SecretStr(secret)
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/health").status_code == 200
        for path, body in [
            ("signup", {"email": "new@example.com", "password": TEST_PASSWORD}),
            ("login", {"email": "new@example.com", "password": TEST_PASSWORD}),
            ("password-reset/request", {"email": "new@example.com"}),
            ("password-reset/confirm", {"token": "test-token", "new_password": TEST_PASSWORD}),
        ]:
            assert client.post("/api/v1/auth/" + path, json=body).status_code == 503
