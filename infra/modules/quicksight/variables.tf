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

variable "notification_email" {
  description = "Inbox QuickSight uses for account notifications. The console IAM user creates the subscription."
  type        = string
}

variable "vpc_id" {
  description = "VPC that holds the private subnets and the RDS instance"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for the QuickSight VPC connection"
  type        = list(string)
}

variable "rds_security_group_id" {
  description = "Security group of the RDS instance. QuickSight is allowed in on port 5432."
  type        = string
}

variable "rds_host" {
  description = "RDS hostname. The instance has no public IP."
  type        = string
}

variable "rds_port" {
  description = "RDS port"
  type        = number
}

variable "rds_database" {
  description = "PostgreSQL database name"
  type        = string
}

variable "db_username" {
  description = "Master username QuickSight uses to read the dataset"
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "Master password QuickSight uses to read the dataset"
  type        = string
  sensitive   = true
}
