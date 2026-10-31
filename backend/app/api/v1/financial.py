from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from app.api.commercial_dependencies import Admin, Current, Database, FilterId, Operator, Paging, RecordId, RequestClock
from app.core.errors import ServiceError
from app.models import Discount, Invoice, InvoiceStatus, Product, UserRole
from app.schemas import financial as s
from app.schemas.commercial import Page
from app.services import billing, invoices
from app.services.payments import invoice_output
from app.models import CustomerProfile, User
from app.services.mailer import MailMessage, MailDeliveryError, DatabaseOutboxMailer
from app.services.audit import record_event
from app.services.catalog import reference
from app.services.commercial_common import apply_fields, get_record, page, validated_patch, write_scope

router = APIRouter(tags=["billing and invoices"])


@router.post("/billing/preview", response_model=s.BillingReport)
def preview(body: s.BillingRequest, actor: Operator, request: Request, clock: RequestClock):
    return billing.run_billing(request.app.state.session_factory, body.as_of, True, actor, clock)


@router.post("/billing/run", response_model=s.BillingReport)
def run(body: s.BillingRequest, actor: Operator, request: Request, clock: RequestClock):
    return billing.run_billing(request.app.state.session_factory, body.as_of, False, actor, clock)


@router.get("/discounts", response_model=Page[s.DiscountOut])
def list_discounts(actor: Operator, db: Database, paging: Paging, active: bool | None = None,
                   as_of: date | None = None, search: Annotated[str | None, Query(max_length=200)] = None):
    query = select(Discount).order_by(Discount.id)
    if active is not None:
        query = query.where(Discount.active == active)
    if as_of is not None:
        query = query.where(Discount.valid_from <= as_of, Discount.valid_to >= as_of)
    if search:
        query = query.where(Discount.name.contains(search, autoescape=True))
    return page(db, query, s.DiscountOut, paging.limit, paging.offset)


@router.get("/discounts/{identifier}", response_model=s.DiscountOut)
def get_discount(identifier: RecordId, actor: Operator, db: Database):
    return s.DiscountOut.model_validate(get_record(db, Discount, identifier))


def save_discount(body, actor, db, clock, identifier=None):
    with write_scope(db, actor, UserRole.ADMIN):
        row = get_record(db, Discount, identifier) if identifier else Discount(times_used=0, created_at=clock())
        values = validated_patch(row, body, s.DiscountCreate) if identifier else body.model_dump()
        if values["product_id"] is not None:
            reference(db, Product, values["product_id"], "Product")
        if values["usage_limit"] is not None and values["usage_limit"] < row.times_used:
            raise ServiceError(422, "usage_limit cannot be lower than times_used")
        apply_fields(row, values)
        row.updated_at = clock()
        db.add(row)
        db.flush()
        record_event(db, actor_id=actor.id, action="discount.updated" if identifier else "discount.created",
                     entity="discount", entity_id=row.id, now=clock())
        return s.DiscountOut.model_validate(row)


@router.post("/discounts", status_code=201, response_model=s.DiscountOut)
def create_discount(body: s.DiscountCreate, actor: Admin, db: Database, clock: RequestClock):
    return save_discount(body, actor, db, clock)


@router.patch("/discounts/{identifier}", response_model=s.DiscountOut)
def patch_discount(identifier: RecordId, body: s.DiscountPatch, actor: Admin, db: Database, clock: RequestClock):
    return save_discount(body, actor, db, clock, identifier)


