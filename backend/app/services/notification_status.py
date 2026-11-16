"""Map an SES delivery event onto one notification row.

The Lambda in ``infra/modules/notifications/events`` copies this mapping.
``tests/test_notifications.py`` checks that the two copies stay aligned.
"""

from __future__ import annotations

from typing import Any

from botocore.exceptions import ClientError

STATUS_BY_EVENT = {
    "Delivery": "delivered",
    "Bounce": "failed",
    "Complaint": "failed",
    "Reject": "failed",
}


def status_for_event(message: dict[str, Any]) -> str | None:
    """Return the DynamoDB status for one SES event, or None when it is ignored."""
    event_type = message.get("eventType") or message.get("notificationType")
    if not isinstance(event_type, str):
        return None
    return STATUS_BY_EVENT.get(event_type)


def notification_key(message: dict[str, Any]) -> tuple[str, str] | None:
    """Read the tenant and notification id stored as SES message tags."""
    mail = message.get("mail")
    if not isinstance(mail, dict):
        return None
    tags = mail.get("tags")
    if not isinstance(tags, dict):
        return None
    tenant_id = _first(tags.get("tenant_id"))
    notification_id = _first(tags.get("notification_id"))
    if tenant_id is None or notification_id is None:
        return None
    return tenant_id, notification_id


def apply_message(client: Any, table_name: str, message: dict[str, Any]) -> str:
    """Update one existing row. A missing row or an unknown event is left untouched."""
    status = status_for_event(message)
    key = notification_key(message)
    if status is None or key is None:
        return "ignored"
    tenant_id, notification_id = key
    try:
        client.update_item(
            TableName=table_name,
            Key={
                "tenant_id": {"S": tenant_id},
                "notification_id": {"S": notification_id},
            },
            UpdateExpression="SET #status = :status",
            ConditionExpression="attribute_exists(notification_id)",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": {"S": status}},
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code == "ConditionalCheckFailedException":
            return "missing"
        raise
    return status


def _first(value: object) -> str | None:
    if isinstance(value, list) and value and isinstance(value[0], str) and value[0]:
        return value[0]
    if isinstance(value, str) and value:
        return value
    return None
