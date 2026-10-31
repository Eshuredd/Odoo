from datetime import date
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.errors import ServiceError
from app.models import Payment, Invoice, InvoiceStatus, UserRole, CustomerProfile
from app.schemas.payments import PaymentCreate, PaymentOut
from app.schemas.financial import InvoiceOut
from app.services.invoices import get_invoice
from app.services.audit import record_event
from app.services.commercial_common import write_scope


def payment_query(actor):
    query = select(Payment).join(Invoice)
    if actor.role == UserRole.CUSTOMER:
        query = query.join(CustomerProfile).where(CustomerProfile.user_id == actor.id)
    return query


def invoice_output(row: Invoice, as_of: date | None = None) -> InvoiceOut:
    result = InvoiceOut.model_validate(row)
    if as_of is not None:
        overdue = row.status == InvoiceStatus.CONFIRMED and row.remaining_balance_paise > 0 and row.due_date < as_of
        result = result.model_copy(update={"is_overdue": overdue, "days_overdue": (as_of-row.due_date).days if overdue else 0})
    return result


def record_payment(session: Session, identifier: int, body: PaymentCreate, actor, clock) -> PaymentOut:
    with write_scope(session, actor, UserRole.ADMIN, UserRole.STAFF):
        invoice = get_invoice(session, actor, identifier)
        existing = session.scalar(select(Payment).where(Payment.idempotency_key == body.idempotency_key))
        if existing:
            matches = existing.invoice_id == identifier and all(getattr(existing, name) == value for name, value in body.model_dump().items())
            if not matches:
                raise ServiceError(409, "Idempotency key was already used with different payment data")
            return PaymentOut.model_validate(existing)
        if invoice.status != InvoiceStatus.CONFIRMED:
            raise ServiceError(409, "Only confirmed invoices can receive payments")
        if body.amount_paise > invoice.remaining_balance_paise:
            raise ServiceError(409, "Payment exceeds the outstanding balance")
        payment = Payment(invoice_id=identifier, created_at=clock(), **body.model_dump())
        session.add(payment)
        session.flush()
        session.expire(invoice, ["paid_amount_paise"])
        if invoice.remaining_balance_paise == 0:
            invoice.status = InvoiceStatus.PAID
        invoice.updated_at = clock()
        record_event(session, actor_id=actor.id, action="payment.recorded", entity="payment", entity_id=payment.id,
                     now=clock(), detail={"invoice_id": identifier, "amount_paise": payment.amount_paise, "invoice_status": invoice.status.value})
        session.flush()
        return PaymentOut.model_validate(payment)


def settle_zero(session, identifier, actor, clock):
    with write_scope(session, actor, UserRole.ADMIN, UserRole.STAFF):
        invoice = get_invoice(session, actor, identifier)
        if invoice.status != InvoiceStatus.CONFIRMED or invoice.total_paise != 0:
            raise ServiceError(409, "Explicit zero settlement requires a confirmed zero-total invoice")
        invoice.status, invoice.updated_at = InvoiceStatus.PAID, clock()
        record_event(session, actor_id=actor.id, action="invoice.zero_settled", entity="invoice", entity_id=invoice.id, now=clock())
        session.flush()
        return invoice_output(invoice)
