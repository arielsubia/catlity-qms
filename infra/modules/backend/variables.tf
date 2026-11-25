variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region for the cluster, repository, and log group"
  type        = string
}

variable "public_subnet_ids" {
  description = "Public subnet IDs where the Fargate task receives a public IP"
  type        = list(string)
}

variable "ecs_security_group_id" {
  description = "Security group that allows TCP 8000 to the task"
  type        = string
}

variable "desired_count" {
  description = "Tasks to keep running. Zero stops Fargate and the public IPv4 charge."
  type        = number
}

variable "github_oidc_subject" {
  description = "Exact GitHub OIDC sub allowed to assume the deploy role. This repository uses immutable subjects, so the claim includes the owner id and the repository id."
  type        = string
}

variable "deployer_user_name" {
  description = "IAM user that applies the stack and joins the deploy group"
  type        = string
}

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
}
