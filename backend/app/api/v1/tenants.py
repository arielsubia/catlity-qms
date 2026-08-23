from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.tenant import Tenant
from app.schemas.tenant import TenantCreate, TenantResponse, TenantUpdate

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/", response_model=list[TenantResponse])
def list_tenants(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[Tenant]:
    """List all tenants with pagination."""
    return db.query(Tenant).offset(skip).limit(limit).all()


@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant(
    tenant_id: str,
    db: Session = Depends(get_db),
) -> Tenant:
    """Get a specific tenant by ID."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return tenant


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
    db: Session = Depends(get_db),
) -> Tenant:
    """Update an existing tenant."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    update_data = tenant_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tenant, field, value)
    db.commit()
    db.refresh(tenant)
    return tenant


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tenant(
    tenant_id: str,
    db: Session = Depends(get_db),
) -> None:
    """Delete a tenant."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    db.delete(tenant)
    db.commit()
