"""Tests for finding-assignment mail, overdue reminders, and delivery status."""

from __future__ import annotations

import importlib.util
import json
import time
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from jose import jwk
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.models.user import User
from app.services.notification_status import notification_key, status_for_event
from app.services.notifications import NotificationService
from tests.test_audits import _auth, _create_audit, _create_tenant
from tests.test_auth import make_token


@pytest.fixture(scope="module")
def rsa_keypair() -> dict[str, Any]:
    """RSA keypair used to sign notification tokens in this module."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_jwk = jwk.construct(
        private.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode(),
        algorithm="RS256",
    ).to_dict()
    public_jwk["kid"] = "test-key-notifications"
    public_jwk["alg"] = "RS256"
    public_jwk["use"] = "sig"
    return {"private_pem": private_pem, "public_jwk": public_jwk}


@pytest.fixture(autouse=True)
def configure_cognito(
    rsa_keypair: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Point settings at a fake pool and preload the JWKS cache."""
    monkeypatch.setattr(settings, "cognito_user_pool_id", "us-east-1_test", raising=False)
    monkeypatch.setattr(
        settings, "cognito_app_client_id", "test-client-id", raising=False
    )
    monkeypatch.setattr(settings, "aws_region", "us-east-1", raising=False)
    kid = rsa_keypair["public_jwk"]["kid"]
    security._jwks_cache._keys = {kid: rsa_keypair["public_jwk"]}
    security._jwks_cache._fetched_at = time.monotonic()


def _token(
    rsa_keypair: dict[str, Any],
    tenant_id: str,
    role: str = "auditor",
    sub: str = "user-sub-123",
) -> str:
    return make_token(rsa_keypair, tenant_id=tenant_id, role=role, sub=sub)


class FakeSes:
    """SES stand-in. The first ``failures`` calls raise Throttling."""

    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.calls: list[dict[str, Any]] = []

    def send_templated_email(self, **kwargs: Any) -> dict[str, str]:
        self.calls.append(kwargs)
        if self.failures:
            self.failures -= 1
            raise ClientError(
                {"Error": {"Code": "Throttling", "Message": "slow down"}},
                "SendTemplatedEmail",
            )
        return {"MessageId": "ses-msg-1"}


class FakeDynamo:
    """In-memory DynamoDB client for the notification table."""

    def __init__(self) -> None:
        self.items: dict[tuple[str, str], dict[str, Any]] = {}

    def put_item(self, TableName: str, Item: dict[str, Any]) -> None:
        key = (Item["tenant_id"]["S"], Item["notification_id"]["S"])
        self.items[key] = dict(Item)

    def query(self, TableName: str, **kwargs: Any) -> dict[str, list[dict[str, Any]]]:
        tenant = kwargs["ExpressionAttributeValues"][":tenant_id"]["S"]
        items = [item for (item_tenant, _), item in self.items.items() if item_tenant == tenant]
        return {"Items": items}

    def update_item(self, TableName: str, Key: dict[str, Any], **kwargs: Any) -> None:
        key = (Key["tenant_id"]["S"], Key["notification_id"]["S"])
        if key not in self.items:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": "missing"}},
                "UpdateItem",
            )
        self.items[key]["status"] = kwargs["ExpressionAttributeValues"][":status"]


def _service(
    failures: int = 0, today: date = date(2026, 11, 15)
) -> tuple[NotificationService, FakeSes, FakeDynamo, list[float]]:
    ses = FakeSes(failures)
    dynamo = FakeDynamo()
    slept: list[float] = []
    service = NotificationService(
        ses_client=ses,
        dynamodb_client=dynamo,
        sleep=slept.append,
        today=today,
    )
    return service, ses, dynamo, slept


