from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import CurrentUser, require_role
from app.schemas.quicksight import EmbedUrlResponse
from app.services.quicksight_embed import (
    QuickSightUnavailable,
    embed_dashboard,
    get_quicksight_client,
)

router = APIRouter(prefix="/quicksight", tags=["quicksight"])

DASHBOARD_ROLES = ["admin", "qa_manager"]


@router.get("/embed-url", response_model=EmbedUrlResponse)
def read_embed_url(
    current_user: CurrentUser = Depends(require_role(DASHBOARD_ROLES)),
    client: Any = Depends(get_quicksight_client),
) -> EmbedUrlResponse:
    """Return a 15-minute embed URL for the signed-in Reader.

    Other roles receive 403. A dashboard or Reader that is not in the account
    yet receives 503. This route does not create either one.
    """
    try:
        embed_url, expires_at = embed_dashboard(client, email=current_user.email or "")
    except QuickSightUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return EmbedUrlResponse(embed_url=embed_url, expires_at=expires_at)
