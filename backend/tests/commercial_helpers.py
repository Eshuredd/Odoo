from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import CustomerProfile
from conftest import TEST_PASSWORD

AS_OF = "2026-01-15"


class Commerce:
    """Build and exercise real API records in the fixture's temporary SQLite file."""

    def __init__(self, client: TestClient, headers: dict[str, str]) -> None:
        self.client = client
        self.headers = headers
        user = self.call("POST", "/auth/signup", 201, json={
            "email": "buyer@example.com", "password": TEST_PASSWORD,
            "company_name": "Synthetic Buyer", "contact_name": "Demo Buyer",
        })
        with client.app.state.session_factory() as session:
            self.customer_id = session.scalar(select(CustomerProfile.id).where(CustomerProfile.user_id == user["id"]))
        self.tax = self.call("POST", "/taxes", 201, json={"name": "GST", "rate_basis_points": 1800})
        self.product = self.call("POST", "/products", 201, json={
            "name": "Software", "product_type": "service", "sales_price_paise": 10000,
            "cost_price_paise": 3000, "tax_id": self.tax["id"],
        })
        self.variant = self.call("POST", f"/products/{self.product['id']}/variants", 201,
                                 json={"attribute": "Brand", "value": "Odoo", "extra_price_paise": 56000})
        self.plan = self.call("POST", "/plans", 201, json={
            "name": "Monthly", "price_paise": 50000, "billing_period": "monthly", "min_quantity": 2,
            "valid_from": "2026-01-01", "valid_to": "2026-12-31",
            "pausable": True, "closable": True, "renewable": True, "auto_close": False,
        })
        self.template = self.call("POST", "/quotation-templates", 201, json={
            "name": "Standard", "validity_days": 14, "plan_id": self.plan["id"], "lines": self.lines(),
        })

    def call(self, method: str, path: str, expected: int = 200, *, headers: dict | None = None, **kwargs: Any):
        response = self.client.request(method, "/api/v1" + path,
                                       headers=self.headers if headers is None else headers, **kwargs)
        assert response.status_code == expected, (response.status_code, response.text)
        return response.json() if response.content else None

    def lines(self) -> list[dict]:
        return [{"product_id": self.product["id"], "variant_id": self.variant["id"], "quantity": 2}]

    def draft_body(self, **overrides: Any) -> dict:
        return {"customer_id": self.customer_id, "plan_id": self.plan["id"], "start_date": AS_OF,
                "expiry_date": "2026-06-15", "payment_terms_days": 15, "as_of": AS_OF,
                "lines": self.lines(), **overrides}

    def subscription(self, state: str = "draft", **overrides: Any) -> dict:
        row = self.call("POST", "/subscriptions", 201, json=self.draft_body(**overrides))
        for action, target in (("quotation", "quotation"), ("confirm", "confirmed"), ("activate", "active")):
            if row["status"] == state:
                break
            row = self.action(row["id"], action)
        assert row["status"] == state
        return row

    def action(self, identifier: int, action: str, expected: int = 200, **overrides: Any):
        return self.call("POST", f"/subscriptions/{identifier}/{action}", expected,
                         json={"as_of": AS_OF, **overrides})
