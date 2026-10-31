from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, SecretStr, field_validator

from app.core.validation import normalize_email, validate_password
from app.models.user import UserRole

CanonicalEmail = Annotated[str, AfterValidator(normalize_email)]


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: CanonicalEmail
    password: SecretStr = Field(min_length=1, max_length=128)


class AccountCreate(Credentials):
    @field_validator("password")
    @classmethod
    def password_policy(cls, value: SecretStr) -> SecretStr:
        validate_password(value.get_secret_value())
        return value


class ResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: CanonicalEmail


class ResetConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: SecretStr = Field(min_length=1, max_length=512)
    new_password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_policy(cls, value: SecretStr) -> SecretStr:
        validate_password(value.get_secret_value())
        return value


class PublicUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = 7200
    user: PublicUser


class MessageResponse(BaseModel):
    message: str
