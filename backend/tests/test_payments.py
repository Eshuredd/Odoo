from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
import pytest
from sqlalchemy import select, text
from alembic import command
from app.models import Invoice, Payment, User, UserRole
from app.core.principal import Principal
from app.core.errors import ServiceError
from app.db.session import create_db_engine, create_session_factory
from app.schemas.payments import PaymentCreate
from app.services import payments
from conftest import migration_config
from test_billing import run, dump


def confirmed(c):
    c.subscription("active")
    identifier=run(c,"2026-01-15",False)["invoices"][0]["invoice_id"]
    return c.call("POST",f"/invoices/{identifier}/confirm")


def body(amount=10000,key="synthetic-payment",**values):
    return {"amount_paise":amount,"method":"bank_transfer","payment_date":"2026-02-01","idempotency_key":key,**values}


def pay(c,id,amount=10000,key="synthetic-payment",expected=201,**values):
    return c.call("POST",f"/invoices/{id}/payments",expected,json=body(amount,key,**values))


def test_partial_full_retry_and_immutable_invoice(commerce):
    c=commerce; inv=confirmed(c); id=inv["id"]
    first=pay(c,id)
    assert pay(c,id)==first
    partial=c.call("GET",f"/invoices/{id}?as_of=2026-03-01")
    assert partial["paid_amount_paise"]==10000 and partial["remaining_balance_paise"]==inv["total_paise"]-10000
    assert partial["status"]=="confirmed" and partial["payment_progress"]=="partial" and partial["is_overdue"]
    c.call("POST",f"/invoices/{id}/cancel",409)
    pay(c,id,inv["total_paise"]-10000,"final")
    settled=c.call("GET",f"/invoices/{id}?as_of=2026-03-01")
    assert settled["status"]=="paid" and settled["remaining_balance_paise"]==0 and not settled["is_overdue"]
    assert settled["lines"]==inv["lines"] and settled["total_paise"]==inv["total_paise"]
    assert pay(c,id)==first  # retry is still valid after final settlement.
    assert c.call("GET",f"/invoices/{id}/payments?limit=1")["total"]==2
    pay(c,id,1,"extra",409)
    pay(c,id,2,"synthetic-payment",409)
    pay(c,id,10000,"synthetic-payment",409,note="different")
    assert run(c,"2026-01-15",False)["generated_or_proposed_invoice_count"]==0


@pytest.mark.parametrize("amount",[0,-1,1.5,True,9223372036854775808])
def test_invalid_amount(commerce,amount):
    inv=confirmed(commerce);pay(commerce,inv["id"],amount,expected=422)


def test_overpayment_draft_cancelled_and_zero_settlement(commerce):
    c=commerce;c.subscription("active");id=run(c,"2026-01-15",False)["invoices"][0]["invoice_id"]
    pay(c,id,expected=409)
    inv=c.call("POST",f"/invoices/{id}/confirm")
    pay(c,id,inv["total_paise"]+1,expected=409)
    c.call("POST",f"/invoices/{id}/settle-zero",409)
    c.call("POST",f"/invoices/{id}/cancel")
    pay(c,id,expected=409)
    c.call("PATCH",f"/plans/{c.plan['id']}",json={"price_paise":0})
    c.call("PATCH",f"/products/{c.product['id']}",json={"sales_price_paise":0})
    c.call("PATCH",f"/products/{c.product['id']}/variants/{c.variant['id']}",json={"extra_price_paise":0})
    c.subscription("active")
    zero=run(c,"2026-01-15",False)["invoices"][0]["invoice_id"]
    c.call("POST",f"/invoices/{zero}/confirm")
    assert c.call("POST",f"/invoices/{zero}/settle-zero")["status"]=="paid"
    assert c.call("GET",f"/invoices/{zero}/payments")["total"]==0


def test_ownership_and_role_restrictions(commerce,make_user,bearer_headers):
    c=commerce;inv=confirmed(c);payment=pay(c,inv["id"])
    with c.client.app.state.session_factory() as session:
        buyer=session.scalar(select(User).where(User.email=="buyer@example.com"))
    owner=bearer_headers(buyer);other=bearer_headers(make_user(UserRole.CUSTOMER,"outsider@example.com"))
    for url in (f"/payments/{payment['id']}",f"/invoices/{inv['id']}/payments"):
        c.call("GET",url,headers=owner);c.call("GET",url,404,headers=other)
    assert c.call("GET","/payments",headers=other)["total"]==0
    c.call("POST",f"/invoices/{inv['id']}/payments",403,headers=owner,json=body())
    c.call("POST",f"/invoices/{inv['id']}/payments",401,headers={},json=body())
    staff=bearer_headers(make_user(UserRole.STAFF))
    c.call("POST",f"/invoices/{inv['id']}/payments",201,headers=staff,json=body(1,"staff"))


def test_concurrent_payments_and_atomic_audit_failure(commerce,monkeypatch):
    c=commerce;inv=confirmed(c)
    before=dump(c)
    def fail(*args,**kwargs):raise RuntimeError("Injected audit failure")
    original=payments.record_event;monkeypatch.setattr(payments,"record_event",fail)
    with pytest.raises(RuntimeError):pay(c,inv["id"],inv["total_paise"])
    assert dump(c)==before
    monkeypatch.setattr(payments,"record_event",original)
    with c.client.app.state.session_factory() as session:
        actor=Principal.from_user(session.scalar(select(User).where(User.role==UserRole.ADMIN)))
    url=str(c.client.app.state.session_factory.kw["bind"].url);barrier=Barrier(2)
    def execute(i):
        engine=create_db_engine(url)
        try:
            barrier.wait(timeout=10)
            with create_session_factory(engine)() as session:
                try:payments.record_payment(session,inv["id"],PaymentCreate(**body(150000,str(i))),actor,c.client.app.state.clock);return 201
                except ServiceError as error:return error.status_code
        finally:engine.dispose()
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(execute,range(2)))
    assert sorted(results)==[201,409]
    assert c.call("GET",f"/invoices/{inv['id']}")["paid_amount_paise"]==150000


def test_payment_migration_and_database_guards(commerce):
    c=commerce;inv=confirmed(c);pay(c,inv["id"])
    engine=c.client.app.state.session_factory.kw["bind"]
    from sqlalchemy.exc import IntegrityError
    for sql in ("DELETE FROM payments","UPDATE payments SET amount_paise=1", "UPDATE invoices SET status='cancelled'", "UPDATE invoices SET status='paid'"):
        with pytest.raises(IntegrityError),engine.begin() as connection:connection.execute(text(sql))
    config=migration_config(str(engine.url));command.check(config)
