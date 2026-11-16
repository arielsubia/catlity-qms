"""Tenant notification triggers that run inside the API process."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, require_role
from app.services.notifications import get_notification_service

router = APIRouter(tags=["notifications"])


class OverdueReminderResponse(BaseModel):
    """Counts from one overdue-reminder pass for the caller's tenant."""

    sent: int
    failed: int
    skipped: int


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
    batch = get_notification_service().send_overdue_reminders(
        db, current_user.tenant_id
    )
    return OverdueReminderResponse(
        sent=batch.sent, failed=batch.failed, skipped=batch.skipped
    )
