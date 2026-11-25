variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "catlity-qms"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "db_username" {
  description = "Master username for the RDS instance"
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "Master password for the RDS instance"
  type        = string
  sensitive   = true
}

variable "budget_alert_email" {
  description = "Email address for budget alert notifications"
  type        = string
}

variable "ses_sender_email" {
  description = "Email address SES verifies as the sandbox sender"
  type        = string
}

variable "cognito_callback_urls" {
  description = "Allowed OAuth callback URLs for the Cognito app client"
  type        = list(string)
  default     = ["http://localhost:5173/"]
}

variable "cognito_logout_urls" {
  description = "Allowed OAuth logout URLs for the Cognito app client"
  type        = list(string)
  default     = ["http://localhost:5173/"]
}

variable "enable_nat" {
  description = "Create one NAT Gateway and a private default route. Keep false outside a short tutor demo."
  type        = bool
  default     = false
}

variable "backend_desired_count" {
  description = "Backend tasks to keep running. Use 0 to stop the Fargate Spot and public IPv4 charges."
  type        = number
  default     = 1
}

variable "github_oidc_subject" {
  description = "Exact GitHub OIDC sub allowed to deploy the backend. Immutable subjects include the owner id and the repository id."
  type        = string
  default     = "repo:arielsubia@191406855/catlity-qms@1341227643:ref:refs/heads/main"
}

variable "deployer_user_name" {
  description = "IAM user that applies this stack and joins the backend deploy group"
  type        = string
  default     = "devops-ariel"
}

variable "frontend_domain_name" {
  description = "Optional hostname for the frontend distribution. Empty uses the CloudFront default hostname. A later value updates the same distribution and does not replace the bucket."
  type        = string
  default     = ""
}

variable "frontend_acm_certificate_arn" {
  description = "Optional ACM certificate ARN in us-east-1 for frontend_domain_name. Empty uses the CloudFront default certificate."
  type        = string
  default     = ""
}
