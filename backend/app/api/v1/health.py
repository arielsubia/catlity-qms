from fastapi import APIRouter

from app.core.config import settings
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Application health check endpoint."""
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        service=settings.app_name,
    )
