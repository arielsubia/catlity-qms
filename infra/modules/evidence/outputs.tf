output "bucket_name" {
  description = "Name of the evidence S3 bucket"
  value       = aws_s3_bucket.evidence.id
}

output "bucket_arn" {
  description = "ARN of the evidence S3 bucket"
  value       = aws_s3_bucket.evidence.arn
}

output "table_name" {
  description = "Name of the evidence DynamoDB table"
  value       = aws_dynamodb_table.evidence.name
}

output "table_arn" {
  description = "ARN of the evidence DynamoDB table"
  value       = aws_dynamodb_table.evidence.arn
}

output "backend_task_role_arn" {
  description = "ARN reserved for the future ECS task role. This module does not create the role."
  value       = local.backend_task_role_arn
}

output "terraform_admin_principal_arn" {
  description = "IAM principal running Terraform, exempted by the evidence bucket policy"
  value       = data.aws_iam_session_context.current.issuer_arn
}
