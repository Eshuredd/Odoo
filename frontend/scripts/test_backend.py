"""Isolated real FastAPI backend with synthetic data for browser tests. Never uses app data/."""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import uvicorn
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.engine import URL

from app.core.config import Settings
from app.main import create_app
from app.db.session import create_db_engine, create_session_factory
from app.db.base import utc_now
from app.services.auth import seed_admin


def main() -> None:
    password = os.environ["SUBCADENCE_TEST_PASSWORD"]
    with TemporaryDirectory(prefix="subcadence-browser-") as directory:
        database = (Path(directory) / "test.db").resolve()
        assert database.is_relative_to(Path(directory).resolve())
        database_url = URL.create("sqlite", database=str(database)).render_as_string()
        settings = Settings(_env_file=None, database_url=database_url,
            auth_secret_key=os.environ["AUTH_SECRET_KEY"], app_env="development",
            smtp_host="", smtp_username="", smtp_password="", smtp_from_email="",
            cors_origins=["http://localhost:3000", "http://127.0.0.1:3000"])
        config = Config(str(ROOT / "backend" / "alembic.ini"))
        config.attributes["database_url"] = database_url
        command.upgrade(config, "head")
        engine = create_db_engine(database_url)
        try:
            with create_session_factory(engine)() as session:
                seed_admin(session, email="admin@example.com", password=password, clock=utc_now)
        finally:
            engine.dispose()
        app = create_app(settings)
        today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
        as_of = today.isoformat()
        with TestClient(app) as client:
            login = client.post("/api/v1/auth/login", json={"email":"admin@example.com","password":password})
            assert login.status_code == 200
            headers = {"Authorization":"Bearer " + login.json()["access_token"]}
            def post(path: str, body: dict, expected: int = 201) -> dict:
                response = client.post("/api/v1" + path, json=body, headers=headers)
                assert response.status_code == expected, (path, response.status_code)
                return response.json()
            post("/users/staff", {"email":"staff@example.com","password":password})
            customers = [post("/customers", {"email":email,"password":password,"company_name":company,"contact_name":name}) for email,company,name in [
                ("buyer@example.com","Alpha Industries","Synthetic Buyer"),
                ("other@example.com","Other Company","Other Buyer"),
            ]]
            tax = post("/taxes", {"name":"GST 18%","rate_basis_points":1800})
            product = post("/products", {"name":"Business Software","product_type":"service","sales_price_paise":10000,"tax_id":tax["id"]})
            variant = post(f"/products/{product['id']}/variants", {"attribute":"Brand","value":"Odoo","extra_price_paise":56000})
            plan = post("/plans", {"name":"Monthly Business","price_paise":50000,"billing_period":"monthly","min_quantity":2,
                "valid_from":"2020-01-01","valid_to":"2099-12-31","pausable":True,"closable":True,"renewable":True})
            post("/discounts", {"name":"Synthetic launch discount","discount_type":"percentage","scope":"subscription",
                "rate_basis_points":1000,"valid_from":"2020-01-01","valid_to":"2099-12-31","usage_limit":2})
            for index in range(24):
                row = post("/subscriptions", {"customer_id":customers[1 if index == 23 else 0]["id"],"plan_id":plan["id"],
                    "start_date":as_of,"expiry_date":(today + timedelta(days=90)).isoformat(),"payment_terms_days":15,"as_of":as_of,
                    "lines":[{"product_id":product["id"],"variant_id":variant["id"],"quantity":2}]})
                if index == 0:
                    for action in ("quotation","confirm","activate"):
                        post(f"/subscriptions/{row['id']}/{action}", {"as_of":as_of}, 200)
        uvicorn.run(app, host="127.0.0.1", port=8766, log_level="warning", access_log=False)


if __name__ == "__main__":
    main()
