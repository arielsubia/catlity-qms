"""Onboarding routes. The harness is not called and Bedrock is not called."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.checklist import Checklist, ChecklistItem
from app.models.tenant import Tenant
from app.models.user import User
from app.services.onboarding import reset_sessions

AUTOMOTIVE_BASES = {
    "common": "OTQJ8TMBNI",
    "automotive": "QWONN58E2H",
}
PHARMACEUTICAL_BASES = {
    "common": "OTQJ8TMBNI",
    "pharmaceutical": "DX3IVAFQ6K",
}


@pytest.fixture(autouse=True)
def clean_sessions() -> Generator[None, None, None]:
    reset_sessions()
    yield
    reset_sessions()


def start(client: TestClient) -> str:
    response = client.post("/api/v1/onboarding/start")
    assert response.status_code == 201
    body = response.json()
    assert body["industry_selected"] is False
    assert body["kb_assigned"] is False
    assert body["checklists_created"] is False
    assert body["admin_created"] is False
    assert body["tenant_id"] is None
    return body["session_id"]


def test_start_opens_a_session_without_a_token(client: TestClient) -> None:
    response = client.post("/api/v1/onboarding/start")

    assert response.status_code == 201
    body = response.json()
    assert body["session_id"]
    assert "comma" in body["reply"]
    assert body["knowledge_base_ids"] is None


def test_message_rejects_an_unknown_session(client: TestClient) -> None:
    response = client.post(
        "/api/v1/onboarding/message",
        json={"session_id": "missing-session", "message": "North Plant, automotive"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Onboarding session not found"


def test_message_rejects_a_blank_message(client: TestClient) -> None:
    session_id = start(client)

    response = client.post(
        "/api/v1/onboarding/message",
        json={"session_id": session_id, "message": "   "},
    )

    assert response.status_code == 422


def test_organization_message_sets_three_flags_and_the_knowledge_bases(
    client: TestClient,
    db: Session,
) -> None:
    session_id = start(client)

    response = client.post(
        "/api/v1/onboarding/message",
        json={"session_id": session_id, "message": "North Plant, automotive"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["industry_selected"] is True
    assert body["kb_assigned"] is True
    assert body["checklists_created"] is True
    assert body["admin_created"] is False
    assert body["knowledge_base_ids"] == AUTOMOTIVE_BASES
    assert body["tenant_id"] is None
    assert db.query(Tenant).count() == 0
    assert db.query(Checklist).count() == 0


def test_a_missing_industry_leaves_the_session_unchanged(
    client: TestClient,
    db: Session,
) -> None:
    session_id = start(client)

    response = client.post(
        "/api/v1/onboarding/message",
        json={"session_id": session_id, "message": "North Plant"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["industry_selected"] is False
    assert body["kb_assigned"] is False
    assert body["checklists_created"] is False
    assert body["admin_created"] is False
    assert db.query(Tenant).count() == 0


def test_admin_message_creates_an_active_tenant_checklist_and_admin(
    client: TestClient,
    db: Session,
) -> None:
    session_id = start(client)
    client.post(
        "/api/v1/onboarding/message",
        json={"session_id": session_id, "message": "North Plant, automotive"},
    )

    response = client.post(
        "/api/v1/onboarding/message",
        json={"session_id": session_id, "message": "Ada Lovelace, ada@north.example"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["admin_created"] is True
    assert body["industry_selected"] is True
    assert body["kb_assigned"] is True
    assert body["checklists_created"] is True
    assert body["knowledge_base_ids"] == AUTOMOTIVE_BASES
    tenant = db.query(Tenant).filter(Tenant.id == body["tenant_id"]).one()
    assert tenant.name == "North Plant"
    assert tenant.industry == "automotive"
    assert tenant.is_active is True
    checklist = db.query(Checklist).filter(Checklist.tenant_id == tenant.id).one()
    items = (
        db.query(ChecklistItem)
        .filter(ChecklistItem.checklist_id == checklist.id)
        .order_by(ChecklistItem.order)
        .all()
    )
    assert len(items) == 5
    assert items[0].question == "The quality policy is written down and approved."
    admin = db.query(User).filter(User.tenant_id == tenant.id).one()
    assert admin.email == "ada@north.example"
    assert admin.full_name == "Ada Lovelace"
    assert admin.role == "admin"
    assert admin.is_active is True
    assert admin.cognito_sub is None


def test_pharmaceutical_assigns_the_pharmaceutical_knowledge_base(
    client: TestClient,
) -> None:
    session_id = start(client)

    response = client.post(
        "/api/v1/onboarding/message",
        json={"session_id": session_id, "message": "South Lab, pharmaceutical"},
    )

    assert response.status_code == 200
    assert response.json()["knowledge_base_ids"] == PHARMACEUTICAL_BASES


def test_a_completed_session_does_not_create_another_tenant(
    client: TestClient,
    db: Session,
) -> None:
    session_id = start(client)
    client.post(
        "/api/v1/onboarding/message",
        json={"session_id": session_id, "message": "North Plant, automotive"},
    )
    client.post(
        "/api/v1/onboarding/message",
        json={"session_id": session_id, "message": "Ada Lovelace, ada@north.example"},
    )

    response = client.post(
        "/api/v1/onboarding/message",
        json={"session_id": session_id, "message": "Ada Lovelace, ada@north.example"},
    )

    assert response.status_code == 200
    assert response.json()["admin_created"] is True
    assert db.query(Tenant).count() == 1
    assert db.query(User).count() == 1


def test_an_existing_email_is_rejected(client: TestClient, db: Session) -> None:
    taken = Tenant(name="Existing", industry="automotive", is_active=True)
    db.add(taken)
    db.flush()
    db.add(
        User(
            tenant_id=taken.id,
            email="ada@north.example",
            full_name="Ada Lovelace",
            role="auditee",
            is_active=True,
        )
    )
    db.commit()
    session_id = start(client)
    client.post(
        "/api/v1/onboarding/message",
        json={"session_id": session_id, "message": "North Plant, automotive"},
    )

    response = client.post(
        "/api/v1/onboarding/message",
        json={"session_id": session_id, "message": "Ada Lovelace, ada@north.example"},
    )

    assert response.status_code == 409
    assert db.query(Tenant).count() == 1
