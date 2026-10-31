import pytest
from sqlalchemy import func, select

from app.models import AuditLog, Product, UserRole


@pytest.mark.parametrize("field,value", [
    ("name", "  "), ("sales_price_paise", -1), ("cost_price_paise", -1),
    ("sales_price_paise", 1.5), ("sales_price_paise", True), ("sales_price_paise", "100"),
    ("product_type", "invalid"), ("tax_id", 9999),
])
def test_product_validation(commerce, field: str, value) -> None:
    body = {"name": "Product", "product_type": "goods", "sales_price_paise": 100, field: value}
    commerce.call("POST", "/products", 422, json=body)
    with commerce.client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Product)) == 1


def test_product_details_prices_and_deactivation(commerce) -> None:
    product = commerce.call("GET", f"/products/{commerce.product['id']}")
    assert product["tax_id"] == commerce.tax["id"]
    assert product["sales_price_paise"] == 10000
    variant = commerce.call("GET", f"/products/{product['id']}/variants/{commerce.variant['id']}")
    assert variant["extra_price_paise"] == 56000
    assert commerce.call("GET", f"/products/{product['id']}/variants?limit=1")["total"] == 1
    commerce.call("PATCH", f"/products/{product['id']}", json={"active": False, "tax_id": None})
    assert commerce.call("GET", "/products?active=false")["total"] == 1
    assert commerce.call("GET", "/products?active=true")["total"] == 0
    commerce.call("DELETE", f"/products/{product['id']}", 405)


@pytest.mark.parametrize("rate", [-1, 10001, 12.5, True])
def test_tax_rate_limits(commerce, rate) -> None:
    commerce.call("POST", "/taxes", 422, json={"name": "Invalid", "rate_basis_points": rate})


def test_tax_maximum_and_zero_are_valid(commerce) -> None:
    for rate in (0, 10000):
        tax = commerce.call("POST", "/taxes", 201, json={"name": "Allowed", "rate_basis_points": rate})
        assert commerce.call("GET", f"/taxes/{tax['id']}")["rate_basis_points"] == rate


@pytest.mark.parametrize("field,value", [
    ("billing_period", "hourly"), ("price_paise", -1), ("min_quantity", 0),
    ("valid_to", "2025-12-31"), ("auto_close", 1), ("price_paise", 1.0),
])
def test_plan_validation(commerce, field: str, value) -> None:
    body = {"name": "Invalid", "price_paise": 100, "billing_period": "monthly", "min_quantity": 1,
            "valid_from": "2026-01-01", "valid_to": "2026-12-31", field: value}
    commerce.call("POST", "/plans", 422, json=body)


@pytest.mark.parametrize("period", ["daily", "weekly", "monthly", "yearly"])
def test_all_billing_periods_and_independent_flags(commerce, period: str) -> None:
    plan = commerce.call("POST", "/plans", 201, json={
        "name": period, "price_paise": 0, "billing_period": period,
        "valid_from": "2026-01-01", "valid_to": "2026-01-01",
        "auto_close": True, "closable": False, "pausable": True, "renewable": False,
    })
    assert (plan["auto_close"], plan["closable"], plan["pausable"], plan["renewable"]) == (True, False, True, False)


def test_partial_plan_update_checks_merged_dates(commerce) -> None:
    commerce.call("PATCH", f"/plans/{commerce.plan['id']}", 422, json={"valid_from": "2027-01-01"})
    commerce.call("PATCH", f"/plans/{commerce.plan['id']}", 422, json={"valid_to": None})
    assert commerce.call("GET", f"/plans/{commerce.plan['id']}")["valid_from"] == "2026-01-01"


@pytest.mark.parametrize("resource", ["products", "taxes", "plans", "quotation-templates"])
def test_staff_reads_but_cannot_configure(commerce, make_user, bearer_headers, resource: str) -> None:
    headers = bearer_headers(make_user(UserRole.STAFF))
    commerce.call("GET", "/" + resource, headers=headers)
    commerce.call("POST", "/" + resource, 403, headers=headers, json={})
    commerce.call("PATCH", "/" + resource + "/1", 403, headers=headers, json={})


@pytest.mark.parametrize("resource", ["products", "taxes", "plans", "quotation-templates"])
def test_customers_cannot_access_admin_catalog(commerce, bearer_headers, make_user, resource: str) -> None:
    headers = bearer_headers(make_user(UserRole.CUSTOMER, "other@example.com"))
    commerce.call("GET", "/" + resource, 403, headers=headers)
    commerce.call("GET", "/" + resource, 401, headers={})


def test_variant_permissions_association_and_uniqueness(commerce, make_user, bearer_headers) -> None:
    product_id = commerce.product["id"]
    staff_headers = bearer_headers(make_user(UserRole.STAFF))
    commerce.call("GET", f"/products/{product_id}/variants", headers=staff_headers)
    commerce.call("POST", f"/products/{product_id}/variants", 403, headers=staff_headers, json={})
    commerce.call("POST", f"/products/{product_id}/variants", 409,
                  json={"attribute": "Brand", "value": "Odoo", "extra_price_paise": 10})
    commerce.call("POST", f"/products/{product_id}/variants", 422,
                  json={"attribute": "Brand", "value": "Other", "extra_price_paise": -1})
    commerce.call("PATCH", f"/products/{product_id + 1}/variants/{commerce.variant['id']}", 404, json={"active": False})


def test_pagination_search_and_filters_are_bounded(commerce) -> None:
    for name in ("Alpha", "Alphabet", "Beta"):
        commerce.call("POST", "/products", 201, json={"name": name, "product_type": "goods", "sales_price_paise": 0})
    first = commerce.call("GET", "/products?search=Alpha&limit=1&offset=0")
    second = commerce.call("GET", "/products?search=Alpha&limit=1&offset=1")
    assert first["total"] == second["total"] == 2
    assert first["items"][0]["id"] < second["items"][0]["id"]
    assert commerce.call("GET", "/products?search=%25")["total"] == 0
    assert commerce.call("GET", f"/products?tax_id={commerce.tax['id']}")["total"] == 1
    assert commerce.call("GET", "/plans?as_of=2027-01-01")["total"] == 0
    for path in ("products", "taxes", "plans", "quotation-templates"):
        commerce.call("GET", f"/{path}?limit=101", 422)
        commerce.call("GET", f"/{path}?offset=-1", 422)
