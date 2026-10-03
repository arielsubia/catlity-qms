from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_tenant_id
from app.models.tenant import Tenant
from app.schemas.tenant import TenantCreate, TenantResponse, TenantUpdate

router = APIRouter(prefix="/tenants", tags=["tenants"])


def _get_owned_tenant(db: Session, path_tenant_id: str, current_tenant_id: str) -> Tenant:
    """Return the caller's tenant, or 404 when the row is missing or belongs to someone else."""
    tenant = (
        db.query(Tenant)
        .filter(Tenant.id == path_tenant_id, Tenant.id == current_tenant_id)
        .first()
    )
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return tenant


@router.get("/", response_model=list[TenantResponse])
def list_tenants(
    skip: int = 0,
    limit: int = 50,
    current_tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
) -> list[Tenant]:
    """List the tenant assigned to the authenticated caller."""
    return (
        db.query(Tenant)
        .filter(Tenant.id == current_tenant_id)
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant(
    tenant_id: str,
    current_tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
) -> Tenant:
    """Get the authenticated caller's tenant."""
    return _get_owned_tenant(db, tenant_id, current_tenant_id)


@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
def create_tenant(
    tenant_in: TenantCreate,
    db: Session = Depends(get_db),
) -> Tenant:
    """Create a new tenant."""
    tenant = Tenant(
        name=tenant_in.name,
        industry=tenant_in.industry,
        description=tenant_in.description,
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


@router.patch("/{tenant_id}", response_model=TenantResponse)
def update_tenant(
    tenant_id: str,
    tenant_in: TenantUpdate,
    current_tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
) -> Tenant:
    """Update the authenticated caller's tenant."""
    tenant = _get_owned_tenant(db, tenant_id, current_tenant_id)
    update_data = tenant_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tenant, field, value)
    db.commit()
    db.refresh(tenant)
    return tenant


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tenant(
    tenant_id: str,
    current_tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
) -> None:
    """Delete the authenticated caller's tenant."""
    tenant = _get_owned_tenant(db, tenant_id, current_tenant_id)
    db.delete(tenant)
    db.commit()
