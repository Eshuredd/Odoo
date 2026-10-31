from email_validator import EmailNotValidError, validate_email


def normalize_email(value: str) -> str:
    value = value.strip()
    if not value.isascii():
        raise ValueError("Only ASCII email addresses are supported")
    try:
        result = validate_email(value, check_deliverability=False, allow_smtputf8=False)
    except EmailNotValidError:
        raise ValueError("Enter a valid email address") from None
    if result.ascii_email is None:
        raise ValueError("Only ASCII email addresses are supported")
    return result.ascii_email.lower()


def validate_password(value: str) -> str:
    """Validate without trimming, truncating, or otherwise modifying the password."""
    if not 9 <= len(value) <= 128:
        raise ValueError("Password must contain 9–128 characters")
    if not any(char.isupper() for char in value):
        raise ValueError("Password must contain an uppercase letter")
    if not any(char.islower() for char in value):
        raise ValueError("Password must contain a lowercase letter")
    if not any(not char.isalnum() and not char.isspace() for char in value):
        raise ValueError("Password must contain a special character (not whitespace)")
    return value
