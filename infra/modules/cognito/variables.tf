variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "callback_urls" {
  description = "Allowed OAuth callback URLs for the app client"
  type        = list(string)
  default     = ["http://localhost:5173/"]
}

variable "logout_urls" {
  description = "Allowed OAuth logout URLs for the app client"
  type        = list(string)
  default     = ["http://localhost:5173/"]
}

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
}
