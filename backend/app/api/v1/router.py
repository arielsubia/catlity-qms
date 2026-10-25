from fastapi import APIRouter

from app.api.v1.auditors import router as auditors_router
from app.api.v1.audits import router as audits_router
from app.api.v1.auth import router as auth_router
from app.api.v1.corrective_actions import router as corrective_actions_router
from app.api.v1.findings import router as findings_router
from app.api.v1.health import router as health_router
from app.api.v1.tenants import router as tenants_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(tenants_router)
api_router.include_router(audits_router)
api_router.include_router(auditors_router)
api_router.include_router(findings_router)
api_router.include_router(corrective_actions_router)
