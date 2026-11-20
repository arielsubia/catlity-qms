"""Return a short starter checklist. This function does not write to a database."""

from typing import Any

INDUSTRIES = ("automotive", "pharmaceutical")

COMMON_ITEMS = (
    {
        "key": "quality-policy",
        "title": "The quality policy is written down and approved.",
    },
    {
        "key": "roles",
        "title": "Quality roles and responsibilities are assigned.",
    },
    {
        "key": "documents",
        "title": "The procedures the team uses are the current approved copies.",
    },
)

INDUSTRY_ITEMS = {
    "automotive": (
        {
            "key": "customer-requirements",
            "title": "Customer-specific requirements are listed for the product.",
        },
        {
            "key": "process-controls",
            "title": "Production process controls are documented.",
        },
    ),
    "pharmaceutical": (
        {
            "key": "batch-record",
            "title": "Batch records are complete before the batch is released.",
        },
        {
            "key": "training",
            "title": "People who perform GMP tasks have a training record.",
        },
    ),
}


def arguments(event: object) -> dict[str, Any]:
    if not isinstance(event, dict):
        return {}
    nested = event.get("arguments")
    if isinstance(nested, dict):
        return nested
    return event


def generate_checklists(industry: object) -> dict[str, Any]:
    """Return common items plus the items for one industry."""
    if industry not in INDUSTRIES:
        return {"error": "industry must be automotive or pharmaceutical."}
    return {
        "industry": industry,
        "items": [*COMMON_ITEMS, *INDUSTRY_ITEMS[industry]],
        "status": "pending",
    }


def handler(event: dict[str, Any], _context: object) -> dict[str, Any]:
    return generate_checklists(arguments(event).get("industry"))
