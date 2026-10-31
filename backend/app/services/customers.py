from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import ServiceError
from app.core.principal import Principal
from app.models import CustomerProfile, UserRole
from app.schemas.commercial import CustomerCreate, CustomerOut, CustomerPatch
from app.services.audit import record_event
from app.services.auth import create_account
from app.services.commercial_common import apply_fields, write_scope


def customer_query(actor: Principal):
    query = select(CustomerProfile)
    if actor.role == UserRole.CUSTOMER:
        query = query.where(CustomerProfile.user_id == actor.id)
    return query


def get_customer(session: Session, actor: Principal, identifier: int | None = None) -> CustomerProfile:
    query = customer_query(actor)
    query = query.where(CustomerProfile.id == identifier) if identifier is not None else query.where(CustomerProfile.user_id == actor.id)
    row = session.scalar(query)
    if row is None:
        raise ServiceError(404, "Customer not found")
    return row


def create_customer(session: Session, body: CustomerCreate, actor: Principal, clock: Clock) -> CustomerOut:
    user = create_account(
        session, email=body.email, password=body.password.get_secret_value(), role=UserRole.CUSTOMER,
        clock=clock, actor=actor, profile=body.model_dump(exclude={"email", "password"}),
    )
    profile = session.scalar(select(CustomerProfile).where(CustomerProfile.user_id == user.id))
    return CustomerOut.model_validate(profile)


def update_customer(session: Session, identifier: int, body: CustomerPatch, actor: Principal, clock: Clock) -> CustomerOut:
    with write_scope(session, actor, UserRole.ADMIN, UserRole.STAFF, UserRole.CUSTOMER):
        row = get_customer(session, actor, identifier)
        if actor.role == UserRole.CUSTOMER and "notes" in body.model_fields_set:
            raise ServiceError(403, "Only staff or admin can edit operational notes")
        apply_fields(row, body.model_dump(exclude_unset=True))
        row.updated_at = clock()
        record_event(session, actor_id=actor.id, action="customer.updated", entity="customer",
                     entity_id=row.id, now=clock())
        session.flush()
        return CustomerOut.model_validate(row)
