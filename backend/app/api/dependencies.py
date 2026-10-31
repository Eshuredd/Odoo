from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import AuthenticationError, ServiceError
from app.core.principal import Principal
from app.core.security import decode_access_token, signing_key
from app.models import User, UserRole
from app.services.mailer import Mailer

bearer = HTTPBearer(auto_error=False)


def get_auth_settings(request: Request) -> Settings:
    settings = request.app.state.settings
    signing_key(settings)  # Fail closed for every auth endpoint, without disabling health.
    return settings


def get_clock(request: Request) -> Clock:
    return request.app.state.clock


def get_mailer(request: Request) -> Mailer:
    return request.app.state.mailer


def get_current_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    settings: Annotated[Settings, Depends(get_auth_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> Principal:
    if credentials is None:
        raise AuthenticationError()
    identity = decode_access_token(credentials.credentials, signing_key(settings), clock())
    # This independent read session never writes or commits. Closing it ends its read
    # transaction before endpoint services begin their separate write transaction.
    with request.app.state.session_factory(autoflush=False) as session:
        user = session.get(User, identity.user_id)
        if user is None or not user.is_active or user.auth_version != identity.auth_version:
            raise AuthenticationError()
        return Principal.from_user(user)


def require_roles(*roles: UserRole) -> Callable[..., Principal]:
    def require(principal: Annotated[Principal, Depends(get_current_principal)]) -> Principal:
        if principal.role not in roles:
            raise ServiceError(403, "Insufficient permissions")
        return principal
    return require
