"""Tenant notification triggers and the in-app notification center."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user, require_role
from app.services.notifications import InboxItem, get_notification_service

router = APIRouter(tags=["notifications"])


class OverdueReminderResponse(BaseModel):
    """Counts from one overdue-reminder pass for the caller's tenant."""

    sent: int
    failed: int
    skipped: int


class NotificationResponse(BaseModel):
    """One row in the caller's notification center."""

    id: str
    kind: str
    title: str
    finding_id: str | None
    read: bool
    created_at: str | None
    status: str


class NotificationListResponse(BaseModel):
    """Newest notifications for the caller, plus the unread total."""

    items: list[NotificationResponse]
    unread_count: int


class NotificationReadUpdate(BaseModel):
    """The center only marks a row read. It does not reopen it."""

    read: Literal[True]


class NotificationReadResponse(BaseModel):
    """Confirmation that one row is now read."""

    id: str
    read: bool


class NotificationReadAllResponse(BaseModel):
    """How many of the caller's rows changed to read."""

    updated: int


def _caller_email(current_user: CurrentUser) -> str:
    if not current_user.email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token is missing an email",
        )
    return current_user.email


def _to_response(item: InboxItem) -> NotificationResponse:
    return NotificationResponse(
        id=item.id,
        kind=item.kind,
        title=item.title,
        finding_id=item.finding_id,
        read=item.read,
        created_at=item.created_at,
        status=item.status,
    )


@router.get("/notifications", response_model=NotificationListResponse)
def list_notifications(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    current_user: CurrentUser = Depends(get_current_user),
) -> NotificationListResponse:
    """List the caller's notifications, newest first.

    ``unread_count`` covers every unread row, not only this page. The query
    reads ``catlity-qms-dev-notifications`` with the process credentials.
    """
    page = get_notification_service().list_inbox(
        current_user.tenant_id, _caller_email(current_user), limit
    )
    return NotificationListResponse(
        items=[_to_response(item) for item in page.items],
        unread_count=page.unread_count,
    )


@router.post("/notifications/read", response_model=NotificationReadAllResponse)
def mark_notifications_read(
    current_user: CurrentUser = Depends(get_current_user),
) -> NotificationReadAllResponse:
    """Mark every unread notification for the caller as read."""
    updated = get_notification_service().mark_all_read(
        current_user.tenant_id, _caller_email(current_user)
    )
    return NotificationReadAllResponse(updated=updated)


@router.patch(
    "/notifications/{notification_id}",
    response_model=NotificationReadResponse,
)
def mark_notification_read(
    notification_id: str,
    body: NotificationReadUpdate,
    current_user: CurrentUser = Depends(get_current_user),
) -> NotificationReadResponse:
    """Mark one of the caller's notifications as read.

    ``body`` only accepts ``read: true``. Another recipient's row is not found.
    The delivery status on the row is left unchanged.
    """
    if not body.read:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A notification can only be marked read",
        )
    found = get_notification_service().mark_read(
        current_user.tenant_id, notification_id, _caller_email(current_user)
    )
    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )
    return NotificationReadResponse(id=notification_id, read=True)


@router.post(
    "/notifications/overdue-reminders",
    response_model=OverdueReminderResponse,
)
def send_overdue_reminders(
    current_user: CurrentUser = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
) -> OverdueReminderResponse:
    """Mail the responsible user for each overdue corrective action.

    Only a tenant admin can run the pass. The scan reads the local database.
    There is no schedule in AWS: the API is not on Fargate and RDS is not applied.
    """
    batch = get_notification_service().send_overdue_reminders(db, current_user.tenant_id)
    return OverdueReminderResponse(sent=batch.sent, failed=batch.failed, skipped=batch.skipped)
