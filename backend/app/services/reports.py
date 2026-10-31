from datetime import date
from sqlalchemy import case, func, select
from sqlalchemy.exc import OperationalError
from app.core.errors import ServiceError
from app.models import Invoice, Payment, Subscription, SubscriptionStatus


def summary(session, as_of: date, from_date: date | None, to_date: date | None):
    start, end = from_date or as_of.replace(day=1), to_date or as_of
    if end < start:
        raise ServiceError(422,"to_date cannot precede from_date")
    paid=select(Payment.invoice_id,func.sum(Payment.amount_paise).label("paid")).group_by(Payment.invoice_id).subquery()
    balances=select(Invoice.id,Invoice.status,Invoice.due_date,
        (Invoice.total_paise-func.coalesce(paid.c.paid,0)).label("balance")).outerjoin(paid,paid.c.invoice_id==Invoice.id).where(Invoice.sealed.is_(True)).subquery()
    collectible=(balances.c.status=="confirmed") & (balances.c.balance>0)
    overdue=collectible & (balances.c.due_date<as_of)
    days=func.julianday(as_of)-func.julianday(balances.c.due_date)
    def amount(condition):return func.coalesce(func.sum(case((condition,balances.c.balance),else_=0)),0)
    def count(condition):return func.coalesce(func.sum(case((condition,1),else_=0)),0)
    try:
        totals=session.execute(select(amount(collectible),count(overdue),amount(overdue),
            *[expression for low,high in ((1,30),(31,60),(61,4000000)) for expression in
              (count(overdue & (days>=low) & (days<=high)),amount(overdue & (days>=low) & (days<=high)))])).one()
        revenue=session.scalar(select(func.coalesce(func.sum(Payment.amount_paise),0)).where(Payment.payment_date>=start,Payment.payment_date<=end))
        month=func.strftime("%Y-%m",Payment.payment_date)
        monthly=session.execute(select(month,func.sum(Payment.amount_paise)).where(Payment.payment_date>=start,Payment.payment_date<=end).group_by(month).order_by(month)).all()
    except OperationalError:
        raise ServiceError(422,"Report totals exceed the supported SQL integer range") from None
    active=session.scalar(select(func.count()).select_from(Subscription).where(Subscription.status==SubscriptionStatus.ACTIVE))
    paused=session.scalar(select(func.count()).select_from(Subscription).where(Subscription.status==SubscriptionStatus.ACTIVE,Subscription.is_paused.is_(True)))
    counts=dict(session.execute(select(Invoice.status,func.count()).where(Invoice.sealed.is_(True)).group_by(Invoice.status)).all())
    return {"as_of":as_of,"from_date":start,"to_date":end,"active_subscription_count":active,"paused_subscription_count":paused,
        "revenue_collected_paise":revenue,"outstanding_balance_paise":totals[0],"overdue_invoice_count":totals[1],"overdue_amount_paise":totals[2],
        "aging_buckets":{label:{"invoice_count":totals[3+2*i],"amount_paise":totals[4+2*i]} for i,label in enumerate(("1_30","31_60","61_plus"))},
        "invoice_count_by_status":{status:counts.get(status,0) for status in ("draft","confirmed","paid","cancelled")},
        "monthly_collections":[{"month":month,"amount_paise":amount} for month,amount in monthly]}
