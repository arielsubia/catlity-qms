"""Return study-note passages from one normative knowledge base."""

import json
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError

_runtime = boto3.client("bedrock-agent-runtime")
_kb_ids = json.loads(os.environ["KB_IDS"])
_MAX_QUERY_LEN = 1000
_TOP_K = 4


def handler(event: dict[str, Any], _context: object) -> dict[str, Any]:
    args = event if isinstance(event, dict) else {}
    nested = args.get("arguments")
    if isinstance(nested, dict):
        args = nested

    corpus = args.get("corpus")
    query = args.get("query")
    if corpus not in _kb_ids:
        return {"error": "corpus must be common, automotive, or pharmaceutical."}
    if not isinstance(query, str) or not query.strip():
        return {"error": "query is required."}
    if len(query) > _MAX_QUERY_LEN:
        return {"error": "query is too long."}

    try:
        response = _runtime.retrieve(
            knowledgeBaseId=_kb_ids[corpus],
            retrievalQuery={"text": query.strip()},
            retrievalConfiguration={
                "vectorSearchConfiguration": {"numberOfResults": _TOP_K}
            },
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "RetrieveFailed")
        return {"error": code}

    passages: list[dict[str, str]] = []
    for item in response.get("retrievalResults", []):
        content = item.get("content", {})
        location = item.get("location", {}).get("s3Location", {})
        passages.append(
            {
                "text": content.get("text", ""),
                "source": location.get("uri", ""),
            }
        )
    return {"corpus": corpus, "passages": passages}
