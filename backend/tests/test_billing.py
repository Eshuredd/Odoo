from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier

import pytest
from alembic import command
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import IntegrityError

from app.core.principal import Principal
from app.db.session import create_db_engine, create_session_factory
from app.models import AuditLog, Discount, DiscountRedemption, Invoice, Subscription, User, UserRole
from app.services import billing
from conftest import TEST_PASSWORD, migration_config


def run(c, as_of="2026-04-30", dry=True):
    return c.call("POST", "/billing/preview" if dry else "/billing/run", json={"as_of": as_of})


def active(c, **overrides):
    as_of = overrides.get("start_date", "2026-01-15")
    row = c.call("POST", "/subscriptions", 201, json=c.draft_body(**{**overrides, "as_of": as_of}))
    for action in ("quotation", "confirm", "activate"):
        row = c.action(row["id"], action, as_of=as_of)
    return row


def discount(c, **values):
    return c.call("POST", "/discounts", 201, json={"name": "Synthetic promotion", "discount_type": "fixed",
        "scope": "subscription", "value_paise": 10000, "valid_from": "2026-01-01", "valid_to": "2026-12-31", **values})


def dump(c):
    with c.client.app.state.session_factory.kw["bind"].connect() as connection:
        return list(connection.connection.driver_connection.iterdump())


def test_catch_up_preview_zero_writes_execution_parity_and_repeat(commerce):
    c = commerce
    sub = active(c, start_date="2026-01-31", expiry_date="2026-04-30")
    discount(c, usage_limit=2)
    before = dump(c)
    writes = []
    def inspect_sql(_conn, _cursor, statement, *_args):
        if statement.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE", "REPLACE"}:
            writes.append(statement)
    event.listen(c.client.app.state.session_factory.kw["bind"], "before_cursor_execute", inspect_sql)
    try:
        preview = run(c)
    finally:
        event.remove(c.client.app.state.session_factory.kw["bind"], "before_cursor_execute", inspect_sql)
    assert not writes and dump(c) == before
    assert preview["generated_or_proposed_invoice_count"] == 4
    assert [i["period_start"] for i in preview["invoices"]] == ["2026-01-31", "2026-02-28", "2026-03-31", "2026-04-30"]
    assert [i["discount_total_paise"] for i in preview["invoices"]] == [10000, 10000, 0, 0]
    assert preview["invoices"][-1]["period_end"] == "2026-05-31"
    actual = run(c, dry=False)
    assert actual["failed_count"] == 0 and actual["projected_or_actual_total_paise"] == preview["projected_or_actual_total_paise"]
    for predicted, generated in zip(preview["invoices"], actual["invoices"]):
        assert predicted["lines"] == generated["lines"]
        assert generated["invoice_number"].startswith("INV-") and generated["invoice_id"]
        assert generated["due_date"] == str(date.fromisoformat(generated["invoice_date"]) + timedelta(days=15))
    after = dump(c)
    repeat = run(c, dry=False)
    assert repeat["generated_or_proposed_invoice_count"] == 0 and repeat["projected_or_actual_total_paise"] == 0
    # no eligible subscriptions: even timestamps/audits/counters stay unchanged.
    assert dump(c) == after
    assert c.call("GET", "/discounts/1")["times_used"] == 2
    assert c.call("GET", f"/subscriptions/{sub['id']}")["next_invoice_date"] == "2026-05-31"


@pytest.mark.parametrize("cadence,start,as_of,count,next_date", [
    ("daily", "2026-01-15", "2026-01-17", 3, "2026-01-18"),
    ("weekly", "2026-01-15", "2026-01-29", 3, "2026-02-05"),
    ("monthly", "2026-01-31", "2026-02-28", 2, "2026-03-31"),
    ("yearly", "2024-02-29", "2028-02-29", 5, "2029-02-28"),
])
def test_frequencies_and_boundary(cadence, start, as_of, count, next_date, commerce):
    c = commerce
    c.call("PATCH", f"/plans/{c.plan['id']}", json={"billing_period": cadence, "valid_from": "2024-01-01", "valid_to": "2030-12-31"})
    row = c.call("POST", "/subscriptions", 201, json=c.draft_body(start_date=start, as_of=start, expiry_date="2030-12-31"))
    for action in ("quotation", "confirm", "activate"):
        c.action(row["id"], action, as_of=start)
    value = run(c, as_of=as_of, dry=False)
    assert value["generated_or_proposed_invoice_count"] == count and value["failed_count"] == 0
    assert c.call("GET", f"/subscriptions/{row['id']}")["next_invoice_date"] == next_date


