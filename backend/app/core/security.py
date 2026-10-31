import re
import secrets
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache

import jwt
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import Settings
from app.core.errors import AuthenticationError, ServiceError
from app.core.validation import validate_password

ACCESS_TOKEN_SECONDS = 7200
ISSUER = "subcadence-api"
AUDIENCE = "subcadence"
password_hasher = PasswordHasher(type=Type.ID)


def signing_key(settings: Settings) -> str:
    key = settings.auth_secret_key.get_secret_value() if settings.auth_secret_key else ""
    if len(key.encode("utf-8")) < 32 or key != key.strip() or len(set(key)) < 8:
        raise ServiceError(503, "Authentication is not configured")
    return key


def hash_password(password: str) -> str:
    return password_hasher.hash(validate_password(password))


@lru_cache(maxsize=1)
def dummy_password_hash() -> str:
    return password_hasher.hash(secrets.token_urlsafe(32))


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


@dataclass(frozen=True)
class TokenIdentity:
    user_id: int
    auth_version: int


def issue_access_token(user_id: int, auth_version: int, key: str, now: datetime) -> str:
    issued_at = int(now.timestamp())
    return jwt.encode({
        "sub": str(user_id), "iat": issued_at, "exp": issued_at + ACCESS_TOKEN_SECONDS,
        "auth_version": auth_version, "iss": ISSUER, "aud": AUDIENCE,
    }, key, algorithm="HS256")


def decode_access_token(token: str, key: str, now: datetime) -> TokenIdentity:
    if len(token) > 8192:
        raise AuthenticationError()
    try:
        claims = jwt.decode(
            token, key, algorithms=["HS256"], issuer=ISSUER, audience=AUDIENCE,
            options={
                "require": ["sub", "iat", "exp", "auth_version", "iss", "aud"],
                # Validate time strictly below using the same injectable clock as resets.
                "verify_exp": False, "verify_iat": False,
                "strict_aud": True,
            },
        )
    except jwt.InvalidTokenError:
        raise AuthenticationError() from None
    sub, issued, expires, version = (claims[name] for name in ("sub", "iat", "exp", "auth_version"))
    if (
        not isinstance(sub, str) or re.fullmatch(r"[1-9][0-9]{0,18}", sub) is None
        or int(sub) > 9223372036854775807
        or type(issued) is not int or type(expires) is not int or type(version) is not int
        or version < 0 or expires - issued != ACCESS_TOKEN_SECONDS
        or not issued <= int(now.timestamp()) < expires
    ):
        raise AuthenticationError()
    return TokenIdentity(user_id=int(sub), auth_version=version)
