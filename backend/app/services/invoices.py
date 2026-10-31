from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import ServiceError
from app.core.principal import Principal
from app.models import CustomerProfile, Invoice, InvoiceStatus, UserRole
from app.schemas.financial import InvoiceOut
from app.services.audit import record_event
from app.services.commercial_common import write_scope


def invoice_query(actor: Principal):
    query = select(Invoice).where(Invoice.sealed.is_(True))
    if actor.role == UserRole.CUSTOMER:
        query = query.join(CustomerProfile).where(CustomerProfile.user_id == actor.id)
    return query


def get_invoice(session: Session, actor: Principal, identifier: int) -> Invoice:
    row = session.scalar(invoice_query(actor).where(Invoice.id == identifier))
    if row is None:
        raise ServiceError(404, "Invoice not found")
    return row


def transition(session: Session, identifier: int, action: str, actor: Principal, clock: Clock) -> InvoiceOut:
    with write_scope(session, actor, UserRole.ADMIN, UserRole.STAFF):
        row = get_invoice(session, actor, identifier)
        allowed = {InvoiceStatus.DRAFT} if action == "confirm" else {InvoiceStatus.DRAFT, InvoiceStatus.CONFIRMED}
        if row.status not in allowed:
            raise ServiceError(409, f"Cannot {action} an invoice in {row.status.value} state")
        if action == "cancel" and row.paid_amount_paise:
            raise ServiceError(409, "Cannot cancel an invoice with recorded payments")
        previous = row.status
        row.status = InvoiceStatus.CONFIRMED if action == "confirm" else InvoiceStatus.CANCELLED
        row.updated_at = clock()
        record_event(session, actor_id=actor.id, action="invoice." + action, entity="invoice", entity_id=row.id,
                     now=clock(), detail={"from": previous.value, "to": row.status.value})
        session.flush()
        return InvoiceOut.model_validate(row)
