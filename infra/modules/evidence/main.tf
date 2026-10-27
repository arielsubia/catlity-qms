data "aws_caller_identity" "current" {}

data "aws_iam_session_context" "current" {
  arn = data.aws_caller_identity.current.arn
}

locals {
  bucket_name = "${var.project_name}-${var.environment}-evidence"
  table_name  = "${var.project_name}-${var.environment}-evidence"

  # Reserved name. The ECS task role is created with the cluster, not here.
  backend_task_role_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${var.project_name}-${var.environment}-backend-task"
  account_root_arn      = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
}

# --- Evidence bucket ---

resource "aws_s3_bucket" "evidence" {
  bucket = local.bucket_name

  tags = merge(var.tags, {
    Name = local.bucket_name
  })
}

resource "aws_s3_bucket_versioning" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  rule {
    id     = "evidence-intelligent-tiering"
    status = "Enabled"

    filter {}

    # Intelligent-Tiering is an object storage class. Day 0 is valid for this class.
    transition {
      days          = 0
      storage_class = "INTELLIGENT_TIERING"
    }

    noncurrent_version_expiration {
      noncurrent_days = 90
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

data "aws_iam_policy_document" "evidence" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.evidence.arn,
      "${aws_s3_bucket.evidence.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  statement {
    sid     = "DenyAnonymous"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.evidence.arn,
      "${aws_s3_bucket.evidence.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Null"
      variable = "aws:PrincipalArn"
      values   = ["true"]
    }
  }

  statement {
    sid     = "DenyExceptBackendAndBreakGlass"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.evidence.arn,
      "${aws_s3_bucket.evidence.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "ArnNotEquals"
      variable = "aws:PrincipalArn"
      values = [
        local.backend_task_role_arn,
        data.aws_iam_session_context.current.issuer_arn,
        local.account_root_arn,
      ]
    }
  }
}

resource "aws_s3_bucket_policy" "evidence" {
  bucket = aws_s3_bucket.evidence.id
  policy = data.aws_iam_policy_document.evidence.json

  depends_on = [
    aws_s3_bucket_public_access_block.evidence,
    aws_s3_bucket_ownership_controls.evidence,
  ]
}

# --- Evidence metadata ---

resource "aws_dynamodb_table" "evidence" {
  name         = local.table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "tenant_id"
  range_key    = "evidence_id"

  attribute {
    name = "tenant_id"
    type = "S"
  }

  attribute {
    name = "evidence_id"
    type = "S"
  }

  # AWS owned key is the default and has no monthly CMK charge.
  point_in_time_recovery {
    enabled = false
  }

  deletion_protection_enabled = false

  tags = merge(var.tags, {
    Name = local.table_name
  })
}
