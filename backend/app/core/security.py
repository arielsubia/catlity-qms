"""Security utilities — JWT validation and tenant isolation.

Full Cognito JWT validation will be implemented in Task 4.
This module provides the placeholder structure.
"""

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db


def get_current_tenant_id() -> str:
    """Placeholder: extract tenant_id from JWT claims.

    Will be replaced by Cognito token parsing in Task 4.
    """
    # During development, return a default tenant for testing
    return "dev-tenant-001"


def require_tenant_db(
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
) -> tuple[Session, str]:
    """Dependency that provides both db session and validated tenant_id."""
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant identification required",
        )
    return db, tenant_id
