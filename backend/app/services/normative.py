"""Normative questions against the study notes already indexed in Bedrock.

The API chooses the knowledge bases from the tenant industry and retrieves
passages itself. The harness call for that request carries an empty tool list:
the gateway Lambda accepts every corpus, so the model must not be able to open it.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any, Protocol

import boto3
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.tenant import Tenant

MAX_QUERIES_PER_MINUTE = 10
WINDOW_SECONDS = 60.0
RETRIEVE_RESULTS = 4
NOTES_DO_NOT_COVER = "The study notes do not cover this question."
ANSWER_PROMPT = (
    "You are Normative Advisor for Catlity QMS. "
    "Answer only from the study-note passages in the user message. "
    "Cite the file name of each note you use. "
    "The notes are original study summaries. "
    "They are not the official text of ISO 9001, IATF 16949, or GMP. "
    "If the notes do not cover the question, say so. "
    "Do not invent clause numbers or requirements."
)


class TenantNotFound(Exception):
    """The token tenant has no row in the local database."""


class UnsupportedIndustry(Exception):
    """The tenant industry is outside the two corpora this advisor can read."""


class QueryRateLimited(Exception):
    """This user already sent 10 queries in the current minute."""


class NormativeUpstreamError(Exception):
    """Bedrock Retrieve or the harness invocation failed."""


@dataclass(frozen=True)
class Passage:
    """One chunk returned by Retrieve, labeled with its file name."""

    text: str
    document: str


@dataclass(frozen=True)
class NormativeReference:
    document: str
    section: str


@dataclass(frozen=True)
class NormativeAnswer:
    answer: str
    references: list[NormativeReference]


class NormativeBackend(Protocol):
    """The two AWS calls the query path is allowed to make."""

    def retrieve(self, knowledge_base_id: str, query: str) -> list[Passage]:
        """Return passages from one knowledge base."""

    def complete(self, *, user_id: str, question: str, passages: list[Passage]) -> str:
        """Ask the harness to answer from passages the API already selected."""


class QueryRateLimiter:
    """In-process counter of queries per user.

    One local API process is the deployment today. The counter is keyed by the
    Cognito ``sub``. It is not shared across processes.
    """

    def __init__(
        self,
        max_queries: int = MAX_QUERIES_PER_MINUTE,
        window_seconds: float = WINDOW_SECONDS,
    ) -> None:
        self._max_queries = max_queries
        self._window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, user_id: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits.setdefault(user_id, deque())
            cutoff = now - self._window_seconds
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self._max_queries:
                return False
            hits.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


rate_limiter = QueryRateLimiter()


def document_name(uri: str) -> str:
    """Return the file name from an S3 URI."""
    cleaned = uri.split("?", 1)[0].rstrip("/")
    name = cleaned.rsplit("/", 1)[-1]
    return name or "study-note"


def knowledge_base_ids_for(industry: str) -> list[str]:
    """Return common plus the industry corpus, in that order."""
    specific = {
        "automotive": settings.normative_kb_automotive_id,
        "pharmaceutical": settings.normative_kb_pharmaceutical_id,
    }.get(industry.strip().lower())
    if specific is None:
        raise UnsupportedIndustry(industry)
    return [settings.normative_kb_common_id, specific]


def references_from(passages: list[Passage]) -> list[NormativeReference]:
    """One reference per file. The file name fills document and section."""
    seen: dict[str, NormativeReference] = {}
    for passage in passages:
        if passage.document not in seen:
            seen[passage.document] = NormativeReference(
                document=passage.document,
                section=passage.document,
            )
    return list(seen.values())


def passages_message(question: str, passages: list[Passage]) -> str:
    blocks = [f"Question:\n{question}", "Passages:"]
    for passage in passages:
        blocks.append(f"File: {passage.document}\n{passage.text}")
    return "\n\n".join(blocks)


def collect_harness_text(events: Iterable[dict[str, Any]]) -> str:
    """Join the text deltas of one harness stream."""
    parts: list[str] = []
    for event in events:
        if "contentBlockDelta" in event:
            text = event["contentBlockDelta"].get("delta", {}).get("text")
            if text:
                parts.append(text)
            continue
        for key in ("runtimeClientError", "validationException", "internalServerException"):
            if key in event:
                message = event[key].get("message", key)
                raise NormativeUpstreamError(message)
    answer = "".join(parts).strip()
    if not answer:
        raise NormativeUpstreamError("The harness returned an empty answer")
    return answer


def answer_question(
    db: Session,
    backend: NormativeBackend,
    *,
    tenant_id: str,
    user_id: str,
    question: str,
    limiter: QueryRateLimiter | None = None,
) -> NormativeAnswer:
    """Answer one question from the knowledge bases of the tenant industry."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant is None:
        raise TenantNotFound(tenant_id)

    knowledge_base_ids = knowledge_base_ids_for(tenant.industry)
    active_limiter = rate_limiter if limiter is None else limiter
    if not active_limiter.allow(user_id):
        raise QueryRateLimited(user_id)

    passages: list[Passage] = []
    for knowledge_base_id in knowledge_base_ids:
        passages.extend(backend.retrieve(knowledge_base_id, question))

    if not passages:
        return NormativeAnswer(answer=NOTES_DO_NOT_COVER, references=[])

    answer = backend.complete(user_id=user_id, question=question, passages=passages)
    return NormativeAnswer(answer=answer, references=references_from(passages))


