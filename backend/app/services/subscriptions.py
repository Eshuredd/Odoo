from datetime import date, timedelta
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import ServiceError
from app.core.principal import Principal
from app.models import CustomerProfile, Plan, QuotationTemplate, QuotationTemplateLine, Subscription, SubscriptionLine, SubscriptionStatus, User, UserRole
from app.models.commercial_common import MAX_INTEGER
from app.schemas import commercial as schemas
from app.services.audit import record_event
from app.services.catalog import reference, selected_product
from app.services.commercial_common import get_record, write_scope


def subscription_query(actor: Principal):
    query = select(Subscription)
    if actor.role == UserRole.CUSTOMER:
        query = query.join(CustomerProfile).where(CustomerProfile.user_id == actor.id)
    return query


def get_subscription(session: Session, actor: Principal, identifier: int) -> Subscription:
    row = session.scalar(subscription_query(actor).where(Subscription.id == identifier))
    if row is None:
        raise ServiceError(404, "Subscription not found")
    return row


def available_plan(session: Session, plan_id: int, as_of: date) -> Plan:
    plan = reference(session, Plan, plan_id, "Plan")
    if not plan.active or not plan.valid_from <= as_of <= plan.valid_to:
        raise ServiceError(422, "Plan is unavailable for new sales on as_of")
    return plan


def priced_lines(session: Session, lines: Sequence[schemas.LineInput | SubscriptionLine | QuotationTemplateLine], minimum: int) -> tuple[list[dict], list[dict]]:
    if sum(line.quantity for line in lines) < minimum:
        raise ServiceError(422, "Total product quantity does not meet the plan minimum")
    values, descriptions = [], []
    for line in lines:
        product, variant, tax = selected_product(session, line.product_id, line.variant_id)
        unit = product.sales_price_paise + (variant.extra_price_paise if variant else 0)
        amount = unit * line.quantity
        if unit > MAX_INTEGER or amount > MAX_INTEGER:
            raise ServiceError(422, "Line price or amount exceeds the supported integer range")
        values.append({"product_id": product.id, "variant_id": variant.id if variant else None,
                       "quantity": line.quantity, "unit_price_paise": unit,
                       "tax_rate_basis_points": tax.rate_basis_points if tax else 0, "amount_paise": amount})
        descriptions.append({"product_id": product.id, "product_name": product.name,
                             "variant_id": variant.id if variant else None,
                             "attribute": variant.attribute if variant else None, "value": variant.value if variant else None,
                             "tax_id": tax.id if tax else None, "tax_name": tax.name if tax else None})
    return values, descriptions


def audit_change(session: Session, row: Subscription, actor: Principal, clock: Clock, action: str, detail: dict) -> None:
    record_event(session, actor_id=actor.id, action="subscription." + action, entity="subscription",
                 entity_id=row.id, now=clock(), detail=detail)


def create_subscription(
    session: Session, body: schemas.SubscriptionCreate | schemas.FromTemplate,
    actor: Principal, clock: Clock, *, from_template: bool = False,
) -> schemas.SubscriptionOut:
    with write_scope(session, actor, UserRole.ADMIN, UserRole.STAFF):
        customer = reference(session, CustomerProfile, body.customer_id, "Customer")
        user = reference(session, User, customer.user_id, "Customer account")
        if user.role != UserRole.CUSTOMER or not user.is_active:
            raise ServiceError(422, "Customer must have an active customer account")
        template = get_record(session, QuotationTemplate, body.template_id) if from_template else None
        if template is not None and not template.active:
            raise ServiceError(422, "Quotation template is inactive")
        plan = available_plan(session, template.plan_id if template else body.plan_id, body.as_of)
        source_lines = template.lines if template else body.lines
        values, _ = priced_lines(session, source_lines, plan.min_quantity)
        if body.as_of > body.expiry_date:
            raise ServiceError(422, "Subscription has already expired on as_of")
        now = clock()
        row = Subscription(
            customer_id=customer.id, plan_id=plan.id, status=SubscriptionStatus.DRAFT,
            start_date=body.start_date, expiry_date=body.expiry_date, payment_terms_days=body.payment_terms_days,
            recurring_base_price_paise=plan.price_paise, created_at=now, updated_at=now,
            lines=[SubscriptionLine(**line) for line in values],
        )
        session.add(row)
        session.flush()
        audit_change(session, row, actor, clock, "created", {"status": "draft", "as_of": body.as_of.isoformat()})
        if template is not None:
            row.status = SubscriptionStatus.QUOTATION
            row.quotation_date = body.as_of
            row.quotation_expiry_date = quotation_expiry(body.as_of, template.validity_days)
            audit_change(session, row, actor, clock, "quotation", {"from": "draft", "to": "quotation", "as_of": body.as_of.isoformat()})
        session.flush()
        return schemas.SubscriptionOut.model_validate(row)


