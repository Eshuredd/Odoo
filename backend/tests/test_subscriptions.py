from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.errors import ServiceError
from app.core.principal import Principal
from app.db.session import create_db_engine, create_session_factory
from app.models import AuditLog, Subscription, User, UserRole
from app.schemas.commercial import SubscriptionCreate
from app.services.subscriptions import create_subscription
from commercial_helpers import AS_OF
from conftest import TEST_PASSWORD


def audit_count(commerce) -> int:
    with commerce.client.app.state.session_factory() as session:
        return session.scalar(select(func.count()).select_from(AuditLog))


def test_draft_and_complete_lifecycle(commerce) -> None:
    row = commerce.subscription()
    assert row["status"] == "draft"
    assert row["number"] == f"SUB-{row['id']:06d}"
    assert row["customer_id"] == commerce.customer_id
    assert row["recurring_base_price_paise"] == 50000
    assert row["lines"][0]["unit_price_paise"] == 66000
    assert row["lines"][0]["amount_paise"] == 132000
    assert row["lines"][0]["tax_rate_basis_points"] == 1800
    assert row["next_invoice_date"] is None
    assert row["commercial_snapshot"] is None
    row = commerce.action(row["id"], "quotation", validity_days=14)
    assert row["quotation_date"] == AS_OF
    assert row["quotation_expiry_date"] == "2026-01-29"
    row = commerce.action(row["id"], "confirm", as_of="2026-01-29")
    assert row["status"] == "confirmed"
    assert row["commercial_snapshot"]["plan"]["min_quantity"] == 2
    row = commerce.action(row["id"], "activate", as_of="2026-02-20")
    assert row["next_invoice_date"] == AS_OF  # Delayed activation must preserve missed periods.
    assert row["billing_period"] == "monthly"
    row = commerce.action(row["id"], "close", as_of="2026-02-21")
    assert row["status"] == "closed"
    assert row["next_invoice_date"] is None
    commerce.action(row["id"], "activate", 409)
    with commerce.client.app.state.session_factory() as session:
        events = session.scalars(select(AuditLog).where(AuditLog.entity == "subscription").order_by(AuditLog.id)).all()
        assert [event.action for event in events] == [
            "subscription.created", "subscription.quotation", "subscription.confirm",
            "subscription.activate", "subscription.close",
        ]
        assert events[-1].detail["from"] == "active"
        assert events[-1].detail["to"] == "closed"


@pytest.mark.parametrize("action", ["confirm", "activate", "close", "pause", "resume", "renew"])
def test_illegal_draft_transitions_are_conflicts_with_no_writes(commerce, action: str) -> None:
    row = commerce.subscription()
    before = audit_count(commerce)
    extra = {"new_expiry_date": "2027-01-15"} if action == "renew" else {}
    commerce.action(row["id"], action, 409, **extra)
    assert commerce.call("GET", f"/subscriptions/{row['id']}") == row
    assert audit_count(commerce) == before


@pytest.mark.parametrize("overrides", [
    {"customer_id": 9999}, {"plan_id": 9999}, {"expiry_date": "2026-01-01"},
    {"payment_terms_days": -1}, {"payment_terms_days": 1.5}, {"lines": []},
    {"lines": [{"product_id": 1, "quantity": 0}]},
    {"lines": [{"product_id": 1, "quantity": 1}]},
    {"lines": [{"product_id": 9999, "quantity": 2}]},
])
def test_subscription_creation_validation_rolls_back(commerce, overrides: dict) -> None:
    before = audit_count(commerce)
    commerce.call("POST", "/subscriptions", 422, json=commerce.draft_body(**overrides))
    assert commerce.call("GET", "/subscriptions")["total"] == 0
    assert audit_count(commerce) == before


def test_quantity_minimum_is_sum_of_all_product_lines(commerce) -> None:
    lines = [{"product_id": commerce.product["id"], "quantity": 1},
             {"product_id": commerce.product["id"], "variant_id": commerce.variant["id"], "quantity": 1}]
    row = commerce.subscription(lines=lines)
    assert [line["amount_paise"] for line in row["lines"]] == [10000, 66000]


def test_variant_product_mismatch_is_rejected(commerce) -> None:
    other = commerce.call("POST", "/products", 201, json={"name": "Other", "product_type": "goods", "sales_price_paise": 1})
    commerce.call("POST", "/subscriptions", 422, json=commerce.draft_body(
        lines=[{"product_id": other["id"], "variant_id": commerce.variant["id"], "quantity": 2}],
    ))


