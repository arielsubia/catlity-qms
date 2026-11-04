import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.schemas.normative import (
    NormativeQueryRequest,
    NormativeQueryResponse,
    NormativeReference,
)
from app.services.normative import (
    NormativeBackend,
    NormativeUpstreamError,
    QueryRateLimited,
    TenantNotFound,
    UnsupportedIndustry,
    answer_question,
    get_normative_backend,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai/normative", tags=["normative"])


@router.post("/query", response_model=NormativeQueryResponse)
def query_normative(
    body: NormativeQueryRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    backend: NormativeBackend = Depends(get_normative_backend),
) -> NormativeQueryResponse:
    """Answer a normative question from the tenant's industry notes."""
    try:
        result = answer_question(
            db,
            backend,
            tenant_id=current_user.tenant_id,
            user_id=current_user.sub,
            question=body.question,
        )
    except TenantNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        ) from exc
    except UnsupportedIndustry as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tenant industry must be automotive or pharmaceutical",
        ) from exc
    except QueryRateLimited as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Maximum 10 queries per minute.",
        ) from exc
    except NormativeUpstreamError as exc:
        logger.warning("normative query failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Normative query failed",
        ) from exc

    return NormativeQueryResponse(
        answer=result.answer,
        references=[
            NormativeReference(document=item.document, section=item.section)
            for item in result.references
        ],
    )
