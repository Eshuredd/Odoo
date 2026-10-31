import pytest
from alembic import command
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.db.session import create_db_engine
from app.models import CustomerProfile
from conftest import migration_config


def test_stage2_upgrade_backfills_profiles_and_preserves_authentication(database_url: str) -> None:
    config = migration_config(database_url)
    command.upgrade(config, "0002_authentication")
    engine = create_db_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("""
                INSERT INTO users (id, email, password_hash, role, auth_version)
                VALUES (7, 'legacy@example.com', 'opaque-existing-hash', 'customer', 3),
                       (8, 'admin@example.com', 'opaque-admin-hash', 'admin', 2)
            """))
            connection.execute(text("""
                INSERT INTO audit_logs (actor_id, action, entity, entity_id)
                VALUES (7, 'existing', 'user', '7')
            """))
            connection.execute(text("""
                INSERT INTO password_reset_tokens (user_id, token_hash, expires_at)
                VALUES (7, 'existing-test-digest', '2026-12-01 00:00:00')
            """))
        command.upgrade(config, "head")
        command.check(config)
        with engine.connect() as connection:
            assert tuple(connection.execute(text(
                "SELECT email, password_hash, role, auth_version FROM users WHERE id=7"
            )).one()) == ("legacy@example.com", "opaque-existing-hash", "customer", 3)
            assert connection.scalar(text("SELECT actor_id FROM audit_logs")) == 7
            assert connection.scalar(text("SELECT token_hash FROM password_reset_tokens")) == "existing-test-digest"
            assert tuple(connection.execute(text("SELECT user_id, company_name, contact_name FROM customer_profiles")).one()) == (7, "", "legacy")
            assert connection.scalar(text("PRAGMA foreign_key_check")) is None
        indexes = inspect(engine).get_indexes("subscriptions")
        assert any(index["column_names"] == ["status", "next_invoice_date"] for index in indexes)
        command.upgrade(config, "head")
        command.downgrade(config, "0002_authentication")
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT actor_id FROM audit_logs")) == 7
            assert connection.scalar(text("SELECT auth_version FROM users WHERE id=7")) == 3
        command.upgrade(config, "head")
    finally:
        engine.dispose()


@pytest.mark.parametrize("statement", [
    "UPDATE products SET sales_price_paise=-1",
    "UPDATE products SET cost_price_paise=1.5",
    "UPDATE products SET name='   '",
    "UPDATE products SET product_type='invalid'",
    "UPDATE products SET tax_id=9999",
    "UPDATE product_variants SET extra_price_paise=-1",
    "UPDATE plans SET min_quantity=0",
    "UPDATE plans SET billing_period='hourly'",
    "UPDATE plans SET valid_to='2025-01-01'",
    "UPDATE plans SET price_paise=-1",
    "UPDATE taxes SET rate_basis_points=-1",
    "UPDATE taxes SET rate_basis_points=10001",
    "UPDATE quotation_template_lines SET quantity=0",
    "UPDATE customer_profiles SET user_id=9999",
    "UPDATE customer_profiles SET user_id=1",
    "UPDATE users SET role='staff' WHERE email='buyer@example.com'",
])
def test_direct_sql_constraints_reject_invalid_writes(commerce, statement: str) -> None:
    with pytest.raises(IntegrityError), commerce.client.app.state.session_factory() as session, session.begin():
        session.execute(text(statement))


def test_variant_pair_constraint_and_historical_references(commerce) -> None:
    row = commerce.subscription()
    other = commerce.call("POST", "/products", 201, json={"name": "Other", "product_type": "goods", "sales_price_paise": 100})
    with pytest.raises(IntegrityError), commerce.client.app.state.session_factory() as session, session.begin():
        session.execute(text("UPDATE subscription_lines SET product_id=:id"), {"id": other["id"]})
    with pytest.raises(IntegrityError), commerce.client.app.state.session_factory() as session, session.begin():
        session.execute(text("DELETE FROM products WHERE id=:id"), {"id": commerce.product["id"]})
    assert commerce.call("GET", f"/subscriptions/{row['id']}") == row


@pytest.mark.parametrize("statement", [
    "UPDATE subscriptions SET recurring_base_price_paise=1",
    "UPDATE subscriptions SET start_date='2026-02-01'",
    "UPDATE subscriptions SET payment_terms_days=30",
    "UPDATE subscription_lines SET quantity=1, amount_paise=unit_price_paise",
    "DELETE FROM subscription_lines",
])
def test_confirmed_snapshots_are_frozen_even_with_raw_sql(commerce, statement: str) -> None:
    row = commerce.subscription("confirmed")
    with pytest.raises(IntegrityError), commerce.client.app.state.session_factory() as session, session.begin():
        session.execute(text(statement))
    assert commerce.call("GET", f"/subscriptions/{row['id']}") == row


def test_direct_subscription_constraints_and_state_machine(commerce) -> None:
    row = commerce.subscription()
    for statement in (
        "UPDATE subscriptions SET status='bogus'",
        "UPDATE subscriptions SET status='active', next_invoice_date=start_date",
        "UPDATE subscriptions SET is_paused=1",
        "UPDATE subscriptions SET payment_terms_days=-1",
        "UPDATE subscriptions SET expiry_date='2025-01-01'",
        "UPDATE subscription_lines SET amount_paise=1",
        "UPDATE subscription_lines SET tax_rate_basis_points=-1",
    ):
        with pytest.raises(IntegrityError), commerce.client.app.state.session_factory() as session, session.begin():
            session.execute(text(statement))
    assert commerce.call("GET", f"/subscriptions/{row['id']}") == row


def test_raw_sql_cannot_quote_below_minimum_quantity(commerce) -> None:
    row = commerce.subscription()
    with pytest.raises(IntegrityError), commerce.client.app.state.session_factory() as session, session.begin():
        session.execute(text("UPDATE subscription_lines SET quantity=1, amount_paise=unit_price_paise"))
        session.execute(text("""
            UPDATE subscriptions SET status='quotation', quotation_date='2026-01-15',
            quotation_expiry_date='2026-01-29'
        """))
    assert commerce.call("GET", f"/subscriptions/{row['id']}") == row