@router.get("/invoices", response_model=Page[s.InvoiceOut])
def list_invoices(actor: Current, db: Database, paging: Paging, status: InvoiceStatus | None = None,
                  customer_id: FilterId = None, subscription_id: FilterId = None,
                  due_from: date | None = None, due_to: date | None = None, as_of: date | None = None, overdue: bool | None = None,
                  search: Annotated[str | None, Query(max_length=200)] = None):
    if actor.role == UserRole.CUSTOMER and customer_id is not None:
        raise ServiceError(403, "Customer filters are for operators only")
    if due_from and due_to and due_to < due_from:
        raise ServiceError(422, "due_to cannot precede due_from")
    query = invoices.invoice_query(actor).order_by(Invoice.id.desc())
    for column, value in ((Invoice.status, status), (Invoice.customer_id, customer_id), (Invoice.subscription_id, subscription_id)):
        if value is not None:
            query = query.where(column == value)
    if due_from:
        query = query.where(Invoice.due_date >= due_from)
    if due_to:
        query = query.where(Invoice.due_date <= due_to)
    if search:
        query = query.where(Invoice.number.contains(search, autoescape=True))
    if overdue is not None:
        if as_of is None:
            raise ServiceError(422,"Overdue filtering requires explicit as_of")
        condition=(Invoice.status==InvoiceStatus.CONFIRMED) & (Invoice.total_paise>Invoice.paid_amount_paise) & (Invoice.due_date<as_of)
        query=query.where(condition if overdue else ~condition)
    result=page(db, query, s.InvoiceOut, paging.limit, paging.offset)
    if as_of is not None:
        for item in result["items"]:
            item.is_overdue=item.status==InvoiceStatus.CONFIRMED and item.remaining_balance_paise>0 and item.due_date<as_of
            item.days_overdue=(as_of-item.due_date).days if item.is_overdue else 0
    return result


@router.get("/invoices/{identifier}", response_model=s.InvoiceOut)
def get_invoice(identifier: RecordId, actor: Current, db: Database, as_of: date | None = None):
    return invoice_output(invoices.get_invoice(db, actor, identifier), as_of)


@router.post("/invoices/{identifier}/confirm", response_model=s.InvoiceOut)
def confirm_invoice(identifier: RecordId, actor: Operator, db: Database, clock: RequestClock):
    return invoices.transition(db, identifier, "confirm", actor, clock)


@router.post("/invoices/{identifier}/cancel", response_model=s.InvoiceOut)
def cancel_invoice(identifier: RecordId, actor: Operator, db: Database, clock: RequestClock):
    return invoices.transition(db, identifier, "cancel", actor, clock)


@router.post("/invoices/{identifier}/send")
def send_invoice(identifier:RecordId,actor:Operator,db:Database,clock:RequestClock,request:Request):
    try:
        with write_scope(db,actor,UserRole.ADMIN,UserRole.STAFF):
            invoice=invoices.get_invoice(db,actor,identifier)
            if invoice.status not in {InvoiceStatus.CONFIRMED,InvoiceStatus.PAID}:
                raise ServiceError(409,"Only confirmed or paid invoices can be sent")
            recipient=db.scalar(select(User.email).join(CustomerProfile,CustomerProfile.user_id==User.id).where(CustomerProfile.id==invoice.customer_id))
            total=f"INR {invoice.total_paise//100}.{invoice.total_paise%100:02d}"
            body=f"SubCadence invoice {invoice.number}\nPeriod: [{invoice.period_start}, {invoice.period_end})\nInvoice date: {invoice.invoice_date}\nDue date: {invoice.due_date}\nTotal: {total}\nThis is an invoice notice, not a payment gateway request."
            request.app.state.mailer.send(MailMessage(recipient_email=recipient,subject=f"SubCadence invoice {invoice.number}",body=body),session=db,now=clock())
            record_event(db,actor_id=actor.id,action="invoice.send_requested",entity="invoice",entity_id=invoice.id,now=clock())
            db.flush()
        offline=isinstance(request.app.state.mailer,DatabaseOutboxMailer)
        return {"message":"Invoice notice saved to the offline email outbox." if offline else "Invoice notice accepted by SMTP.","delivery":"offline_outbox" if offline else "smtp_accepted"}
    except MailDeliveryError:
        raise ServiceError(503,"Invoice notice could not be sent; no success was recorded") from None
