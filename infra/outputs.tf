output "vpc_id" {
  description = "ID of the VPC"
  value       = module.networking.vpc_id
}

output "public_subnet_ids" {
  description = "IDs of public subnets"
  value       = module.networking.public_subnet_ids
}

output "private_subnet_ids" {
  description = "IDs of private subnets"
  value       = module.networking.private_subnet_ids
}

output "rds_endpoint" {
  description = "RDS instance endpoint"
  value       = module.database.rds_endpoint
}

output "rds_port" {
  description = "RDS instance port"
  value       = module.database.rds_port
}

output "budget_sns_topic_arn" {
  description = "ARN of the SNS topic for budget alerts"
  value       = module.cost.sns_topic_arn
}

output "cognito_user_pool_id" {
  description = "ID of the Cognito User Pool"
  value       = module.cognito.user_pool_id
}

output "cognito_app_client_id" {
  description = "ID of the Cognito frontend app client"
  value       = module.cognito.app_client_id
}

output "cognito_issuer_url" {
  description = "OpenID Connect issuer URL for JWT validation"
  value       = module.cognito.issuer_url
}

output "evidence_bucket_name" {
  description = "Name of the evidence S3 bucket"
  value       = module.evidence.bucket_name
}

output "evidence_bucket_arn" {
  description = "ARN of the evidence S3 bucket"
  value       = module.evidence.bucket_arn
}

output "evidence_table_name" {
  description = "Name of the evidence DynamoDB table"
  value       = module.evidence.table_name
}

output "evidence_table_arn" {
  description = "ARN of the evidence DynamoDB table"
  value       = module.evidence.table_arn
}

output "evidence_backend_task_role_arn" {
  description = "ARN reserved for the future ECS task role that may access evidence"
  value       = module.evidence.backend_task_role_arn
}
