"""Send SES templates and store each attempt in the notification table.

A successful send is ``sent``. The SNS subscriber moves that row to
``delivered`` or ``failed`` when SES publishes the matching event.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import uuid4

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.corrective_action import CorrectiveAction
from app.models.user import User
from app.services.notification_status import apply_message

logger = logging.getLogger(__name__)

# One try, then three waits. A transient SES error spends about seven seconds.
BACKOFF_SECONDS = (1, 2, 4)
FINDING_ASSIGNED = "finding_assigned"
ACTION_OVERDUE = "corrective_action_overdue"


@dataclass(frozen=True)
class ReminderBatch:
    """How many overdue actions were mailed, skipped, or stored as failed."""

    sent: int
    failed: int
    skipped: int


class NotificationService:
    """SES templated email plus the DynamoDB history row."""

    def __init__(
        self,
        ses_client: Any | None = None,
        dynamodb_client: Any | None = None,
        sleep: Callable[[float], None] | None = None,
        today: date | None = None,
    ) -> None:
        self._ses = ses_client or boto3.client("ses", region_name=settings.aws_region)
        self._dynamodb = dynamodb_client or boto3.client(
            "dynamodb", region_name=settings.aws_region
        )
        self._sleep = sleep or time.sleep
        self._today = today or date.today()
        self._table_name = settings.notifications_table_name

    def send_finding_assigned(
        self,
        *,
        tenant_id: str,
        finding_id: str,
        recipient_email: str,
        recipient_name: str,
        finding_title: str,
        audit_name: str,
    ) -> str:
        """Mail the assignee and return the notification id."""
        action_url = f"{settings.app_public_url.rstrip('/')}/findings"
        return self._send(
            tenant_id=tenant_id,
            resource_id=finding_id,
            kind=FINDING_ASSIGNED,
            template=settings.finding_assigned_template,
            recipient_email=recipient_email,
            template_data={
                "recipient_name": recipient_name,
                "finding_title": finding_title,
                "audit_name": audit_name,
                "action_url": action_url,
            },
        )

    def send_overdue_reminders(self, db: Session, tenant_id: str) -> ReminderBatch:
        """Mail the responsible user for each overdue action of one tenant.

        An action is overdue when its due date is before today and it has no
        completion date. The recipient is ``responsible_id`` when that user is
        active, otherwise the finding's active auditee. A row already ``sent``
        or ``delivered`` for the same action is not mailed again.
        """
        actions = (
            db.query(CorrectiveAction)
            .filter(
                CorrectiveAction.tenant_id == tenant_id,
                CorrectiveAction.due_date.is_not(None),
                CorrectiveAction.due_date < self._today,
                CorrectiveAction.completion_date.is_(None),
            )
            .all()
        )
        sent = 0
        failed = 0
        skipped = 0
        for action in actions:
            recipient = _recipient(db, action)
            if recipient is None or self._already_open(tenant_id, action.id):
                skipped += 1
                continue
            due = action.due_date.isoformat() if action.due_date else ""
            action_url = f"{settings.app_public_url.rstrip('/')}/findings"
            status = self._send_status(
                tenant_id=tenant_id,
                resource_id=action.id,
                kind=ACTION_OVERDUE,
                template=settings.corrective_action_overdue_template,
                recipient_email=recipient.email,
                template_data={
                    "recipient_name": recipient.full_name,
                    "action_description": action.description,
                    "due_date": due,
                    "action_url": action_url,
                },
            )
            if status == "sent":
                sent += 1
            else:
                failed += 1
        return ReminderBatch(sent=sent, failed=failed, skipped=skipped)

    def record_delivery(self, message: dict[str, Any]) -> str:
        """Apply one SES event JSON to the matching history row."""
        return apply_message(self._dynamodb, self._table_name, message)

    def _send(
        self,
        *,
        tenant_id: str,
        resource_id: str,
        kind: str,
        template: str,
        recipient_email: str,
        template_data: dict[str, str],
    ) -> str:
        notification_id, _status = self._deliver(
            tenant_id=tenant_id,
            resource_id=resource_id,
            kind=kind,
            template=template,
            recipient_email=recipient_email,
            template_data=template_data,
        )
        return notification_id

    def _send_status(
        self,
        *,
        tenant_id: str,
        resource_id: str,
        kind: str,
        template: str,
        recipient_email: str,
        template_data: dict[str, str],
    ) -> str:
        _notification_id, status = self._deliver(
            tenant_id=tenant_id,
            resource_id=resource_id,
            kind=kind,
            template=template,
            recipient_email=recipient_email,
            template_data=template_data,
        )
        return status

    def _deliver(
        self,
        *,
        tenant_id: str,
        resource_id: str,
        kind: str,
        template: str,
        recipient_email: str,
        template_data: dict[str, str],
    ) -> tuple[str, str]:
        notification_id = str(uuid4())
        message_id = ""
        error = ""
        try:
            message_id = self._send_with_retry(
                template=template,
                recipient_email=recipient_email,
                template_data=template_data,
                tenant_id=tenant_id,
                notification_id=notification_id,
            )
            status = "sent"
        except (ClientError, BotoCoreError) as exc:
            status = "failed"
            error = _error_code(exc)
            logger.warning(
                "notification %s was not sent (%s)", notification_id, error
            )
        item = {
            "tenant_id": tenant_id,
            "notification_id": notification_id,
            "status": status,
            "kind": kind,
            "resource_id": resource_id,
            "recipient_email": recipient_email,
        }
        if message_id:
            item["ses_message_id"] = message_id
        if error:
            item["error"] = error
        self._dynamodb.put_item(
            TableName=self._table_name,
            Item={key: {"S": value} for key, value in item.items()},
        )
        return notification_id, status

    def _send_with_retry(
        self,
        *,
        template: str,
        recipient_email: str,
        template_data: dict[str, str],
        tenant_id: str,
        notification_id: str,
    ) -> str:
        delays = iter(BACKOFF_SECONDS)
        while True:
            try:
                response = self._ses.send_templated_email(
                    Source=settings.ses_sender_email,
                    Destination={"ToAddresses": [recipient_email]},
                    Template=template,
                    TemplateData=json.dumps(template_data),
                    ConfigurationSetName=settings.ses_configuration_set,
                    Tags=[
                        {"Name": "tenant_id", "Value": tenant_id},
                        {"Name": "notification_id", "Value": notification_id},
                    ],
                )
                return str(response["MessageId"])
            except (ClientError, BotoCoreError):
                delay = next(delays, None)
                if delay is None:
                    raise
                self._sleep(delay)

    def _already_open(self, tenant_id: str, resource_id: str) -> bool:
        response = self._dynamodb.query(
            TableName=self._table_name,
            KeyConditionExpression="tenant_id = :tenant_id",
            ExpressionAttributeValues={":tenant_id": {"S": tenant_id}},
        )
        for item in response.get("Items", []):
            same_action = item.get("resource_id", {}).get("S") == resource_id
            same_kind = item.get("kind", {}).get("S") == ACTION_OVERDUE
            status = item.get("status", {}).get("S")
            if same_action and same_kind and status in {"sent", "delivered"}:
                return True
        return False


def get_notification_service() -> NotificationService:
    """Build a service with the process credentials."""
    return NotificationService()


def _recipient(db: Session, action: CorrectiveAction) -> User | None:
    if action.responsible_id:
        responsible = (
            db.query(User)
            .filter(
                User.id == action.responsible_id,
                User.tenant_id == action.tenant_id,
                User.is_active.is_(True),
            )
            .first()
        )
        if responsible is not None:
            return responsible
    finding = action.finding
    if finding is None or not finding.assignee_id:
        return None
    assignee = (
        db.query(User)
        .filter(
            User.id == finding.assignee_id,
            User.tenant_id == action.tenant_id,
            User.role == "auditee",
            User.is_active.is_(True),
        )
        .first()
    )
    return assignee


def _error_code(exc: Exception) -> str:
    if isinstance(exc, ClientError):
        return str(exc.response.get("Error", {}).get("Code", "SendFailed"))
    return exc.__class__.__name__
