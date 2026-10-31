from typing import Annotated

from fastapi import APIRouter, Query

from app.api.commercial_dependencies import Current, Database, Operator, Paging, RequestClock, RecordId, FilterId
from app.models import Subscription, SubscriptionLine, SubscriptionStatus
from app.schemas import commercial as s
from app.services import subscriptions
from app.services.commercial_common import page

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("", response_model=s.Page[s.SubscriptionOut])
def list_subscriptions(
    actor: Current, db: Database, paging: Paging, customer_id: FilterId = None,
    plan_id: FilterId = None, product_id: FilterId = None, status: SubscriptionStatus | None = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
) -> dict:
    query = subscriptions.subscription_query(actor)
    for column, value in ((Subscription.customer_id, customer_id), (Subscription.plan_id, plan_id), (Subscription.status, status)):
        if value is not None:
            query = query.where(column == value)
    if product_id is not None:
        query = query.where(Subscription.lines.any(SubscriptionLine.product_id == product_id))
    if search:
        query = query.where(Subscription.number.contains(search, autoescape=True))
    return page(db, query.order_by(Subscription.id), s.SubscriptionOut, paging.limit, paging.offset)


@router.get("/{identifier}", response_model=s.SubscriptionOut)
def get_subscription(identifier: RecordId, actor: Current, db: Database) -> s.SubscriptionOut:
    return s.SubscriptionOut.model_validate(subscriptions.get_subscription(db, actor, identifier))


@router.post("", status_code=201, response_model=s.SubscriptionOut)
def create_subscription(body: s.SubscriptionCreate, actor: Operator, db: Database, clock: RequestClock):
    return subscriptions.create_subscription(db, body, actor, clock)


@router.post("/from-template", status_code=201, response_model=s.SubscriptionOut)
def from_template(body: s.FromTemplate, actor: Operator, db: Database, clock: RequestClock):
    return subscriptions.create_subscription(db, body, actor, clock, from_template=True)


@router.post("/{identifier}/quotation", response_model=s.SubscriptionOut)
def quotation(identifier: RecordId, body: s.QuotationAction, actor: Operator, db: Database, clock: RequestClock):
    return subscriptions.transition(db, identifier, "quotation", body, actor, clock)


@router.post("/{identifier}/confirm", response_model=s.SubscriptionOut)
def confirm(identifier: RecordId, body: s.Action, actor: Operator, db: Database, clock: RequestClock):
    return subscriptions.transition(db, identifier, "confirm", body, actor, clock)


@router.post("/{identifier}/activate", response_model=s.SubscriptionOut)
def activate(identifier: RecordId, body: s.Action, actor: Operator, db: Database, clock: RequestClock):
    return subscriptions.transition(db, identifier, "activate", body, actor, clock)


@router.post("/{identifier}/close", response_model=s.SubscriptionOut)
def close(identifier: RecordId, body: s.Action, actor: Operator, db: Database, clock: RequestClock):
    return subscriptions.transition(db, identifier, "close", body, actor, clock)


@router.post("/{identifier}/pause", response_model=s.SubscriptionOut)
def pause(identifier: RecordId, body: s.Action, actor: Operator, db: Database, clock: RequestClock):
    return subscriptions.transition(db, identifier, "pause", body, actor, clock)


@router.post("/{identifier}/resume", response_model=s.SubscriptionOut)
def resume(identifier: RecordId, body: s.Action, actor: Operator, db: Database, clock: RequestClock):
    return subscriptions.transition(db, identifier, "resume", body, actor, clock)


@router.post("/{identifier}/renew", response_model=s.SubscriptionOut)
def renew(identifier: RecordId, body: s.RenewAction, actor: Operator, db: Database, clock: RequestClock):
    return subscriptions.transition(db, identifier, "renew", body, actor, clock)
