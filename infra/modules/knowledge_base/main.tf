data "aws_caller_identity" "current" {}

data "aws_iam_session_context" "current" {
  arn = data.aws_caller_identity.current.arn
}

locals {
  bucket_name = "${var.project_name}-${var.environment}-knowledge-base"

  # Reserved name. The Bedrock knowledge base role is created with the agent, not here.
  bedrock_kb_role_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${var.project_name}-${var.environment}-bedrock-kb"
  account_root_arn    = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"

  document_root = "${path.module}/../../../knowledge-base"
  document_keys = fileset(local.document_root, "*/*.txt")

  prefixes = [
    "knowledge-base/common/",
    "knowledge-base/automotive/",
    "knowledge-base/pharmaceutical/",
  ]
}

# --- Normative reference bucket ---

resource "aws_s3_bucket" "knowledge_base" {
  bucket = local.bucket_name

  tags = merge(var.tags, {
    Name = local.bucket_name
  })

  lifecycle {
    precondition {
      condition = alltrue([
        for prefix in ["common", "automotive", "pharmaceutical"] :
        length([for key in local.document_keys : key if startswith(key, "${prefix}/")]) >= 3
      ])
      error_message = "knowledge-base/common, automotive, and pharmaceutical each need at least 3 .txt files."
    }
  }
}

resource "aws_s3_bucket_versioning" "knowledge_base" {
  bucket = aws_s3_bucket.knowledge_base.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "knowledge_base" {
  bucket = aws_s3_bucket.knowledge_base.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "knowledge_base" {
  bucket = aws_s3_bucket.knowledge_base.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "knowledge_base" {
  bucket = aws_s3_bucket.knowledge_base.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

data "aws_iam_policy_document" "knowledge_base" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.knowledge_base.arn,
      "${aws_s3_bucket.knowledge_base.arn}/*",
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
      aws_s3_bucket.knowledge_base.arn,
      "${aws_s3_bucket.knowledge_base.arn}/*",
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
    sid     = "DenyExceptKnowledgeBaseAndBreakGlass"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.knowledge_base.arn,
      "${aws_s3_bucket.knowledge_base.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "ArnNotEquals"
      variable = "aws:PrincipalArn"
      values = [
        local.bedrock_kb_role_arn,
        data.aws_iam_session_context.current.issuer_arn,
        local.account_root_arn,
      ]
    }
  }
}

resource "aws_s3_bucket_policy" "knowledge_base" {
  bucket = aws_s3_bucket.knowledge_base.id
  policy = data.aws_iam_policy_document.knowledge_base.json

  depends_on = [
    aws_s3_bucket_public_access_block.knowledge_base,
    aws_s3_bucket_ownership_controls.knowledge_base,
  ]
}

# Study notes from the repository. A changed file uploads a new object version.
resource "aws_s3_object" "document" {
  for_each = local.document_keys

  bucket       = aws_s3_bucket.knowledge_base.id
  key          = "knowledge-base/${each.value}"
  source       = "${local.document_root}/${each.value}"
  source_hash  = filemd5("${local.document_root}/${each.value}")
  content_type = "text/plain; charset=utf-8"

  tags = merge(var.tags, {
    Name = "knowledge-base/${each.value}"
  })

  depends_on = [aws_s3_bucket_policy.knowledge_base]
}
