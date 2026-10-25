from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.findings import (
    ADMIN_ROLES,
    _get_tenant_finding,
    _holds_role,
    _is_assigned_auditee,
)
from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.corrective_action import CorrectiveAction
from app.models.finding import Finding
from app.schemas.corrective_action import (
    CorrectiveActionCreate,
    CorrectiveActionListResponse,
    CorrectiveActionResponse,
    CorrectiveActionUpdate,
)

router = APIRouter(tags=["corrective-actions"])


def _require_action_editor(
    db: Session, current_user: CurrentUser, finding: Finding
) -> None:
    """Allow the assigned auditee or a tenant admin to change actions."""
    if _holds_role(current_user, ADMIN_ROLES) or _is_assigned_auditee(
        db, current_user, finding
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You cannot change corrective actions for this finding",
    )


def _get_tenant_action(
    db: Session, action_id: str, tenant_id: str
) -> CorrectiveAction:
    """Return the action when it belongs to the caller, otherwise 404."""
    action = (
        db.query(CorrectiveAction)
        .filter(
            CorrectiveAction.id == action_id,
            CorrectiveAction.tenant_id == tenant_id,
        )
        .first()
    )
    if action is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Corrective action not found",
        )
    return action


@router.post(
    "/findings/{finding_id}/corrective-actions",
    response_model=CorrectiveActionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_corrective_action(
    finding_id: str,
    action_in: CorrectiveActionCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CorrectiveAction:
    """Create a corrective action on a finding of the caller's tenant.

    A finding can hold several actions. The new row stays ``pending`` and
    ``corrective``, with no responsible user.
    """
    finding = _get_tenant_finding(db, finding_id, current_user.tenant_id)
    _require_action_editor(db, current_user, finding)
    action = CorrectiveAction(
        tenant_id=current_user.tenant_id,
        finding_id=finding_id,
        description=action_in.description,
        due_date=action_in.due_date,
        completion_date=action_in.completion_date,
        effectiveness=action_in.effectiveness,
        action_type="corrective",
        status="pending",
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action


@router.get(
    "/findings/{finding_id}/corrective-actions",
    response_model=CorrectiveActionListResponse,
)
def list_corrective_actions(
    finding_id: str,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CorrectiveActionListResponse:
    """List corrective actions recorded on one finding of the caller's tenant."""
    _get_tenant_finding(db, finding_id, current_user.tenant_id)
    query = db.query(CorrectiveAction).filter(
        CorrectiveAction.tenant_id == current_user.tenant_id,
        CorrectiveAction.finding_id == finding_id,
    )
    total = query.count()
    items = (
        query.order_by(CorrectiveAction.created_at.desc(), CorrectiveAction.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return CorrectiveActionListResponse(
        items=items, total=total, skip=skip, limit=limit
    )


@router.get(
    "/corrective-actions/{action_id}",
    response_model=CorrectiveActionResponse,
)
def get_corrective_action(
    action_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CorrectiveAction:
    """Return one corrective action when it belongs to the caller's tenant."""
    return _get_tenant_action(db, action_id, current_user.tenant_id)


@router.patch(
    "/corrective-actions/{action_id}",
    response_model=CorrectiveActionResponse,
)
def update_corrective_action(
    action_id: str,
    action_in: CorrectiveActionUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CorrectiveAction:
    """Update description, dates, or effectiveness for an action in the tenant.

    Status, action type, the responsible user, and the parent finding stay
    unchanged.
    """
    action = _get_tenant_action(db, action_id, current_user.tenant_id)
    finding = _get_tenant_finding(db, action.finding_id, current_user.tenant_id)
    _require_action_editor(db, current_user, finding)
    update_data = action_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(action, field, value)
    db.commit()
    db.refresh(action)
    return action


@router.delete(
    "/corrective-actions/{action_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_corrective_action(
    action_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Delete one corrective action that belongs to the caller's tenant."""
    action = _get_tenant_action(db, action_id, current_user.tenant_id)
    finding = _get_tenant_finding(db, action.finding_id, current_user.tenant_id)
    _require_action_editor(db, current_user, finding)
    db.delete(action)
    db.commit()
