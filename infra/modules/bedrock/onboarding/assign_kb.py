"""Confirm the existing knowledge bases for one industry.

The ids are the ones already applied. This function reads them. It does not
create a knowledge base.
"""

import os
from collections.abc import Mapping
from typing import Any

import boto3
from botocore.exceptions import ClientError

INDUSTRIES = ("automotive", "pharmaceutical")
ENV_BY_CORPUS = {
    "common": "KB_COMMON",
    "automotive": "KB_AUTOMOTIVE",
    "pharmaceutical": "KB_PHARMACEUTICAL",
}


def arguments(event: object) -> dict[str, Any]:
    if not isinstance(event, dict):
        return {}
    nested = event.get("arguments")
    if isinstance(nested, dict):
        return nested
    return event


def knowledge_base_ids(environment: Mapping[str, str]) -> dict[str, str] | None:
    """Read the three applied ids. Missing configuration returns None."""
    found: dict[str, str] = {}
    for corpus, env_name in ENV_BY_CORPUS.items():
        value = environment.get(env_name, "")
        if not isinstance(value, str) or not value.strip():
            return None
        found[corpus] = value.strip()
    return found


def assign_kb(
    industry: object,
    knowledge_bases: Mapping[str, str],
    client: Any,
) -> dict[str, Any]:
    """Check common and the industry base, then return both ids."""
    if industry not in INDUSTRIES:
        return {"error": "industry must be automotive or pharmaceutical."}
    selected = {
        "common": knowledge_bases["common"],
        industry: knowledge_bases[industry],
    }
    for corpus, knowledge_base_id in selected.items():
        try:
            client.get_knowledge_base(knowledgeBaseId=knowledge_base_id)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "GetKnowledgeBaseFailed")
            return {"error": code, "corpus": corpus}
    return {
        "industry": industry,
        "knowledge_base_ids": selected,
        "status": "assigned",
    }


def handler(
    event: dict[str, Any],
    _context: object,
    client: Any | None = None,
) -> dict[str, Any]:
    ids = knowledge_base_ids(os.environ)
    if ids is None:
        return {"error": "knowledge base ids are not configured."}
    if client is None:
        client = boto3.client("bedrock-agent")
    return assign_kb(arguments(event).get("industry"), ids, client)
