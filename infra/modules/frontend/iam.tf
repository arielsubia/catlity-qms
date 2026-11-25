data "aws_caller_identity" "current" {}

# Created by module.backend. A second provider for the same issuer is rejected.
data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

locals {
  account_id       = data.aws_caller_identity.current.account_id
  bucket_arn       = "arn:aws:s3:::${local.bucket_name}"
  deploy_role_name = "${var.project_name}-${var.environment}-github-frontend-deploy"
  deploy_role_arn  = "arn:aws:iam::${local.account_id}:role/${local.deploy_role_name}"
  distribution_arn = aws_cloudfront_distribution.frontend.arn
}

# --- GitHub Actions, main branch only ---

resource "aws_iam_role" "github_deploy" {
  name = local.deploy_role_name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Federated = data.aws_iam_openid_connect_provider.github.arn }
        Action    = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
            "token.actions.githubusercontent.com:sub" = var.github_oidc_subject
          }
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Name = local.deploy_role_name
  })
}

resource "aws_iam_role_policy" "github_deploy" {
  name = local.deploy_role_name
  role = aws_iam_role.github_deploy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListFrontendBucket"
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:GetBucketLocation"]
        Resource = local.bucket_arn
      },
      {
        Sid    = "SyncFrontendObjects"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:AbortMultipartUpload",
        ]
        Resource = "${local.bucket_arn}/*"
      },
      {
        # ListDistributions does not accept a distribution ARN.
        Sid      = "FindDistribution"
        Effect   = "Allow"
        Action   = ["cloudfront:ListDistributions"]
        Resource = "*"
      },
      {
        Sid    = "InvalidateFrontend"
        Effect = "Allow"
        Action = [
          "cloudfront:CreateInvalidation",
          "cloudfront:GetInvalidation",
          "cloudfront:ListInvalidations",
        ]
        Resource = local.distribution_arn
      }
    ]
  })
}

# --- devops-ariel is already at the managed-policy limit, so this is a group ---

# IAM groups cannot be tagged. The role, the bucket, and the distribution carry common_tags.
resource "aws_iam_group" "deploy" {
  name = "${var.project_name}-frontend-deploy"
}

resource "aws_iam_group_policy" "deploy" {
  name  = "${var.project_name}-frontend-deploy"
  group = aws_iam_group.deploy.name

  # ARNs are built from the names so this policy can be applied before the
  # bucket and the distribution exist. CloudFront create and list actions
  # have no distribution id yet, so those stay on "*".
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "FrontendBucket"
        Effect = "Allow"
        Action = [
          "s3:CreateBucket",
          "s3:DeleteBucket",
          "s3:ListBucket",
          "s3:GetBucketLocation",
          "s3:GetBucketPolicy",
          "s3:PutBucketPolicy",
          "s3:DeleteBucketPolicy",
          "s3:GetBucketPolicyStatus",
          "s3:GetEncryptionConfiguration",
          "s3:PutEncryptionConfiguration",
          "s3:GetBucketPublicAccessBlock",
          "s3:PutBucketPublicAccessBlock",
          "s3:GetBucketOwnershipControls",
          "s3:PutBucketOwnershipControls",
          "s3:GetBucketTagging",
          "s3:PutBucketTagging",
          "s3:GetBucketVersioning",
          "s3:GetBucketAcl",
          "s3:GetBucketCors",
          "s3:GetBucketWebsite",
          "s3:GetBucketLogging",
          "s3:GetAccelerateConfiguration",
          "s3:GetBucketRequestPayment",
          "s3:GetLifecycleConfiguration",
          "s3:GetReplicationConfiguration",
          "s3:GetBucketObjectLockConfiguration",
          "s3:GetBucketNotification",
        ]
        Resource = [
          local.bucket_arn,
          "${local.bucket_arn}/*",
        ]
      },
      {
        Sid    = "FrontendCloudFront"
        Effect = "Allow"
        Action = [
          "cloudfront:CreateDistribution",
          "cloudfront:GetDistribution",
          "cloudfront:GetDistributionConfig",
          "cloudfront:UpdateDistribution",
          "cloudfront:DeleteDistribution",
          "cloudfront:ListDistributions",
          "cloudfront:TagResource",
          "cloudfront:UntagResource",
          "cloudfront:ListTagsForResource",
          "cloudfront:CreateOriginAccessControl",
          "cloudfront:GetOriginAccessControl",
          "cloudfront:UpdateOriginAccessControl",
          "cloudfront:DeleteOriginAccessControl",
          "cloudfront:ListOriginAccessControls",
          "cloudfront:GetCachePolicy",
          "cloudfront:ListCachePolicies",
        ]
        Resource = "*"
      },
      {
        Sid    = "FrontendDeployRole"
        Effect = "Allow"
        Action = [
          "iam:GetRole",
          "iam:CreateRole",
          "iam:DeleteRole",
          "iam:UpdateAssumeRolePolicy",
          "iam:TagRole",
          "iam:UntagRole",
          "iam:ListRoleTags",
          "iam:ListRolePolicies",
          "iam:ListAttachedRolePolicies",
          "iam:GetRolePolicy",
          "iam:PutRolePolicy",
          "iam:DeleteRolePolicy",
        ]
        Resource = local.deploy_role_arn
      },
      {
        Sid      = "ReadGitHubOidcProvider"
        Effect   = "Allow"
        Action   = ["iam:GetOpenIDConnectProvider"]
        Resource = data.aws_iam_openid_connect_provider.github.arn
      }
    ]
  })
}

resource "aws_iam_group_membership" "deploy" {
  name  = "${var.project_name}-frontend-deploy"
  users = [var.deployer_user_name]
  group = aws_iam_group.deploy.name
}