class BotoNormativeBackend:
    """Retrieve with the agent runtime, then invoke the existing harness."""

    def __init__(self, runtime: Any | None = None, harness: Any | None = None) -> None:
        self._runtime = runtime or boto3.client(
            "bedrock-agent-runtime",
            region_name=settings.aws_region,
        )
        self._harness = harness or boto3.client(
            "bedrock-agentcore",
            region_name=settings.aws_region,
        )

    def retrieve(self, knowledge_base_id: str, query: str) -> list[Passage]:
        try:
            response = self._runtime.retrieve(
                knowledgeBaseId=knowledge_base_id,
                retrievalQuery={"text": query},
                retrievalConfiguration={
                    "vectorSearchConfiguration": {"numberOfResults": RETRIEVE_RESULTS}
                },
            )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "RetrieveFailed")
            raise NormativeUpstreamError(code) from exc

        passages: list[Passage] = []
        for item in response.get("retrievalResults", []):
            text = item.get("content", {}).get("text", "").strip()
            if not text:
                continue
            uri = item.get("location", {}).get("s3Location", {}).get("uri", "")
            passages.append(Passage(text=text, document=document_name(uri)))
        return passages

    def complete(self, *, user_id: str, question: str, passages: list[Passage]) -> str:
        # The gateway tool accepts every corpus. This call passes only the
        # passages already retrieved for the tenant and clears the tool list.
        try:
            response = self._harness.invoke_harness(
                harnessArn=settings.normative_harness_arn,
                runtimeSessionId=str(uuid.uuid4()),
                runtimeUserId=user_id or "catlity-user",
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": passages_message(question, passages)}],
                    }
                ],
                systemPrompt=[{"text": ANSWER_PROMPT}],
                tools=[],
                allowedTools=[],
                maxIterations=1,
            )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "InvokeHarnessFailed")
            raise NormativeUpstreamError(code) from exc
        return collect_harness_text(_stream_events(response))


def _stream_events(response: dict[str, Any]) -> Iterator[dict[str, Any]]:
    stream = response.get("stream", ())
    yield from stream


_backend: BotoNormativeBackend | None = None


def get_normative_backend() -> BotoNormativeBackend:
    """FastAPI dependency. Clients are created on first use."""
    global _backend
    if _backend is None:
        _backend = BotoNormativeBackend()
    return _backend
