from typing import Annotated

from fastapi import APIRouter, Query

from app.api.commercial_dependencies import Current, Database, Operator, Paging, RequestClock, RecordId, FilterId
from app.models import CustomerProfile
from app.schemas.commercial import CustomerCreate, CustomerOut, CustomerPatch, Page
from app.services import customers
from app.services.commercial_common import page

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=Page[CustomerOut])
def list_customers(
    actor: Current, db: Database, paging: Paging, search: Annotated[str | None, Query(max_length=200)] = None,
) -> dict:
    query = customers.customer_query(actor)
    if search:
        query = query.where(CustomerProfile.company_name.contains(search, autoescape=True)
                            | CustomerProfile.contact_name.contains(search, autoescape=True))
    return page(db, query.order_by(CustomerProfile.id), CustomerOut, paging.limit, paging.offset)


@router.get("/me", response_model=CustomerOut)
def own_profile(actor: Current, db: Database) -> CustomerOut:
    return CustomerOut.model_validate(customers.get_customer(db, actor))


@router.get("/{identifier}", response_model=CustomerOut)
def get_customer(identifier: RecordId, actor: Current, db: Database) -> CustomerOut:
    return CustomerOut.model_validate(customers.get_customer(db, actor, identifier))


@router.post("", status_code=201, response_model=CustomerOut)
def create_customer(body: CustomerCreate, actor: Operator, db: Database, clock: RequestClock) -> CustomerOut:
    return customers.create_customer(db, body, actor, clock)


@router.patch("/{identifier}", response_model=CustomerOut)
def update_customer(identifier: RecordId, body: CustomerPatch, actor: Current, db: Database, clock: RequestClock) -> CustomerOut:
    return customers.update_customer(db, identifier, body, actor, clock)
