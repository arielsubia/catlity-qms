"""Onboarding action Lambdas: validation only, with Bedrock mocked for assign_kb."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
from botocore.exceptions import ClientError

HANDLERS = (
    Path(__file__).resolve().parents[2]
    / "infra"
    / "modules"
    / "bedrock"
    / "onboarding"
)

KB_ENV = {
    "KB_COMMON": "OTQJ8TMBNI",
    "KB_AUTOMOTIVE": "QWONN58E2H",
    "KB_PHARMACEUTICAL": "DX3IVAFQ6K",
}


def load_handler(name: str) -> ModuleType:
    path = HANDLERS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"onboarding_{name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


create_tenant = load_handler("create_tenant")
assign_kb = load_handler("assign_kb")
generate_checklists = load_handler("generate_checklists")
create_admin_user = load_handler("create_admin_user")


class FakeKnowledgeBases:
    """Records GetKnowledgeBase calls and can fail one corpus."""

    def __init__(self, failure: ClientError | None = None, fail_on: str | None = None) -> None:
        self.calls: list[str] = []
        self.failure = failure
        self.fail_on = fail_on

    def get_knowledge_base(self, knowledgeBaseId: str) -> dict[str, str]:
        self.calls.append(knowledgeBaseId)
        if self.failure is not None and knowledgeBaseId == self.fail_on:
            raise self.failure
        return {"knowledgeBaseId": knowledgeBaseId}


def client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, "GetKnowledgeBase")


def test_create_tenant_accepts_an_automotive_organization() -> None:
    result = create_tenant.handler(
        {"arguments": {"organization_name": "  North Plant  ", "industry": "automotive"}},
        None,
    )

    assert result == {
        "organization_name": "North Plant",
        "industry": "automotive",
        "status": "pending",
    }


@pytest.mark.parametrize(
    ("payload", "error"),
    [
        ({"organization_name": "  ", "industry": "automotive"}, "organization_name is required."),
        ({"organization_name": "A" * 256, "industry": "automotive"}, "organization_name is too long."),
        ({"organization_name": "North Plant", "industry": "common"}, "industry must be automotive or pharmaceutical."),
        ({"organization_name": "North Plant"}, "industry must be automotive or pharmaceutical."),
    ],
)
def test_create_tenant_rejects_a_bad_organization(payload: dict[str, str], error: str) -> None:
    assert create_tenant.handler(payload, None) == {"error": error}


def _set_kb_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in KB_ENV.items():
        monkeypatch.setenv(name, value)


def test_assign_kb_checks_common_and_the_industry_base(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_kb_env(monkeypatch)
    client = FakeKnowledgeBases()

    result = assign_kb.handler({"industry": "pharmaceutical"}, None, client)

    assert result == {
        "industry": "pharmaceutical",
        "knowledge_base_ids": {
            "common": "OTQJ8TMBNI",
            "pharmaceutical": "DX3IVAFQ6K",
        },
        "status": "assigned",
    }
    assert client.calls == ["OTQJ8TMBNI", "DX3IVAFQ6K"]


def test_assign_kb_returns_the_bedrock_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_kb_env(monkeypatch)
    client = FakeKnowledgeBases(client_error("ResourceNotFoundException"), fail_on="OTQJ8TMBNI")

    result = assign_kb.handler({"industry": "automotive"}, None, client)

    assert result == {"error": "ResourceNotFoundException", "corpus": "common"}
    assert client.calls == ["OTQJ8TMBNI"]


def test_assign_kb_stops_when_ids_are_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in KB_ENV:
        monkeypatch.delenv(name, raising=False)
    client = FakeKnowledgeBases()

    assert assign_kb.handler({"industry": "automotive"}, None, client) == {
        "error": "knowledge base ids are not configured."
    }
    assert client.calls == []


def test_generate_checklists_adds_industry_items_to_the_common_list() -> None:
    result = generate_checklists.handler({"industry": "automotive"}, None)

    assert result["status"] == "pending"
    assert result["industry"] == "automotive"
    keys = [item["key"] for item in result["items"]]
    assert keys == [
        "quality-policy",
        "roles",
        "documents",
        "customer-requirements",
        "process-controls",
    ]


def test_generate_checklists_rejects_an_unknown_industry() -> None:
    assert generate_checklists.handler({"industry": "food"}, None) == {
        "error": "industry must be automotive or pharmaceutical."
    }


def test_create_admin_user_accepts_a_name_and_email() -> None:
    result = create_admin_user.handler(
        {"arguments": {"full_name": " Ada Admin ", "email": "ada@example.com"}},
        None,
    )

    assert result == {
        "full_name": "Ada Admin",
        "email": "ada@example.com",
        "role": "admin",
        "status": "pending",
    }


@pytest.mark.parametrize(
    ("payload", "error"),
    [
        ({"full_name": " ", "email": "ada@example.com"}, "full_name is required."),
        ({"full_name": "Ada", "email": "ada"}, "email is required."),
        ({"full_name": "Ada", "email": "ada @example.com"}, "email is required."),
    ],
)
def test_create_admin_user_rejects_a_bad_admin(payload: dict[str, str], error: str) -> None:
    assert create_admin_user.handler(payload, None) == {"error": error}


def test_handlers_do_not_accept_an_unexpected_shape() -> None:
    assert create_tenant.handler("north", None)["error"] == "organization_name is required."
    assert isinstance(generate_checklists.handler(None, None), dict)
