variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region for Bedrock and S3 Vectors"
  type        = string
}

variable "knowledge_base_bucket_arn" {
  description = "ARN of the S3 bucket that holds the normative study notes"
  type        = string
}

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
}
