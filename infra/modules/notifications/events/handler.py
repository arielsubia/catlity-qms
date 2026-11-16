"""Set the DynamoDB notification status from an SES event published to SNS.

This file is the deployment copy of ``backend/app/services/notification_status.py``.
The function stays outside the VPC: it only calls DynamoDB, so it does not use the NAT.
"""

from __future__ import annotations

import json
import os
from typing import Any

import boto3
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


def handler(event: dict[str, Any], _context: object, dynamodb: Any = None) -> dict[str, int]:
    """Unwrap SNS records and update one notification row per SES event."""
    client = dynamodb if dynamodb is not None else boto3.client("dynamodb")
    table_name = os.environ["NOTIFICATIONS_TABLE_NAME"]
    updated = 0
    for record in event.get("Records", []):
        if not isinstance(record, dict):
            continue
        sns = record.get("Sns")
        raw = sns.get("Message") if isinstance(sns, dict) else None
        if not isinstance(raw, str):
            continue
        message = json.loads(raw)
        if not isinstance(message, dict):
            continue
        if apply_message(client, table_name, message) in {"delivered", "failed"}:
            updated += 1
    return {"updated": updated}
