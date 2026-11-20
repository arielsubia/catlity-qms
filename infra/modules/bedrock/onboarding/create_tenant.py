"""Validate a new organization. This function does not write to a database."""

from typing import Any

INDUSTRIES = ("automotive", "pharmaceutical")
MAX_NAME_LENGTH = 255


def arguments(event: object) -> dict[str, Any]:
    if not isinstance(event, dict):
        return {}
    nested = event.get("arguments")
    if isinstance(nested, dict):
        return nested
    return event


def create_tenant(organization_name: object, industry: object) -> dict[str, str]:
    """Return a pending tenant, or an error the assistant can read back."""
    if not isinstance(organization_name, str) or not organization_name.strip():
        return {"error": "organization_name is required."}
    name = organization_name.strip()
    if len(name) > MAX_NAME_LENGTH:
        return {"error": "organization_name is too long."}
    if industry not in INDUSTRIES:
        return {"error": "industry must be automotive or pharmaceutical."}
    return {"organization_name": name, "industry": industry, "status": "pending"}


def handler(event: dict[str, Any], _context: object) -> dict[str, str]:
    args = arguments(event)
    return create_tenant(args.get("organization_name"), args.get("industry"))
