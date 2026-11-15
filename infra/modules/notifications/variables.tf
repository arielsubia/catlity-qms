variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "tags" {
  description = "Common tags to apply to all resources that support tags"
  type        = map(string)
}

variable "sender_email" {
  description = "Email address SES verifies as the sandbox sender. Dev does not verify a domain."
  type        = string
}
