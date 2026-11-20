"""Validate the first administrator. This function does not call Cognito."""

from typing import Any

MAX_NAME_LENGTH = 255
MAX_EMAIL_LENGTH = 254


def arguments(event: object) -> dict[str, Any]:
    if not isinstance(event, dict):
        return {}
    nested = event.get("arguments")
    if isinstance(nested, dict):
        return nested
    return event


def valid_email(value: str) -> bool:
    if not value or len(value) > MAX_EMAIL_LENGTH or any(char.isspace() for char in value):
        return False
    local, separator, domain = value.partition("@")
    if not separator or not local or not domain or "@" in domain:
        return False
    if "." not in domain or domain.startswith(".") or domain.endswith("."):
        return False
    return True


def create_admin_user(full_name: object, email: object) -> dict[str, str]:
    """Return a pending admin, or an error the assistant can read back."""
    if not isinstance(full_name, str) or not full_name.strip():
        return {"error": "full_name is required."}
    name = full_name.strip()
    if len(name) > MAX_NAME_LENGTH:
        return {"error": "full_name is too long."}
    if not isinstance(email, str) or not valid_email(email.strip()):
        return {"error": "email is required."}
    return {
        "full_name": name,
        "email": email.strip(),
        "role": "admin",
        "status": "pending",
    }


def handler(event: dict[str, Any], _context: object) -> dict[str, str]:
    args = arguments(event)
    return create_admin_user(args.get("full_name"), args.get("email"))
