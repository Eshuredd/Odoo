class ServiceError(Exception):
    """A deliberately public, credential-free error message."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class AuthenticationError(ServiceError):
    def __init__(self) -> None:
        super().__init__(401, "Invalid or missing authentication")
