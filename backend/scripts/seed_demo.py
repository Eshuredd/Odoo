"""Explicit small synthetic demo, always isolated from the ordinary DATABASE_URL."""
import os
import secrets
from datetime import timedelta, timezone
from sqlalchemy import inspect, select
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from app.core.config import BACKEND_DIR, Settings
from app.db.base import Base, utc_now
from app.db.session import create_db_engine, create_session_factory
from app.models import AuditLog
from app.main import create_app
from app.services.auth import seed_admin


def main():
    required=("ADMIN_EMAIL","ADMIN_PASSWORD","DEMO_STAFF_EMAIL","DEMO_STAFF_PASSWORD","DEMO_CUSTOMER_PASSWORD")
    if any(not os.environ.get(name) for name in required):
        raise SystemExit("Set ADMIN_EMAIL, ADMIN_PASSWORD, DEMO_STAFF_EMAIL, DEMO_STAFF_PASSWORD and DEMO_CUSTOMER_PASSWORD explicitly.")
    # Deliberately ignore normal DATABASE_URL. Use this same demo URL when launching the app.
    url=os.environ.get("DEMO_DATABASE_URL","sqlite:///data/synthetic_demo.db")
    engine=create_db_engine(url)
    try:
        tables=set(inspect(engine).get_table_names())
        with engine.connect() as connection:
            if "audit_logs" in tables and connection.scalar(select(AuditLog.id).where(AuditLog.action=="demo.seeded").limit(1)):
                print("Synthetic demo already seeded; existing accounts and records were left unchanged.")
                return
            if any(connection.scalar(select(table.c.id).limit(1)) is not None for table in Base.metadata.sorted_tables if table.name in tables):
                raise SystemExit("Refusing to seed a nonempty database without the synthetic demo marker. Choose a fresh DEMO_DATABASE_URL.")
    finally:
        engine.dispose()
    config=Config(str(BACKEND_DIR/"alembic.ini"));config.attributes["database_url"]=url;command.upgrade(config,"head")
    settings=Settings(_env_file=None,database_url=url,auth_secret_key=os.environ.get("AUTH_SECRET_KEY") or secrets.token_urlsafe(48),
        app_env="development",smtp_host="",smtp_username="",smtp_password="",smtp_from_email="")
    engine=create_db_engine(url)
    try:
        with create_session_factory(engine)() as session:
            seed_admin(session,email=os.environ["ADMIN_EMAIL"],password=os.environ["ADMIN_PASSWORD"],clock=utc_now)
    finally:engine.dispose()
    today=utc_now().astimezone(timezone(timedelta(hours=5,minutes=30))).date()
    with TestClient(create_app(settings)) as client:
        response=client.post("/api/v1/auth/login",json={"email":os.environ["ADMIN_EMAIL"],"password":os.environ["ADMIN_PASSWORD"]})
        if response.status_code!=200:raise SystemExit("Synthetic admin login failed; verify credentials/configuration.")
        headers={"Authorization":"Bearer "+response.json()["access_token"]}
        def post(path,body=None):
            result=client.post("/api/v1"+path,headers=headers,json=body)
            if not result.is_success:raise RuntimeError(f"Synthetic setup failed at {path} (HTTP {result.status_code}); use a fresh demo database after correcting inputs.")
            return result.json()
        post("/users/staff",{"email":os.environ["DEMO_STAFF_EMAIL"],"password":os.environ["DEMO_STAFF_PASSWORD"]})
        customers=[post("/customers",{"email":os.environ.get("DEMO_CUSTOMER_EMAIL","buyer@demo.example.com") if i==0 else f"synthetic{i+1}@demo.example.com",
            "password":os.environ["DEMO_CUSTOMER_PASSWORD"],"company_name":f"Synthetic Demo Company {i+1}","contact_name":f"Synthetic Buyer {i+1}"}) for i in range(3)]
        tax=post("/taxes",{"name":"Synthetic GST 18%","rate_basis_points":1800})
        product=post("/products",{"name":"Synthetic Business Software","product_type":"service","sales_price_paise":15000,"tax_id":tax["id"]})
        variant=post(f"/products/{product['id']}/variants",{"attribute":"Tier","value":"Synthetic Pro","extra_price_paise":5000})
        plans={cadence:post("/plans",{"name":f"Synthetic {cadence.title()}","price_paise":50000,"billing_period":cadence,
            "valid_from":str(today-timedelta(days=800)),"valid_to":str(today+timedelta(days=1500)),"pausable":True,"closable":True,"renewable":True}) for cadence in ("daily","weekly","monthly","yearly")}
        lines=[{"product_id":product["id"],"variant_id":variant["id"],"quantity":2}]
        post("/quotation-templates",{"name":"Synthetic Standard Quote","plan_id":plans["monthly"]["id"],"validity_days":30,"lines":lines})
        post("/discounts",{"name":"Synthetic Launch 10%","discount_type":"percentage","scope":"subscription","rate_basis_points":1000,
            "valid_from":str(today-timedelta(days=800)),"valid_to":str(today+timedelta(days=365)),"usage_limit":4})
        def subscription(state,cadence="monthly",age=60,index=0,paused=False):
            row=post("/subscriptions",{"customer_id":customers[index]["id"],"plan_id":plans[cadence]["id"],"start_date":str(today-timedelta(days=age)),
                "expiry_date":str(today+timedelta(days=300)),"payment_terms_days":7,"as_of":str(today),"lines":lines})
            for action,target in (("quotation","quotation"),("confirm","confirmed"),("activate","active"),("close","closed")):
                if row["status"]==state:break
                row=post(f"/subscriptions/{row['id']}/{action}",{"as_of":str(today)})
            if paused:post(f"/subscriptions/{row['id']}/pause",{"as_of":str(today)})
            return row
        for state in ("draft","quotation","confirmed","active","closed"):subscription(state)
        subscription("active","daily",2,1);subscription("active","weekly",14,2);subscription("active","yearly",0,1)
        subscription("active",paused=True,index=2)
        report=post("/billing/run",{"as_of":str(today)})
        if report["failed_count"]:raise RuntimeError("Synthetic billing failed; no fabricated invoices were inserted")
        for index,item in enumerate(report["invoices"]):
            identifier=item["invoice_id"]
            if index==len(report["invoices"])-1:continue # leave one Draft for confirmation during the demo.
            invoice=post(f"/invoices/{identifier}/confirm")
            if index<2:
                post(f"/invoices/{identifier}/payments",{"amount_paise":invoice["total_paise"] if index==0 else invoice["total_paise"]//2,
                    "method":"bank_transfer","payment_date":str(today),"reference":"SYNTHETIC DEMO","idempotency_key":f"synthetic-demo-payment-{identifier}"})
        with client.app.state.session_factory() as session,session.begin():
            session.add(AuditLog(actor_id=None,action="demo.seeded",entity="demo",entity_id="1",timestamp=utc_now(),detail={"synthetic":True,"as_of":str(today)}))
        print(f"Synthetic demo ready: 3 customers, 4 cadences, 9 subscriptions, {len(report['invoices'])} calculated invoices, partial/full payments and overdue balances.")
        print("Launch the backend with DATABASE_URL matching DEMO_DATABASE_URL. No ordinary application database or existing account was overwritten.")


if __name__=="__main__":main()