def test_pause_defers_resume_catches_up_and_auto_close_independent_of_manual_permission(commerce):
    c = commerce
    c.call("PATCH", f"/plans/{c.plan['id']}", json={"auto_close": True, "closable": False})
    sub = c.subscription("active", expiry_date="2026-02-01")
    c.action(sub["id"], "pause")
    assert run(c, dry=False)["skipped_count"] == 1
    assert c.call("GET", f"/subscriptions/{sub['id']}")["next_invoice_date"] == "2026-01-15"
    c.action(sub["id"], "resume")
    preview = run(c, as_of="2026-02-02")  # expiry passed but next monthly boundary is in the future.
    assert preview["auto_closed_subscription_ids"] == [sub["id"]]
    assert preview["generated_or_proposed_invoice_count"] == 1
    value = run(c, as_of="2026-02-02", dry=False)
    assert value["auto_closed_subscription_ids"] == [sub["id"]]
    closed = c.call("GET", f"/subscriptions/{sub['id']}")
    assert closed["status"] == "closed" and closed["next_invoice_date"] is None
    with c.client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "subscription.auto_closed")) == 1


def test_autoclose_after_prior_run_and_expiry_without_due_boundary(commerce):
    c = commerce
    c.call("PATCH", f"/plans/{c.plan['id']}", json={"auto_close": True})
    sub = c.subscription("active", expiry_date="2026-01-20")
    assert run(c, "2026-01-15", False)["generated_or_proposed_invoice_count"] == 1
    assert run(c, "2026-01-21", False)["auto_closed_subscription_ids"] == [sub["id"]]


def test_expired_without_auto_close_stays_open_and_repeat_changes_nothing(commerce):
    c = commerce
    sub = c.subscription("active", expiry_date="2026-01-20")
    result = run(c, "2026-04-30", False)
    assert result["generated_or_proposed_invoice_count"] == 1
    assert result["invoices"][0]["period_end"] == "2026-02-15"
    row = c.call("GET", f"/subscriptions/{sub['id']}")
    assert row["status"] == "active" and row["next_invoice_date"] == "2026-02-15"
    before = dump(c)
    assert run(c, "2026-04-30", False)["generated_or_proposed_invoice_count"] == 0
    assert dump(c) == before


def test_paid_invoice_cannot_be_cancelled(commerce):
    c = commerce
    c.subscription("active")
    identifier = run(c, "2026-01-15", False)["invoices"][0]["invoice_id"]
    # Stage 5 is absent: deliberately install a reserved paid fixture only in this isolated database.
    with c.client.app.state.session_factory.kw["bind"].begin() as connection:
        connection.execute(text("DROP TRIGGER invoice_status_transition"))
        connection.execute(text("UPDATE invoices SET status='paid' WHERE id=:id"), {"id": identifier})
    c.call("POST", f"/invoices/{identifier}/cancel", 409)
    c.call("POST", f"/invoices/{identifier}/confirm", 409)
    assert c.call("GET", f"/invoices/{identifier}")["status"] == "paid"


def test_failure_rolls_back_all_periods_redemptions_audits_and_schedule_then_continues(commerce, monkeypatch):
    c = commerce
    bad = c.subscription("active")
    good = c.subscription("active")
    discount(c, usage_limit=3)
    original = billing.record_event
    def fail(session, **kwargs):
        if kwargs["action"] == "invoice.generated" and kwargs["detail"]["subscription_id"] == bad["id"] and kwargs["detail"]["period_start"] == "2026-02-15":
            raise ValueError("Injected failure after first invoice and redemption")
        original(session, **kwargs)
    monkeypatch.setattr(billing, "record_event", fail)
    result = run(c, "2026-02-15", False)
    assert result["failed_count"] == 1 and result["generated_or_proposed_invoice_count"] == 2
    assert all(i["subscription_id"] == good["id"] for i in result["invoices"])
    assert c.call("GET", f"/subscriptions/{bad['id']}")["next_invoice_date"] == "2026-01-15"
    assert c.call("GET", "/discounts/1")["times_used"] == 2
    with c.client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(DiscountRedemption)) == 2
        assert session.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "invoice.generated")) == 2


