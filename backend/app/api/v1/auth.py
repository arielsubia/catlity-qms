from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user, get_optional_user
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import (
    ALLOWED_ROLES,
    DEFAULT_ROLE,
    CurrentUserResponse,
    RegisterRequest,
    RegisterResponse,
)
from app.services import cognito

router = APIRouter(prefix="/auth", tags=["auth"])


def _caller_is_admin(caller: CurrentUser) -> bool:
    return "admin" in {caller.role, *caller.groups}


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    caller: Annotated[CurrentUser | None, Depends(get_optional_user)] = None,
) -> User:
    """Register a new user in Cognito and persist the local profile.

    Anonymous callers can only create an auditee. Any other role requires an
    admin of the same tenant. The caller cannot use this endpoint to change
    their own tenant or role.
    """
    role = payload.normalized_role
    if role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid role. Allowed roles: {', '.join(ALLOWED_ROLES)}",
        )

    if (
        caller is not None
        and caller.email is not None
        and caller.email.casefold() == payload.email.casefold()
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot change your own tenant or role",
        )

    if role != DEFAULT_ROLE:
        if caller is None or not _caller_is_admin(caller):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Assigning a role other than auditee requires a tenant admin",
            )
        if caller.tenant_id != payload.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="A tenant admin can only assign roles inside their own organization",
            )

    tenant = db.query(Tenant).filter(Tenant.id == payload.tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    try:
        cognito_sub = cognito.register_user(
            email=payload.email,
            password=payload.password,
            tenant_id=payload.tenant_id,
            role=role,
        )
    except cognito.CognitoError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    user = User(
        tenant_id=payload.tenant_id,
        cognito_sub=cognito_sub or None,
        email=payload.email,
        full_name=payload.full_name,
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/me", response_model=CurrentUserResponse)
def read_current_user(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUserResponse:
    """Return the authenticated principal derived from the bearer token."""
    return CurrentUserResponse(
        sub=current_user.sub,
        email=current_user.email,
        tenant_id=current_user.tenant_id,
        role=current_user.role,
        groups=list(current_user.groups),
    )
