"""Onboarding session for a new organization.

The harness ``Onboarding_Assistant`` and its four Lambdas are defined and not
applied. This service calls the same four Python functions. It does not call
``invoke_harness`` and it does not call ``bedrock:GetKnowledgeBase``. The
knowledge base ids are the ones already applied. ``assign_kb`` only checks
that the industry is known and returns common plus that industry.

The session lives in this process. A restart drops an unfinished session.
The tenant, the starter checklist, and the admin user are written together,
in the local database, when the administrator name and email are accepted.
No Cognito user is created.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.checklist import Checklist, ChecklistItem
from app.models.tenant import Tenant
from app.models.user import User

logger = logging.getLogger(__name__)

ASK_ORGANIZATION = (
    "Send the organization name and the industry, separated by a comma. "
    "The industry is automotive or pharmaceutical."
)
ASK_ADMIN = "Send the administrator full name and email, separated by a comma."

_HANDLERS = (
    Path(__file__).resolve().parents[3] / "infra" / "modules" / "bedrock" / "onboarding"
)
_MODULES: dict[str, ModuleType] = {}
_SESSIONS: dict[str, "OnboardingSession"] = {}
_LOCK = threading.Lock()


class SessionNotFound(Exception):
    """No onboarding session has this id in this process."""


class EmailAlreadyUsed(Exception):
    """The administrator email is already stored for another user."""


class OnboardingWriteError(Exception):
    """The local database rejected the completed onboarding."""


@dataclass
class OnboardingSession:
    """One registration. The four flags are the checklist state."""

    session_id: str
    reply: str
    industry_selected: bool = False
    kb_assigned: bool = False
    checklists_created: bool = False
    admin_created: bool = False
    organization_name: str | None = None
    industry: str | None = None
    knowledge_base_ids: dict[str, str] | None = None
    checklist_items: list[dict[str, str]] | None = None
    admin_name: str | None = None
    admin_email: str | None = None
    tenant_id: str | None = None


@dataclass(frozen=True)
class OnboardingView:
    """A copy of the session fields returned to the route."""

    session_id: str
    reply: str
    industry_selected: bool
    kb_assigned: bool
    checklists_created: bool
    admin_created: bool
    knowledge_base_ids: dict[str, str] | None
    tenant_id: str | None


class _ConfirmingKnowledgeBases:
    """Stand-in for bedrock-agent. It does not call AWS."""

    def get_knowledge_base(self, knowledgeBaseId: str) -> dict[str, str]:
        return {"knowledgeBaseId": knowledgeBaseId}


def reset_sessions() -> None:
    """Drop every in-memory session. Tests call this between cases."""
    with _LOCK:
        _SESSIONS.clear()


def start_session() -> OnboardingView:
    """Open a session and ask for the organization."""
    session = OnboardingSession(session_id=str(uuid.uuid4()), reply=ASK_ORGANIZATION)
    with _LOCK:
        _SESSIONS[session.session_id] = session
        return _view(session)


def continue_session(db: Session, *, session_id: str, message: str) -> OnboardingView:
    """Record the next fact. The finishing message writes the three rows."""
    with _LOCK:
        session = _SESSIONS.get(session_id)
        if session is None:
            raise SessionNotFound(session_id)
        if session.admin_created:
            return _view(session)
        if not session.checklists_created:
            _apply_organization(session, message)
            return _view(session)
        _apply_admin(db, session, message)
        return _view(session)


def _load_handler(name: str) -> ModuleType:
    cached = _MODULES.get(name)
    if cached is not None:
        return cached
    path = _HANDLERS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"onboarding_{name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _MODULES[name] = module
    return module


def _knowledge_bases() -> dict[str, str]:
    return {
        "common": settings.normative_kb_common_id,
        "automotive": settings.normative_kb_automotive_id,
        "pharmaceutical": settings.normative_kb_pharmaceutical_id,
    }


def _split_pair(text: str) -> tuple[str, str] | None:
    if "," not in text:
        return None
    left, _, right = text.rpartition(",")
    left = left.strip()
    right = right.strip()
    if not left or not right:
        return None
    return left, right


def _apply_organization(session: OnboardingSession, message: str) -> None:
    pair = _split_pair(message)
    if pair is None:
        session.reply = ASK_ORGANIZATION
        return
    organization_name, industry = pair
    industry = industry.casefold()
    created = _load_handler("create_tenant").create_tenant(organization_name, industry)
    if "error" in created:
        session.reply = f"{created['error']} {ASK_ORGANIZATION}"
        return
    assigned = _load_handler("assign_kb").assign_kb(
        industry,
        _knowledge_bases(),
        _ConfirmingKnowledgeBases(),
    )
    if "error" in assigned:
        session.reply = f"{assigned['error']} {ASK_ORGANIZATION}"
        return
    generated = _load_handler("generate_checklists").generate_checklists(industry)
    if "error" in generated:
        session.reply = f"{generated['error']} {ASK_ORGANIZATION}"
        return
    session.organization_name = created["organization_name"]
    session.industry = created["industry"]
    session.knowledge_base_ids = dict(assigned["knowledge_base_ids"])
    session.checklist_items = [dict(item) for item in generated["items"]]
    session.industry_selected = True
    session.kb_assigned = True
    session.checklists_created = True
    session.reply = ASK_ADMIN


def _apply_admin(db: Session, session: OnboardingSession, message: str) -> None:
    pair = _split_pair(message)
    if pair is None:
        session.reply = ASK_ADMIN
        return
    full_name, email = pair
    created = _load_handler("create_admin_user").create_admin_user(full_name, email)
    if "error" in created:
        session.reply = f"{created['error']} {ASK_ADMIN}"
        return
    if _email_exists(db, created["email"]):
        raise EmailAlreadyUsed(created["email"])
    try:
        tenant = _write_organization(db, session, created)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.warning("onboarding write failed: %s", exc)
        raise OnboardingWriteError("Onboarding could not be saved") from exc
    session.admin_name = created["full_name"]
    session.admin_email = created["email"]
    session.tenant_id = tenant.id
    session.admin_created = True
    session.reply = _summary(session)


def _email_exists(db: Session, email: str) -> bool:
    return db.query(User).filter(User.email == email).first() is not None


def _write_organization(
    db: Session,
    session: OnboardingSession,
    admin: dict[str, str],
) -> Tenant:
    """Insert the active tenant, its checklist, and the admin user."""
    tenant = Tenant(
        name=session.organization_name or "",
        industry=session.industry or "",
        is_active=True,
    )
    db.add(tenant)
    db.flush()
    checklist = Checklist(
        tenant_id=tenant.id,
        name="Starter checklist",
        description=f"Starter checklist for {session.industry}.",
        standard_reference="ISO 9001",
    )
    db.add(checklist)
    db.flush()
    for order, item in enumerate(session.checklist_items or []):
        db.add(
            ChecklistItem(
                checklist_id=checklist.id,
                order=order,
                clause_reference=item["key"],
                question=item["title"],
                is_mandatory=True,
            )
        )
    db.add(
        User(
            tenant_id=tenant.id,
            cognito_sub=None,
            email=admin["email"],
            full_name=admin["full_name"],
            role="admin",
            is_active=True,
        )
    )
    db.commit()
    return tenant


def _summary(session: OnboardingSession) -> str:
    ids = session.knowledge_base_ids or {}
    listed = ", ".join(f"{name} {kb_id}" for name, kb_id in ids.items())
    return (
        f"{session.organization_name} is active in {session.industry}. "
        f"Knowledge bases: {listed}. "
        f"Administrator: {session.admin_name} <{session.admin_email}>."
    )


def _view(session: OnboardingSession) -> OnboardingView:
    ids = dict(session.knowledge_base_ids) if session.knowledge_base_ids else None
    return OnboardingView(
        session_id=session.session_id,
        reply=session.reply,
        industry_selected=session.industry_selected,
        kb_assigned=session.kb_assigned,
        checklists_created=session.checklists_created,
        admin_created=session.admin_created,
        knowledge_base_ids=ids,
        tenant_id=session.tenant_id,
    )