def test_preview_failure_restores_simulated_discount_usage(commerce, monkeypatch):
    c = commerce
    c.subscription("active")
    good = c.subscription("active")
    discount(c, usage_limit=1)
    original = billing.price_invoice
    calls = 0
    def fail(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("Injected preview error")
        return original(*args)
    monkeypatch.setattr(billing, "price_invoice", fail)
    before = dump(c)
    report = run(c, "2026-02-15")
    assert report["failed_count"] == 1 and len(report["invoices"]) == 2
    assert report["invoices"][0]["subscription_id"] == good["id"]
    assert [i["discount_total_paise"] for i in report["invoices"]] == [10000, 0]
    assert dump(c) == before


def test_concurrent_billing_separate_connections_and_global_limit(commerce):
    c = commerce
    c.subscription("active")
    c.subscription("active")
    discount(c, usage_limit=1)
    with c.client.app.state.session_factory() as session:
        actor = Principal.from_user(session.scalar(select(User).where(User.role == UserRole.ADMIN)))
    url = str(c.client.app.state.session_factory.kw["bind"].url)
    barrier = Barrier(2)
    connections = []
    def execute():
        engine = create_db_engine(url)
        @event.listens_for(engine, "connect")
        def record(connection, _):
            connections.append(connection)
        try:
            barrier.wait(timeout=10)
            return billing.run_billing(create_session_factory(engine), date(2026, 2, 15), False, actor)
        finally:
            engine.dispose()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: execute(), range(2)))
    assert len({id(connection) for connection in connections}) >= 2
    assert sum(r.generated_or_proposed_invoice_count for r in results) == 4
    assert all(r.failed_count == 0 for r in results)
    assert c.call("GET", "/discounts/1")["times_used"] == 1
    assert c.call("GET", "/invoices")["total"] == 4


def test_invoice_snapshots_confirm_cancel_reserve_period_and_audit(commerce):
    c = commerce
    sub = c.subscription("active")
    promotion = discount(c)
    generated = run(c, "2026-01-15", False)["invoices"][0]
    identifier = generated["invoice_id"]
    path = f"/invoices/{identifier}"
    original = c.call("GET", path)
    c.call("PATCH", f"/products/{c.product['id']}", json={"sales_price_paise": 1, "name": "Changed"})
    c.call("PATCH", f"/plans/{c.plan['id']}", json={"price_paise": 1})
    c.call("PATCH", f"/discounts/{promotion['id']}", json={"value_paise": 1, "name": "Changed"})
    assert c.call("GET", path) == original
    assert c.call("POST", path + "/confirm")["status"] == "confirmed"
    c.call("POST", path + "/confirm", 409)
    assert c.call("POST", path + "/cancel")["status"] == "cancelled"
    c.call("POST", path + "/cancel", 409)
    c.call("POST", path + "/confirm", 409)
    assert c.call("GET", "/discounts/1")["times_used"] == 1
    # Simulate a stale schedule: even a cancelled period cannot be billed again.
    with c.client.app.state.session_factory() as session, session.begin():
        session.get(Subscription, sub["id"]).next_invoice_date = date(2026, 1, 15)
    repeated = run(c, "2026-01-15", False)
    assert repeated["generated_or_proposed_invoice_count"] == 0 and len(repeated["existing_invoices"]) == 1
    assert repeated["existing_invoices"][0]["invoice_id"] == identifier
    with c.client.app.state.session_factory() as session:
        actions = set(session.scalars(select(AuditLog.action)))
        assert {"invoice.confirm", "invoice.cancel", "invoice.generated", "discount.redeemed"} <= actions


@pytest.mark.parametrize("changes", [
    {"rate_basis_points": 100}, {"discount_type": "percentage"}, {"value_paise": -1},
    {"value_paise": 1.5}, {"scope": "product"}, {"product_id": 999}, {"minimum_quantity": 0},
    {"valid_to": "2025-01-01"}, {"usage_limit": -1}, {"times_used": 5},
    {"discount_type": "percentage", "value_paise": None, "rate_basis_points": 10001},
])
def test_invalid_discounts_rejected(commerce, changes):
    c = commerce
    c.call("POST", "/discounts", 422, json={"name": "Invalid", "discount_type": "fixed", "scope": "subscription",
        "value_paise": 100, "valid_from": "2026-01-01", "valid_to": "2026-12-31", **changes})