@pytest.mark.parametrize("patch,as_of", [({"active": False}, AS_OF), ({}, "2027-01-01"), ({}, "2025-12-31")])
def test_unavailable_plans_cannot_be_selected(commerce, patch: dict, as_of: str) -> None:
    if patch:
        commerce.call("PATCH", f"/plans/{commerce.plan['id']}", json=patch)
    commerce.call("POST", "/subscriptions", 422, json=commerce.draft_body(as_of=as_of, expiry_date="2027-06-01"))
    body = commerce.draft_body(as_of=as_of, expiry_date="2027-06-01")
    body.pop("plan_id")
    body.pop("lines")
    commerce.call("POST", "/subscriptions/from-template", 422, json={**body, "template_id": commerce.template["id"]})


@pytest.mark.parametrize("resource", ["products", "variants", "taxes"])
def test_inactive_catalog_items_are_rejected_for_new_sales(commerce, resource: str) -> None:
    path = {"products": f"/products/{commerce.product['id']}",
            "variants": f"/products/{commerce.product['id']}/variants/{commerce.variant['id']}",
            "taxes": f"/taxes/{commerce.tax['id']}"}[resource]
    commerce.call("PATCH", path, json={"active": False})
    commerce.call("POST", "/subscriptions", 422, json=commerce.draft_body())


def test_confirmation_revalidates_minimum_and_expiry(commerce) -> None:
    row = commerce.subscription("quotation")
    commerce.action(row["id"], "confirm", 409, as_of="2026-02-15")
    commerce.call("PATCH", f"/plans/{commerce.plan['id']}", json={"min_quantity": 3})
    commerce.action(row["id"], "confirm", 422)
    assert commerce.call("GET", f"/subscriptions/{row['id']}")["status"] == "quotation"


def test_snapshots_freeze_prices_taxes_names_period_and_plan_flags(commerce) -> None:
    row = commerce.subscription("quotation")
    commerce.call("PATCH", f"/products/{commerce.product['id']}", json={"sales_price_paise": 20000})
    commerce.call("PATCH", f"/taxes/{commerce.tax['id']}", json={"rate_basis_points": 2000})
    row = commerce.action(row["id"], "confirm")
    assert row["lines"][0]["unit_price_paise"] == 76000
    assert row["lines"][0]["amount_paise"] == 152000
    assert row["lines"][0]["tax_rate_basis_points"] == 2000
    for path, patch in [
        (f"/products/{commerce.product['id']}", {"sales_price_paise": 90000, "name": "Changed", "active": False}),
        (f"/products/{commerce.product['id']}/variants/{commerce.variant['id']}", {"extra_price_paise": 90000}),
        (f"/taxes/{commerce.tax['id']}", {"rate_basis_points": 500}),
        (f"/plans/{commerce.plan['id']}", {"price_paise": 99999, "billing_period": "daily", "closable": False, "pausable": False,
                                           "renewable": False, "active": False, "valid_to": AS_OF}),
    ]:
        commerce.call("PATCH", path, json=patch)
    current = commerce.call("GET", f"/subscriptions/{row['id']}")
    assert current == row
    assert current["commercial_snapshot"]["lines"][0]["product_name"] == "Software"
    active = commerce.action(row["id"], "activate", as_of="2026-02-01")
    assert active["billing_period"] == "monthly"
    commerce.action(row["id"], "pause")
    commerce.action(row["id"], "resume")
    commerce.action(row["id"], "renew", new_expiry_date="2027-06-15")
    commerce.action(row["id"], "close")


def test_pause_resume_and_renew_do_not_advance_billing_anchor(commerce) -> None:
    row = commerce.subscription("active")
    commerce.action(row["id"], "resume", 409)
    paused = commerce.action(row["id"], "pause")
    assert paused["is_paused"] is True
    assert paused["status"] == "active"
    assert paused["next_invoice_date"] == AS_OF
    commerce.action(row["id"], "pause", 409)
    resumed = commerce.action(row["id"], "resume")
    assert resumed["is_paused"] is False
    assert resumed["next_invoice_date"] == AS_OF
    commerce.action(row["id"], "renew", 409, new_expiry_date=row["expiry_date"])
    renewed = commerce.action(row["id"], "renew", new_expiry_date="2027-01-15")
    assert renewed["expiry_date"] == "2027-01-15"
    assert renewed["start_date"] == renewed["next_invoice_date"] == AS_OF
    commerce.action(row["id"], "close")
    commerce.action(row["id"], "resume", 409)
    commerce.action(row["id"], "renew", 409, new_expiry_date="2028-01-15")


@pytest.mark.parametrize("flag,action,extra", [
    ("closable", "close", {}), ("pausable", "pause", {}),
    ("renewable", "renew", {"new_expiry_date": "2027-01-15"}),
])
def test_plan_flags_restrict_actions(commerce, flag: str, action: str, extra: dict) -> None:
    commerce.call("PATCH", f"/plans/{commerce.plan['id']}", json={flag: False})
    row = commerce.subscription("active")
    commerce.action(row["id"], action, 409, **extra)
    assert commerce.call("GET", f"/subscriptions/{row['id']}") == row


