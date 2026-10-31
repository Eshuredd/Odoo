from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_auth_settings, get_clock, get_current_principal, get_mailer
from app.core.clock import Clock
from app.core.config import Settings
from app.core.principal import Principal
from app.db.session import get_db
from app.models import UserRole
from app.schemas.auth import AccountCreate, Credentials, LoginResponse, MessageResponse, PublicUser, ResetConfirm, ResetRequest
from app.services import auth
from app.services.mailer import Mailer
from app.schemas.signup import SignupRequest

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(get_auth_settings)])
Database = Annotated[Session, Depends(get_db)]
RequestClock = Annotated[Clock, Depends(get_clock)]
AuthSettings = Annotated[Settings, Depends(get_auth_settings)]
CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


@router.post("/signup", status_code=201, response_model=PublicUser)
def signup(body: SignupRequest, db: Database, clock: RequestClock) -> PublicUser:
    return auth.create_account(db, email=body.email, password=body.password.get_secret_value(),
                               role=UserRole.CUSTOMER, clock=clock,
                               profile=body.model_dump(exclude={"email", "password"}, exclude_none=True))


@router.post("/login", response_model=LoginResponse)
def login(body: Credentials, db: Database, settings: AuthSettings, clock: RequestClock) -> LoginResponse:
    return auth.login(db, email=body.email, password=body.password.get_secret_value(),
                      settings=settings, clock=clock)


@router.get("/me", response_model=PublicUser)
def me(principal: CurrentPrincipal) -> PublicUser:
    return PublicUser.model_validate(principal)


@router.post("/logout", response_model=MessageResponse)
def logout(principal: CurrentPrincipal, db: Database, clock: RequestClock) -> MessageResponse:
    auth.logout(db, principal, clock)
    return MessageResponse(message="Logged out of all sessions.")


@router.post("/password-reset/request", response_model=MessageResponse)
def request_reset(
    body: ResetRequest, db: Database, settings: AuthSettings, clock: RequestClock,
    mailer: Annotated[Mailer, Depends(get_mailer)],
) -> MessageResponse:
    auth.request_password_reset(db, email=body.email, settings=settings, mailer=mailer, clock=clock)
    return MessageResponse(message=auth.RESET_REQUEST_MESSAGE)


@router.post("/password-reset/confirm", response_model=MessageResponse)
def confirm_reset(body: ResetConfirm, db: Database, clock: RequestClock) -> MessageResponse:
    auth.confirm_password_reset(db, token=body.token.get_secret_value(),
                                password=body.new_password.get_secret_value(), clock=clock)
    return MessageResponse(message="Password reset successful. Please log in again.")
