from pydantic import BaseModel, Field

MAX_FILE_BYTES = 25 * 1024 * 1024


class UploadUrlRequest(BaseModel):
    """File the client intends to upload directly to S3."""

    file_name: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=1, max_length=255)
    file_size: int = Field(..., gt=0, le=MAX_FILE_BYTES)


class UploadUrlResponse(BaseModel):
    """Presigned PUT and the headers the client must send with it."""

    evidence_id: str
    upload_url: str
    expires_in: int
    headers: dict[str, str]
    s3_key: str


class DownloadUrlResponse(BaseModel):
    """Presigned GET for one uploaded object of the caller's tenant."""

    evidence_id: str
    download_url: str
    expires_in: int
    file_name: str
    content_type: str


class EvidenceMetadata(BaseModel):
    """Evidence metadata stored in DynamoDB."""

    tenant_id: str
    evidence_id: str
    file_name: str
    content_type: str
    file_size: int
    s3_key: str
    status: str
    uploaded_by: str
    uploaded_at: str | None = None
