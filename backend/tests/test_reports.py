from sqlalchemy import select
from app.models import User, UserRole
from test_billing import run
from test_payments import pay


def test_reports_reconcile_balances_aging_dates_and_roles(commerce,make_user,bearer_headers):
    c=commerce
    sub=c.subscription("active",payment_terms_days=0)
    c.action(sub["id"],"pause")
    assert run(c,"2026-03-15",False)["generated_or_proposed_invoice_count"]==0
    c.action(sub["id"],"resume")
    invoices=run(c,"2026-03-15",False)["invoices"]
    for invoice in invoices:c.call("POST",f"/invoices/{invoice['invoice_id']}/confirm")
    c.action(sub["id"],"pause")
    pay(c,invoices[0]["invoice_id"],10000,"jan",payment_date="2026-01-20")
    pay(c,invoices[1]["invoice_id"],20000,"feb",payment_date="2026-02-20")
    total=invoices[0]["total_paise"]
    report=c.call("GET","/reports/summary?as_of=2026-03-18&from_date=2026-01-01&to_date=2026-03-31")
    assert report["revenue_collected_paise"]==30000
    assert report["outstanding_balance_paise"]==3*total-30000
    assert report["overdue_amount_paise"]==report["outstanding_balance_paise"] and report["overdue_invoice_count"]==3
    assert [b["invoice_count"] for b in report["aging_buckets"].values()]==[1,1,1]
    assert report["active_subscription_count"]==1 and report["paused_subscription_count"]==1
    assert report["monthly_collections"]==[{"month":"2026-01","amount_paise":10000},{"month":"2026-02","amount_paise":20000}]
    assert c.call("GET","/reports/summary?as_of=2026-03-15")["overdue_invoice_count"]==2
    assert c.call("GET","/reports/summary?as_of=2026-01-15")["overdue_invoice_count"]==0
    for invoice in invoices:
        detail=c.call("GET",f"/invoices/{invoice['invoice_id']}?as_of=2026-03-18")
        assert detail["is_overdue"] and detail["days_overdue"]>0
    assert c.call("GET","/invoices?as_of=2026-03-18&overdue=true")["total"]==3
    c.call("GET","/invoices?overdue=true",422)
    pay(c,invoices[0]["invoice_id"],total-10000,"settle",payment_date="2026-03-01")
    assert c.call("GET","/reports/summary?as_of=2026-03-18")["overdue_invoice_count"]==2
    c.call("POST",f"/invoices/{invoices[2]['invoice_id']}/cancel")
    report=c.call("GET","/reports/summary?as_of=2026-03-18&from_date=2026-02-20&to_date=2026-02-20")
    assert report["revenue_collected_paise"]==20000 and report["outstanding_balance_paise"]==total-20000
    assert report["invoice_count_by_status"]=={"draft":0,"confirmed":1,"paid":1,"cancelled":1}
    c.call("GET","/reports/summary?as_of=2026-03-18&from_date=2026-04-01",422)
    with c.client.app.state.session_factory() as session:buyer=session.scalar(select(User).where(User.email=="buyer@example.com"))
    c.call("GET","/reports/summary?as_of=2026-03-18",403,headers=bearer_headers(buyer))
    c.call("GET","/reports/summary?as_of=2026-03-18",401,headers={})
    c.call("GET","/reports/summary?as_of=2026-03-18",headers=bearer_headers(make_user(UserRole.STAFF)))
