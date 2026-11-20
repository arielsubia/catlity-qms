import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.onboarding import OnboardingMessageRequest, OnboardingResponse
from app.services.onboarding import (
    EmailAlreadyUsed,
    OnboardingView,
    OnboardingWriteError,
    SessionNotFound,
    continue_session,
    start_session,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def _response(view: OnboardingView) -> OnboardingResponse:
    return OnboardingResponse(
        session_id=view.session_id,
        reply=view.reply,
        industry_selected=view.industry_selected,
        kb_assigned=view.kb_assigned,
        checklists_created=view.checklists_created,
        admin_created=view.admin_created,
        knowledge_base_ids=view.knowledge_base_ids,
        tenant_id=view.tenant_id,
    )


@router.post(
    "/start",
    response_model=OnboardingResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_onboarding() -> OnboardingResponse:
    """Open an onboarding session. No token is required."""
    return _response(start_session())


@router.post("/message", response_model=OnboardingResponse)
def send_onboarding_message(
    body: OnboardingMessageRequest,
    db: Session = Depends(get_db),
) -> OnboardingResponse:
    """Store the next fact. The last step writes the tenant and the admin."""
    try:
        view = continue_session(db, session_id=body.session_id, message=body.message)
    except SessionNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Onboarding session not found",
        ) from exc
    except EmailAlreadyUsed as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        ) from exc
    except OnboardingWriteError as exc:
        logger.warning("onboarding message failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Onboarding could not be saved",
        ) from exc
    return _response(view)
