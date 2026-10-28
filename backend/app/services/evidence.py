"""Presigned evidence uploads and their DynamoDB metadata.

The API signs the PUT locally. The file bytes go to S3 from the client.
A confirm call checks the object and then marks the DynamoDB row uploaded.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings
from app.schemas.evidence import MAX_FILE_BYTES

UPLOAD_EXPIRES_IN = 15 * 60
STORAGE_CLASS = "INTELLIGENT_TIERING"

CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}
JPEG_SUFFIXES = {".jpg", ".jpeg"}


class InvalidEvidenceFile(Exception):
    """The requested file type or name is not accepted."""


class EvidenceNotFound(Exception):
    """This tenant has no upload request for the evidence id."""


class EvidenceNotUploaded(Exception):
    """The signed URL was issued, but the object is not in the bucket yet."""


class EvidenceObjectMismatch(Exception):
    """The object in S3 does not match the type or size that was signed."""


@dataclass(frozen=True)
class ObjectHead:
    """Size and type reported by S3 for one object."""

    content_type: str
    content_length: int


@dataclass(frozen=True)
class UploadTicket:
    """What the client needs to perform the PUT."""

    evidence_id: str
    upload_url: str
    expires_in: int
    headers: dict[str, str]
    s3_key: str


class EvidenceStore(Protocol):
    """Persistence and S3 calls used by the upload flow."""

    def put_pending(self, item: dict[str, Any]) -> None:
        """Store a pending upload for one tenant."""

    def get(self, tenant_id: str, evidence_id: str) -> dict[str, Any] | None:
        """Return the metadata row, or None when this tenant has no such id."""

    def mark_uploaded(
        self, tenant_id: str, evidence_id: str, uploaded_at: str
    ) -> dict[str, Any]:
        """Set the row to uploaded and return it."""

    def presign_put(self, *, key: str, content_type: str, file_size: int) -> str:
        """Return a PUT URL that expires in 15 minutes."""

    def head(self, key: str) -> ObjectHead | None:
        """Return the object head, or None when the key is absent."""


class BotoEvidenceStore:
    """S3 and DynamoDB implementation of ``EvidenceStore``."""

    def __init__(
        self,
        *,
        bucket: str,
        table: str,
        region: str,
        s3_client: Any | None = None,
        dynamodb_client: Any | None = None,
    ) -> None:
        self._bucket = bucket
        self._table = table
        self._s3 = s3_client or boto3.client("s3", region_name=region)
        self._dynamodb = dynamodb_client or boto3.client("dynamodb", region_name=region)

    def put_pending(self, item: dict[str, Any]) -> None:
        self._dynamodb.put_item(
            TableName=self._table,
            Item=_to_item(item),
            ConditionExpression="attribute_not_exists(evidence_id)",
        )

    def get(self, tenant_id: str, evidence_id: str) -> dict[str, Any] | None:
        response = self._dynamodb.get_item(
            TableName=self._table,
            Key={
                "tenant_id": {"S": tenant_id},
                "evidence_id": {"S": evidence_id},
            },
        )
        raw = response.get("Item")
        if raw is None:
            return None
        return _from_item(raw)

    def mark_uploaded(
        self, tenant_id: str, evidence_id: str, uploaded_at: str
    ) -> dict[str, Any]:
        response = self._dynamodb.update_item(
            TableName=self._table,
            Key={
                "tenant_id": {"S": tenant_id},
                "evidence_id": {"S": evidence_id},
            },
            UpdateExpression="SET #status = :uploaded, uploaded_at = :at",
            ConditionExpression="#status = :pending",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":uploaded": {"S": "uploaded"},
                ":pending": {"S": "pending"},
                ":at": {"S": uploaded_at},
            },
            ReturnValues="ALL_NEW",
        )
        return _from_item(response["Attributes"])

    def presign_put(self, *, key: str, content_type: str, file_size: int) -> str:
        return self._s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self._bucket,
                "Key": key,
                "ContentType": content_type,
                "ContentLength": file_size,
                "StorageClass": STORAGE_CLASS,
            },
            ExpiresIn=UPLOAD_EXPIRES_IN,
        )

    def head(self, key: str) -> ObjectHead | None:
        try:
            response = self._s3.head_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise
        return ObjectHead(
            content_type=response.get("ContentType", ""),
            content_length=int(response["ContentLength"]),
        )


def create_upload_url(
    store: EvidenceStore,
    *,
    tenant_id: str,
    uploaded_by: str,
    file_name: str,
    content_type: str,
    file_size: int,
) -> UploadTicket:
    """Validate the file, record a pending row, and sign the PUT."""
    safe_name = _clean_file_name(file_name)
    _validate_file(safe_name, content_type, file_size)

    evidence_id = str(uuid4())
    s3_key = f"{tenant_id}/{evidence_id}/{safe_name}"
    store.put_pending(
        {
            "tenant_id": tenant_id,
            "evidence_id": evidence_id,
            "file_name": safe_name,
            "content_type": content_type,
            "file_size": file_size,
            "s3_key": s3_key,
            "status": "pending",
            "uploaded_by": uploaded_by,
            "uploaded_at": None,
        }
    )
    upload_url = store.presign_put(
        key=s3_key, content_type=content_type, file_size=file_size
    )
    return UploadTicket(
        evidence_id=evidence_id,
        upload_url=upload_url,
        expires_in=UPLOAD_EXPIRES_IN,
        headers={
            "Content-Type": content_type,
            "Content-Length": str(file_size),
            "x-amz-storage-class": STORAGE_CLASS,
        },
        s3_key=s3_key,
    )


def confirm_upload(
    store: EvidenceStore, *, tenant_id: str, evidence_id: str
) -> dict[str, Any]:
    """Mark the row uploaded after the object is present and matches the signature."""
    item = store.get(tenant_id, evidence_id)
    if item is None:
        raise EvidenceNotFound("Evidence upload was not requested")
    if item["status"] == "uploaded":
        return item

    head = store.head(item["s3_key"])
    if head is None:
        raise EvidenceNotUploaded("Object is not in the evidence bucket yet")
    if head.content_type != item["content_type"] or head.content_length != item["file_size"]:
        raise EvidenceObjectMismatch(
            "Uploaded object does not match the signed type or size"
        )
    return store.mark_uploaded(tenant_id, evidence_id, datetime.now(UTC).isoformat())


def _clean_file_name(file_name: str) -> str:
    if "/" in file_name or "\\" in file_name or file_name in {".", ".."}:
        raise InvalidEvidenceFile("File name must not include a path")
    return file_name


def _validate_file(file_name: str, content_type: str, file_size: int) -> None:
    if file_size < 1 or file_size > MAX_FILE_BYTES:
        raise InvalidEvidenceFile("File size must be between 1 byte and 25 MB")
    expected = CONTENT_TYPES.get(content_type)
    if expected is None:
        raise InvalidEvidenceFile("File type must be PDF, PNG, JPG, or DOCX")
    suffix = Path(file_name).suffix.lower()
    allowed = JPEG_SUFFIXES if content_type == "image/jpeg" else {expected}
    if suffix not in allowed:
        raise InvalidEvidenceFile("File name extension does not match the content type")


def _to_item(item: dict[str, Any]) -> dict[str, dict[str, str]]:
    mapped: dict[str, dict[str, str]] = {
        "tenant_id": {"S": item["tenant_id"]},
        "evidence_id": {"S": item["evidence_id"]},
        "file_name": {"S": item["file_name"]},
        "content_type": {"S": item["content_type"]},
        "file_size": {"N": str(item["file_size"])},
        "s3_key": {"S": item["s3_key"]},
        "status": {"S": item["status"]},
        "uploaded_by": {"S": item["uploaded_by"]},
    }
    if item.get("uploaded_at"):
        mapped["uploaded_at"] = {"S": item["uploaded_at"]}
    return mapped


def _from_item(item: dict[str, dict[str, str]]) -> dict[str, Any]:
    parsed: dict[str, Any] = {
        "tenant_id": item["tenant_id"]["S"],
        "evidence_id": item["evidence_id"]["S"],
        "file_name": item["file_name"]["S"],
        "content_type": item["content_type"]["S"],
        "file_size": int(item["file_size"]["N"]),
        "s3_key": item["s3_key"]["S"],
        "status": item["status"]["S"],
        "uploaded_by": item["uploaded_by"]["S"],
        "uploaded_at": None,
    }
    if "uploaded_at" in item:
        parsed["uploaded_at"] = item["uploaded_at"]["S"]
    return parsed


@lru_cache(maxsize=1)
def get_store() -> EvidenceStore:
    """Build the store from the process settings. Tests replace this."""
    return BotoEvidenceStore(
        bucket=settings.evidence_bucket_name,
        table=settings.evidence_table_name,
        region=settings.aws_region,
    )
