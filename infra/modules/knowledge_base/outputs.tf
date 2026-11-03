output "bucket_name" {
  description = "Name of the normative knowledge base S3 bucket"
  value       = aws_s3_bucket.knowledge_base.id
}

output "bucket_arn" {
  description = "ARN of the normative knowledge base S3 bucket"
  value       = aws_s3_bucket.knowledge_base.arn
}

output "prefixes" {
  description = "S3 prefixes that hold the normative reference documents"
  value       = local.prefixes
}

output "document_keys" {
  description = "Object keys uploaded from the repository knowledge-base tree"
  value       = [for key in sort(tolist(local.document_keys)) : "knowledge-base/${key}"]
}

output "bedrock_kb_role_arn" {
  description = "ARN of the Bedrock knowledge base role. module.bedrock creates the role with this name."
  value       = local.bedrock_kb_role_arn
}

output "terraform_admin_principal_arn" {
  description = "IAM principal running Terraform, exempted by the knowledge base bucket policy"
  value       = data.aws_iam_session_context.current.issuer_arn
}
