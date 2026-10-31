from dataclasses import dataclass
from datetime import datetime

from app.models.user import User, UserRole


@dataclass(frozen=True)
class Principal:
    id: int
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    auth_version: int

    @classmethod
    def from_user(cls, user: User) -> "Principal":
        return cls(user.id, user.email, user.role, user.is_active, user.created_at, user.auth_version)
