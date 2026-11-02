variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
}

variable "cors_allowed_origins" {
  description = "Browser origins allowed to upload evidence directly to the bucket"
  type        = list(string)
  default     = ["http://localhost:5173"]
}