def test_roles_ownership_invoice_filters_and_discount_patch(commerce, make_user, bearer_headers):
    c = commerce
    sub = c.subscription("active")
    discount(c, usage_limit=1)
    inv = run(c, "2026-02-15", False)["invoices"][0]["invoice_id"]
    staff = bearer_headers(make_user(UserRole.STAFF))
    with c.client.app.state.session_factory() as session:
        buyer = session.scalar(select(User).where(User.email == "buyer@example.com"))
    owner = bearer_headers(buyer)
    other = bearer_headers(make_user(UserRole.CUSTOMER, "outsider@example.com"))
    for headers, expected in (({}, 401), (owner, 403), (other, 403)):
        c.call("POST", "/billing/preview", expected, headers=headers, json={"as_of": "2026-01-15"})
        c.call("POST", "/billing/run", expected, headers=headers, json={"as_of": "2026-01-15"})
    c.call("GET", "/discounts", headers=staff)
    c.call("PATCH", "/discounts/1", 403, headers=staff, json={"active": False})
    c.call("GET", "/discounts", 403, headers=owner)
    c.call("GET", f"/invoices/{inv}", headers=owner)
    c.call("GET", f"/invoices/{inv}", 404, headers=other)
    assert c.call("GET", "/invoices", headers=other)["total"] == 0
    assert c.call("GET", "/invoices", headers=owner)["total"] == 2
    c.call("POST", f"/invoices/{inv}/confirm", 403, headers=owner)
    c.call("POST", f"/invoices/{inv}/confirm", headers=staff)
    c.call("POST", f"/invoices/{inv}/cancel", headers=staff)
    assert c.call("GET", f"/invoices?status=cancelled&subscription_id={sub['id']}")["total"] == 1
    assert c.call("GET", "/invoices?due_from=2026-03-01")["total"] == 1
    assert c.call("GET", "/invoices?limit=1&offset=1")["items"][0]["id"] == inv
    c.call("GET", "/invoices?customer_id=1", 403, headers=owner)
    c.call("GET", "/invoices?due_from=2026-03-01&due_to=2026-01-01", 422)
    c.call("PATCH", "/discounts/1", 422, json={"usage_limit": 0})
    c.call("PATCH", "/discounts/1", 422, json={"name": None})
    c.call("PATCH", "/discounts/1", json={"discount_type": "percentage", "value_paise": None, "rate_basis_points": 500})
    assert c.call("GET", "/discounts?active=true&as_of=2026-01-01&limit=1")["total"] == 1


@pytest.mark.parametrize("statement", [
    "UPDATE discounts SET value_paise=-1", "UPDATE discounts SET times_used=-1", "UPDATE discounts SET rate_basis_points=1",
    "UPDATE discounts SET times_used=2, usage_limit=1", "UPDATE discounts SET scope='product'", "UPDATE discounts SET active=2",
    "UPDATE invoice_lines SET description='altered'", "DELETE FROM invoice_lines", "DELETE FROM invoices",
    "UPDATE invoices SET total_paise=total_paise+1", "UPDATE invoices SET status='paid'", "UPDATE invoices SET sealed=0",
    "DELETE FROM discount_redemptions", "UPDATE discount_redemptions SET discount_id=999",
    "INSERT INTO discount_redemptions(discount_id,invoice_id,redeemed_at) SELECT discount_id,invoice_id,redeemed_at FROM discount_redemptions",
    "INSERT INTO invoice_lines(invoice_id,line_type,description,quantity,unit_price_paise,subtotal_paise,discount_paise,taxable_amount_paise,tax_rate_basis_points,tax_paise,total_paise) VALUES(1,'plan','Injected',1,0,0,0,0,0,0,0)",
])
def test_database_financial_guards(commerce, statement):
    c = commerce
    c.subscription("active")
    discount(c)
    assert run(c, "2026-01-15", False)["failed_count"] == 0
    with pytest.raises(IntegrityError), c.client.app.state.session_factory.kw["bind"].begin() as connection:
        connection.execute(text(statement))


def test_migration_upgrade_check_downgrade_preserves_stage3(commerce):
    c = commerce
    sub = c.subscription("active")
    config = migration_config(str(c.client.app.state.session_factory.kw["bind"].url))
    command.check(config)
    command.downgrade(config, "0003_commercial")
    assert c.call("GET", f"/subscriptions/{sub['id']}")["status"] == "active"
    command.upgrade(config, "head")
    command.check(config)
