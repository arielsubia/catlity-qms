variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "domain_name" {
  description = "Optional hostname served by this distribution. Empty keeps the CloudFront default hostname. Setting this later updates the same distribution and does not replace the bucket."
  type        = string
  default     = ""
}

variable "acm_certificate_arn" {
  description = "Optional ACM certificate ARN in us-east-1 for domain_name. Empty uses the certificate CloudFront issues for its default hostname. Set both together when a domain exists."
  type        = string
  default     = ""

  validation {
    condition     = var.acm_certificate_arn == "" || startswith(var.acm_certificate_arn, "arn:aws:acm:us-east-1:")
    error_message = "acm_certificate_arn must be an ACM certificate in us-east-1."
  }
}

variable "github_oidc_subject" {
  description = "Exact GitHub OIDC sub allowed to assume the frontend deploy role. This repository uses immutable subjects, so the claim includes the owner id and the repository id."
  type        = string
}

variable "deployer_user_name" {
  description = "IAM user that applies the stack and joins the frontend deploy group"
  type        = string
}

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
}
