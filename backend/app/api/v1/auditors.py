from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, require_role
from app.models.user import User
from app.schemas.audit import AvailableAuditor

router = APIRouter(prefix="/auditors", tags=["auditors"])

AUDITOR_LIST_ROLES = ["lead_auditor", "admin"]


@router.get("/", response_model=list[AvailableAuditor])
def list_available_auditors(
    current_user: CurrentUser = Depends(require_role(AUDITOR_LIST_ROLES)),
    db: Session = Depends(get_db),
) -> list[User]:
    """List active auditors of the caller's tenant.

    A lead auditor uses this roster when assigning who executes an audit.
    """
    return (
        db.query(User)
        .filter(
            User.tenant_id == current_user.tenant_id,
            User.role == "auditor",
            User.is_active.is_(True),
        )
        .order_by(User.full_name, User.id)
        .all()
    )
