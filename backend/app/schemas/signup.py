from typing import Annotated

from pydantic import StringConstraints

from app.schemas.auth import AccountCreate


class SignupRequest(AccountCreate):
    company_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ""
    contact_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)] | None = None
    phone: Annotated[str, StringConstraints(max_length=50)] | None = None
