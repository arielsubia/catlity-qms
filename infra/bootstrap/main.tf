locals {
  common_tags = {
    Project     = "catlity-qms"
    Environment = "dev"
    ManagedBy   = "terraform"
    Owner       = "phil-dev"
  }
}

# State bucket for the main stack. This configuration uses a local backend
# because the bucket cannot store the state of its own creation.
resource "aws_s3_bucket" "terraform_state" {
  bucket = "catlity-qms-terraform-state"

  tags = merge(local.common_tags, {
    Name = "catlity-qms-terraform-state"
  })
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}