def _auditee(db: Session, tenant_id: str, email: str = "auditee@example.com") -> User:
    user = User(
        tenant_id=tenant_id,
        cognito_sub="auditee-sub",
        email=email,
        full_name="Ada Auditee",
        role="auditee",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _delivery(tenant_id: str, notification_id: str, event_type: str = "Delivery") -> dict:
    return {
        "eventType": event_type,
        "mail": {
            "messageId": "ses-msg-1",
            "tags": {
                "tenant_id": [tenant_id],
                "notification_id": [notification_id],
            },
        },
    }


def test_finding_email_retries_then_records_sent() -> None:
    service, ses, dynamo, slept = _service(failures=3)
    notification_id = service.send_finding_assigned(
        tenant_id="tenant-1",
        finding_id="finding-1",
        recipient_email="auditee@example.com",
        recipient_name="Ada Auditee",
        finding_title="Gauge out of tolerance",
        audit_name="Process audit",
    )
    assert slept == [1, 2, 4]
    assert len(ses.calls) == 4
    call = ses.calls[-1]
    assert call["Template"] == "finding-assigned"
    assert call["Destination"]["ToAddresses"] == ["auditee@example.com"]
    assert call["Source"] == "arielmsubia@gmail.com"
    assert call["ConfigurationSetName"] == "catlity-qms-dev-notifications"
    tags = {tag["Name"]: tag["Value"] for tag in call["Tags"]}
    assert tags["tenant_id"] == "tenant-1"
    assert tags["notification_id"] == notification_id
    item = dynamo.items[("tenant-1", notification_id)]
    assert item["status"]["S"] == "sent"
    assert item["ses_message_id"]["S"] == "ses-msg-1"
    assert item["kind"]["S"] == "finding_assigned"


def test_exhausted_retries_record_failed() -> None:
    service, _ses, dynamo, slept = _service(failures=4)
    notification_id = service.send_finding_assigned(
        tenant_id="tenant-1",
        finding_id="finding-1",
        recipient_email="auditee@example.com",
        recipient_name="Ada Auditee",
        finding_title="Gauge",
        audit_name="Process audit",
    )
    assert slept == [1, 2, 4]
    item = dynamo.items[("tenant-1", notification_id)]
    assert item["status"]["S"] == "failed"
    assert item["error"]["S"] == "Throttling"
    assert "ses_message_id" not in item


def test_delivery_event_updates_sent_row() -> None:
    service, _ses, dynamo, _slept = _service()
    notification_id = service.send_finding_assigned(
        tenant_id="tenant-1",
        finding_id="finding-1",
        recipient_email="auditee@example.com",
        recipient_name="Ada",
        finding_title="Gauge",
        audit_name="Audit",
    )
    assert service.record_delivery(_delivery("tenant-1", notification_id)) == "delivered"
    assert dynamo.items[("tenant-1", notification_id)]["status"]["S"] == "delivered"
    assert service.record_delivery(_delivery("tenant-1", notification_id, "Bounce")) == "failed"
    assert dynamo.items[("tenant-1", notification_id)]["status"]["S"] == "failed"
    assert service.record_delivery({"eventType": "Open"}) == "ignored"
    assert service.record_delivery(_delivery("tenant-1", "missing")) == "missing"


def test_create_finding_with_assignee_sends_email(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, ses, dynamo, _slept = _service()
    monkeypatch.setattr(
        "app.api.v1.findings.get_notification_service", lambda: service
    )
    tenant_id = _create_tenant(client, "Notify Findings")
    auditee = _auditee(db, tenant_id)
    token = _token(rsa_keypair, tenant_id)
    audit = _create_audit(client, token, title="Process audit")
    response = client.post(
        f"/api/v1/audits/{audit['id']}/findings",
        json={"title": "Gauge out of tolerance", "assignee_id": auditee.id},
        headers=_auth(token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["assignee_id"] == auditee.id
    assert body["status"] == "open"
    assert len(ses.calls) == 1
    template_data = json.loads(ses.calls[0]["TemplateData"])
    assert template_data["recipient_name"] == "Ada Auditee"
    assert template_data["finding_title"] == "Gauge out of tolerance"
    assert template_data["audit_name"] == "Process audit"
    item = next(iter(dynamo.items.values()))
    assert item["status"]["S"] == "sent"
    assert item["recipient_email"]["S"] == "auditee@example.com"


def test_create_finding_keeps_row_when_mail_record_fails(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Broken:
        def send_finding_assigned(self, **kwargs: Any) -> str:
            raise RuntimeError("dynamo down")

    monkeypatch.setattr("app.api.v1.findings.get_notification_service", lambda: Broken())
    tenant_id = _create_tenant(client, "Mail Failure Org")
    auditee = _auditee(db, tenant_id)
    token = _token(rsa_keypair, tenant_id)
    audit = _create_audit(client, token)
    response = client.post(
        f"/api/v1/audits/{audit['id']}/findings",
        json={"title": "Still stored", "assignee_id": auditee.id},
        headers=_auth(token),
    )
    assert response.status_code == 201
    assert response.json()["assignee_id"] == auditee.id


def test_unknown_assignee_returns_422(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "Bad Assignee")
    token = _token(rsa_keypair, tenant_id)
    audit = _create_audit(client, token)
    response = client.post(
        f"/api/v1/audits/{audit['id']}/findings",
        json={"title": "No such person", "assignee_id": "missing-user"},
        headers=_auth(token),
    )
    assert response.status_code == 422


def test_overdue_reminder_goes_to_responsible_and_is_not_repeated(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, ses, _dynamo, _slept = _service(today=date(2026, 11, 15))
    monkeypatch.setattr(
        "app.api.v1.notifications.get_notification_service", lambda: service
    )
    monkeypatch.setattr("app.api.v1.findings.get_notification_service", lambda: service)
    tenant_id = _create_tenant(client, "Overdue Org")
    auditee = _auditee(db, tenant_id, email="owner@example.com")
    auditor = _token(rsa_keypair, tenant_id, role="auditor", sub="auditor-sub")
    admin = _token(rsa_keypair, tenant_id, role="admin", sub="admin-sub")
    audit = _create_audit(client, auditor)
    finding = client.post(
        f"/api/v1/audits/{audit['id']}/findings",
        json={"title": "Late record", "assignee_id": auditee.id},
        headers=_auth(auditor),
    )
    assert finding.status_code == 201
    created = client.post(
        f"/api/v1/findings/{finding.json()['id']}/corrective-actions",
        json={
            "description": "Replace the record",
            "due_date": "2026-11-01",
            "responsible_id": auditee.id,
        },
        headers=_auth(admin),
    )
    assert created.status_code == 201
    assert created.json()["responsible_id"] == auditee.id

    first = client.post(
        "/api/v1/notifications/overdue-reminders", headers=_auth(admin)
    )
    assert first.status_code == 200
    assert first.json() == {"sent": 1, "failed": 0, "skipped": 0}
    reminder = ses.calls[-1]
    assert reminder["Template"] == "corrective-action-overdue"
    assert reminder["Destination"]["ToAddresses"] == ["owner@example.com"]
    assert json.loads(reminder["TemplateData"])["due_date"] == "2026-11-01"

    second = client.post(
        "/api/v1/notifications/overdue-reminders", headers=_auth(admin)
    )
    assert second.status_code == 200
    assert second.json() == {"sent": 0, "failed": 0, "skipped": 1}
    assert len(ses.calls) == 2


def test_overdue_without_responsible_uses_the_finding_assignee(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, ses, _dynamo, _slept = _service(today=date(2026, 11, 15))
    monkeypatch.setattr(
        "app.api.v1.notifications.get_notification_service", lambda: service
    )
    monkeypatch.setattr("app.api.v1.findings.get_notification_service", lambda: service)
    tenant_id = _create_tenant(client, "Fallback Org")
    auditee = _auditee(db, tenant_id, email="fallback@example.com")
    auditor = _token(rsa_keypair, tenant_id, role="auditor")
    admin = _token(rsa_keypair, tenant_id, role="admin", sub="admin-sub")
    audit = _create_audit(client, auditor)
    finding = client.post(
        f"/api/v1/audits/{audit['id']}/findings",
        json={"title": "Open item", "assignee_id": auditee.id},
        headers=_auth(auditor),
    )
    action = client.post(
        f"/api/v1/findings/{finding.json()['id']}/corrective-actions",
        json={"description": "Close the gap", "due_date": "2026-11-14"},
        headers=_auth(admin),
    )
    assert action.status_code == 201
    response = client.post(
        "/api/v1/notifications/overdue-reminders", headers=_auth(admin)
    )
    assert response.json()["sent"] == 1
    assert ses.calls[-1]["Destination"]["ToAddresses"] == ["fallback@example.com"]


def test_future_and_completed_actions_are_skipped(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, ses, _dynamo, _slept = _service(today=date(2026, 11, 15))
    monkeypatch.setattr(
        "app.api.v1.notifications.get_notification_service", lambda: service
    )
    tenant_id = _create_tenant(client, "Not Due Org")
    auditee = _auditee(db, tenant_id)
    admin = _token(rsa_keypair, tenant_id, role="admin")
    auditor = _token(rsa_keypair, tenant_id, role="auditor", sub="auditor-sub")
    audit = _create_audit(client, auditor)
    finding_id = client.post(
        f"/api/v1/audits/{audit['id']}/findings",
        json={"title": "Scheduled"},
        headers=_auth(auditor),
    ).json()["id"]
    client.post(
        f"/api/v1/findings/{finding_id}/corrective-actions",
        json={
            "description": "Still in the future",
            "due_date": "2026-12-01",
            "responsible_id": auditee.id,
        },
        headers=_auth(admin),
    )
    client.post(
        f"/api/v1/findings/{finding_id}/corrective-actions",
        json={
            "description": "Already closed",
            "due_date": "2026-11-01",
            "completion_date": "2026-11-10",
            "responsible_id": auditee.id,
        },
        headers=_auth(admin),
    )
    response = client.post(
        "/api/v1/notifications/overdue-reminders", headers=_auth(admin)
    )
    assert response.json() == {"sent": 0, "failed": 0, "skipped": 0}
    assert ses.calls == []


def test_overdue_route_rejects_non_admin(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "Auditor Reminder")
    token = _token(rsa_keypair, tenant_id, role="auditor")
    response = client.post(
        "/api/v1/notifications/overdue-reminders", headers=_auth(token)
    )
    assert response.status_code == 403


def test_unknown_responsible_returns_422(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "Bad Responsible")
    admin = _token(rsa_keypair, tenant_id, role="admin")
    auditor = _token(rsa_keypair, tenant_id, role="auditor", sub="auditor-sub")
    audit = _create_audit(client, auditor)
    finding_id = client.post(
        f"/api/v1/audits/{audit['id']}/findings",
        json={"title": "Unowned"},
        headers=_auth(auditor),
    ).json()["id"]
    response = client.post(
        f"/api/v1/findings/{finding_id}/corrective-actions",
        json={"description": "Nobody", "responsible_id": "missing-user"},
        headers=_auth(admin),
    )
    assert response.status_code == 422


def _load_handler() -> Any:
    path = (
        Path(__file__).resolve().parents[2]
        / "infra"
        / "modules"
        / "notifications"
        / "events"
        / "handler.py"
    )
    spec = importlib.util.spec_from_file_location("notification_delivery_handler", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lambda_mapping_matches_the_api_and_updates_the_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handler = _load_handler()
    message = _delivery("tenant-1", "note-1", "Complaint")
    assert handler.status_for_event(message) == status_for_event(message) == "failed"
    assert handler.notification_key(message) == notification_key(message)
    assert handler.STATUS_BY_EVENT == {
        "Delivery": "delivered",
        "Bounce": "failed",
        "Complaint": "failed",
        "Reject": "failed",
    }
    dynamo = FakeDynamo()
    dynamo.put_item(
        TableName="notifications",
        Item={
            "tenant_id": {"S": "tenant-1"},
            "notification_id": {"S": "note-1"},
            "status": {"S": "sent"},
        },
    )
    monkeypatch.setenv("NOTIFICATIONS_TABLE_NAME", "catlity-qms-dev-notifications")
    result = handler.handler(
        {"Records": [{"Sns": {"Message": json.dumps(message)}}]},
        None,
        dynamodb=dynamo,
    )
    assert result == {"updated": 1}
    assert dynamo.items[("tenant-1", "note-1")]["status"]["S"] == "failed"
