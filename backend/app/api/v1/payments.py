from datetime import date
from fastapi import APIRouter
from sqlalchemy import select
from app.api.commercial_dependencies import Current, Operator, Database, Paging, RecordId, FilterId, RequestClock
from app.core.errors import ServiceError
from app.models import Payment
from app.schemas.commercial import Page
from app.schemas.payments import PaymentCreate, PaymentOut
from app.schemas.financial import InvoiceOut
from app.services import payments, invoices
from app.services.commercial_common import page

router = APIRouter(tags=["payments"])


@router.post("/invoices/{identifier}/payments", response_model=PaymentOut, status_code=201)
def create(identifier: RecordId, body: PaymentCreate, actor: Operator, db: Database, clock: RequestClock):
    return payments.record_payment(db, identifier, body, actor, clock)


@router.post("/invoices/{identifier}/settle-zero", response_model=InvoiceOut)
def settle(identifier: RecordId, actor: Operator, db: Database, clock: RequestClock):
    return payments.settle_zero(db, identifier, actor, clock)


@router.get("/invoices/{identifier}/payments", response_model=Page[PaymentOut])
def invoice_payments(identifier: RecordId, actor: Current, db: Database, paging: Paging):
    invoices.get_invoice(db, actor, identifier)
    return page(db, payments.payment_query(actor).where(Payment.invoice_id==identifier).order_by(Payment.id.desc()), PaymentOut, paging.limit, paging.offset)


@router.get("/payments", response_model=Page[PaymentOut])
def list_payments(actor: Current, db: Database, paging: Paging, invoice_id: FilterId = None,
                  from_date: date | None = None, to_date: date | None = None):
    if from_date and to_date and to_date < from_date:
        raise ServiceError(422,"to_date cannot precede from_date")
    query=payments.payment_query(actor).order_by(Payment.id.desc())
    if invoice_id is not None:
        query=query.where(Payment.invoice_id==invoice_id)
    if from_date:
        query=query.where(Payment.payment_date>=from_date)
    if to_date:
        query=query.where(Payment.payment_date<=to_date)
    return page(db,query,PaymentOut,paging.limit,paging.offset)


@router.get("/payments/{identifier}", response_model=PaymentOut)
def detail(identifier: RecordId, actor: Current, db: Database):
    row=db.scalar(payments.payment_query(actor).where(Payment.id==identifier))
    if row is None:
        raise ServiceError(404,"Payment not found")
    return PaymentOut.model_validate(row)
