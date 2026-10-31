import pytest
from sqlalchemy import func, select

from app.models import AuditLog, CustomerProfile, User, UserRole
from conftest import TEST_PASSWORD


def test_signup_creates_profile_with_backwards_compatible_defaults(auth_client) -> None:
    response = auth_client.post("/api/v1/auth/signup", json={"email": "basic@example.com", "password": TEST_PASSWORD})
    assert response.status_code == 201
    with auth_client.app.state.session_factory() as session:
        profile = session.scalar(select(CustomerProfile))
        assert profile.user_id == response.json()["id"]
        assert profile.company_name == ""
        assert profile.contact_name == "basic"


@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.STAFF])
def test_operator_can_create_customer_but_not_staff_privileges(commerce, make_user, bearer_headers, role: UserRole) -> None:
    headers = commerce.headers if role == UserRole.ADMIN else bearer_headers(make_user(role))
    body = {"email": "created@example.com", "password": TEST_PASSWORD,
            "company_name": "Created Co", "contact_name": "Created Person", "notes": "Synthetic"}
    profile = commerce.call("POST", "/customers", 201, headers=headers, json=body)
    assert profile["company_name"] == "Created Co"
    with commerce.client.app.state.session_factory() as session:
        assert session.get(User, profile["user_id"]).role == UserRole.CUSTOMER
    body["email"] = "CREATED@EXAMPLE.COM"
    commerce.call("POST", "/customers", 409, headers=headers, json=body)
    commerce.call("POST", "/customers", 422, headers=headers, json={**body, "role": "admin"})
    if role == UserRole.STAFF:
        commerce.call("POST", "/users/staff", 403, headers=headers, json={"email": "staff2@example.com", "password": TEST_PASSWORD})


def test_customer_profile_ownership_and_safe_updates(commerce) -> None:
    commerce.call("POST", "/auth/signup", 201, json={"email": "other@example.com", "password": TEST_PASSWORD})
    login = commerce.call("POST", "/auth/login", json={"email": "buyer@example.com", "password": TEST_PASSWORD})
    headers = {"Authorization": "Bearer " + login["access_token"]}
    own = commerce.call("GET", "/customers/me", headers=headers)
    assert own["id"] == commerce.customer_id
    result = commerce.call("GET", "/customers?limit=1", headers=headers)
    assert result["total"] == 1
    assert result["items"][0]["user_id"] == login["user"]["id"]
    other_id = commerce.call("GET", "/customers")["items"][1]["id"]
    commerce.call("GET", f"/customers/{other_id}", 404, headers=headers)
    commerce.call("PATCH", f"/customers/{other_id}", 404, headers=headers, json={"contact_name": "Attack"})
    updated = commerce.call("PATCH", f"/customers/{own['id']}", headers=headers,
                            json={"company_name": "Updated", "phone": "555-0100"})
    assert updated["company_name"] == "Updated"
    commerce.call("PATCH", f"/customers/{own['id']}", 403, headers=headers, json={"notes": "Private"})
    commerce.call("PATCH", f"/customers/{own['id']}", 422, headers=headers, json={"user_id": 999})
    commerce.call("POST", "/customers", 403, headers=headers, json={})


def test_signup_profile_and_user_roll_back_together(auth_client, monkeypatch) -> None:
    from app.services import auth

    original = auth.CustomerProfile

    def invalid_profile(**kwargs):
        return original(**{**kwargs, "contact_name": None})

    monkeypatch.setattr(auth, "CustomerProfile", invalid_profile)
    response = auth_client.post("/api/v1/auth/signup", json={"email": "rollback@example.com", "password": TEST_PASSWORD})
    assert response.status_code == 503
    with auth_client.app.state.session_factory() as session:
        for model in (User, CustomerProfile, AuditLog):
            assert session.scalar(select(func.count()).select_from(model)) == 0