def quotation_expiry(as_of: date, validity_days: int) -> date:
    try:
        return as_of + timedelta(days=validity_days)
    except OverflowError:
        raise ServiceError(422, "Quotation expiry exceeds the supported date range") from None


def transition(
    session: Session, identifier: int, action: str,
    body: schemas.Action | schemas.QuotationAction | schemas.RenewAction, actor: Principal, clock: Clock,
) -> schemas.SubscriptionOut:
    with write_scope(session, actor, UserRole.ADMIN, UserRole.STAFF):
        row = get_subscription(session, actor, identifier)
        old_status = row.status
        required = {"quotation": "draft", "confirm": "quotation", "activate": "confirmed",
                    "close": "active", "pause": "active", "resume": "active", "renew": "active"}
        if row.status.value != required[action]:
            raise ServiceError(409, f"Cannot {action} a subscription in {row.status.value} state")
        terms = row.commercial_snapshot["plan"] if row.commercial_snapshot else {}
        detail = {"as_of": body.as_of.isoformat()}
        if action in {"quotation", "confirm"}:
            if body.as_of > row.expiry_date:
                raise ServiceError(409, "Subscription has expired")
            plan = available_plan(session, row.plan_id, body.as_of)
            values, descriptions = priced_lines(session, row.lines, plan.min_quantity)
            if action == "quotation":
                row.quotation_date = body.as_of
                row.quotation_expiry_date = quotation_expiry(body.as_of, body.validity_days)
                row.status = SubscriptionStatus.QUOTATION
            else:
                if not row.quotation_date <= body.as_of <= row.quotation_expiry_date:
                    raise ServiceError(409, "Quotation is not valid on as_of")
                for line, values_for_line in zip(row.lines, values):
                    for key, value in values_for_line.items():
                        setattr(line, key, value)
                # Persist final line values while the parent is still a quotation.
                session.flush()
                row.recurring_base_price_paise = plan.price_paise
                row.billing_period = plan.billing_period
                row.commercial_snapshot = {
                    "plan": {"id": plan.id, "name": plan.name, "billing_period": plan.billing_period.value,
                             "min_quantity": plan.min_quantity, "auto_close": plan.auto_close, "closable": plan.closable,
                             "pausable": plan.pausable, "renewable": plan.renewable},
                    "lines": descriptions, "start_date": row.start_date.isoformat(),
                    "original_expiry_date": row.expiry_date.isoformat(), "payment_terms_days": row.payment_terms_days,
                }
                row.status = SubscriptionStatus.CONFIRMED
        elif action == "activate":
            if not row.start_date <= body.as_of <= row.expiry_date:
                raise ServiceError(409, "Activation requires as_of within the subscription dates")
            row.next_invoice_date = row.start_date
            row.status = SubscriptionStatus.ACTIVE
        elif action == "close":
            if not terms["closable"]:
                raise ServiceError(409, "Accepted plan terms do not permit closure")
            row.status, row.is_paused, row.next_invoice_date = SubscriptionStatus.CLOSED, False, None
        elif action == "pause":
            if row.is_paused or not terms["pausable"]:
                raise ServiceError(409, "Subscription is already paused or pausing is not permitted")
            row.is_paused = True
        elif action == "resume":
            if not row.is_paused:
                raise ServiceError(409, "Subscription is not paused")
            row.is_paused = False
        elif action == "renew":
            if not terms["renewable"] or body.new_expiry_date <= max(row.expiry_date, body.as_of):
                raise ServiceError(409, "Renewal requires permitted terms and a later expiry than current expiry and as_of")
            detail["previous_expiry_date"] = row.expiry_date.isoformat()
            detail["new_expiry_date"] = body.new_expiry_date.isoformat()
            row.expiry_date = body.new_expiry_date
        row.updated_at = clock()
        detail.update({"from": old_status.value, "to": row.status.value})
        audit_change(session, row, actor, clock, action, detail)
        session.flush()
        return schemas.SubscriptionOut.model_validate(row)