def test_transition_failure_rolls_back_subscription_and_audit(commerce, monkeypatch) -> None:
    from app.services import subscriptions

    row = commerce.subscription("quotation")
    before = audit_count(commerce)

    def reject_audit(*args, **kwargs) -> None:
        raise ServiceError(503, "Synthetic audit failure")

    monkeypatch.setattr(subscriptions, "record_event", reject_audit)
    commerce.action(row["id"], "confirm", 503)
    assert commerce.call("GET", f"/subscriptions/{row['id']}") == row
    assert audit_count(commerce) == before


def test_staff_operates_subscriptions_and_customer_reads_only_own(commerce, make_user, bearer_headers) -> None:
    staff = bearer_headers(make_user(UserRole.STAFF))
    row = commerce.call("POST", "/subscriptions", 201, headers=staff, json=commerce.draft_body())
    commerce.call("POST", f"/subscriptions/{row['id']}/quotation", headers=staff, json={"as_of": AS_OF})
    commerce.call("POST", f"/subscriptions/{row['id']}/confirm", headers=staff, json={"as_of": AS_OF})
    commerce.call("POST", f"/subscriptions/{row['id']}/activate", headers=staff, json={"as_of": AS_OF})
    commerce.call("POST", "/auth/signup", 201, json={"email": "other@example.com", "password": TEST_PASSWORD})
    other_user = commerce.call("POST", "/auth/login", json={"email": "other@example.com", "password": TEST_PASSWORD})
    other_headers = {"Authorization": "Bearer " + other_user["access_token"]}
    other_profile = commerce.call("GET", "/customers/me", headers=other_headers)
    other_sub = commerce.subscription(customer_id=other_profile["id"])
    buyer = commerce.call("POST", "/auth/login", json={"email": "buyer@example.com", "password": TEST_PASSWORD})
    headers = {"Authorization": "Bearer " + buyer["access_token"]}
    own = commerce.call("GET", "/subscriptions?limit=1", headers=headers)
    assert own["total"] == 1
    assert own["items"][0]["id"] == row["id"]
    commerce.call("GET", f"/subscriptions/{row['id']}", headers=headers)
    commerce.call("GET", f"/subscriptions/{other_sub['id']}", 404, headers=headers)
    assert commerce.call("GET", f"/subscriptions?customer_id={other_profile['id']}", headers=headers)["total"] == 0
    for action in ("quotation", "confirm", "activate", "close", "pause", "resume", "renew"):
        commerce.call("POST", f"/subscriptions/{row['id']}/{action}", 403, headers=headers,
                      json={"as_of": AS_OF, **({"new_expiry_date": "2027-01-01"} if action == "renew" else {})})
    commerce.call("POST", "/subscriptions", 403, headers=headers, json=commerce.draft_body())
    commerce.call("GET", "/subscriptions", 401, headers={})


def test_subscription_pagination_filters_do_not_duplicate_multiline_records(commerce) -> None:
    first = commerce.subscription()
    second = commerce.subscription("active", lines=commerce.lines() + commerce.lines())
    result = commerce.call("GET", f"/subscriptions?product_id={commerce.product['id']}&limit=1&offset=1")
    assert result["total"] == 2
    assert result["items"][0]["id"] == second["id"]
    assert commerce.call("GET", "/subscriptions?status=draft")["items"][0]["id"] == first["id"]
    assert commerce.call("GET", f"/subscriptions?plan_id={commerce.plan['id']}")["total"] == 2
    assert commerce.call("GET", f"/subscriptions?search={first['number']}")["total"] == 1
    commerce.call("GET", "/subscriptions?customer_id=999999999999999999999999", 422)
    commerce.call("GET", "/subscriptions/999999999999999999999999", 422)


def test_concurrent_numbers_use_distinct_database_generated_ids(commerce, migrated_url: str, clock) -> None:
    with commerce.client.app.state.session_factory() as session:
        actor = Principal.from_user(session.scalar(select(User).where(User.role == UserRole.ADMIN)))
    body = SubscriptionCreate.model_validate(commerce.draft_body())

    def create(_index: int) -> tuple[int, str]:
        engine = create_db_engine(migrated_url)
        try:
            with create_session_factory(engine)() as session:
                row = create_subscription(session, body, actor, clock)
                return row.id, row.number
        finally:
            engine.dispose()

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(create, range(4)))
    assert len({number for _, number in results}) == 4
    assert all(number == f"SUB-{identifier:06d}" for identifier, number in results)
