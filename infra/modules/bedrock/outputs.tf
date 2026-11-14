output "kb_role_arn" {
  description = "ARN of the Bedrock knowledge base role. The document bucket policy already reserves this name."
  value       = aws_iam_role.knowledge_base.arn
}

output "agent_role_arn" {
  description = "ARN of the AgentCore harness execution role"
  value       = aws_iam_role.agent.arn
}

output "gateway_id" {
  description = "Id of the study-note retrieval gateway"
  value       = aws_bedrockagentcore_gateway.normative.gateway_id
}

output "retrieve_function_name" {
  description = "Name of the Lambda that calls Retrieve on the knowledge bases"
  value       = aws_lambda_function.retrieve.function_name
}

output "vector_bucket_name" {
  description = "Name of the S3 Vectors bucket"
  value       = aws_s3vectors_vector_bucket.normative.vector_bucket_name
}

output "knowledge_base_ids" {
  description = "Bedrock knowledge base ids keyed by corpus"
  value       = { for key, kb in aws_bedrockagent_knowledge_base.corpus : key => kb.id }
}

output "data_source_ids" {
  description = "Bedrock data source ids keyed by corpus"
  value       = { for key, source in aws_bedrockagent_data_source.corpus : key => source.data_source_id }
}

output "harness_id" {
  description = "Id of the Normative Advisor harness"
  value       = aws_bedrockagentcore_harness.normative.harness_id
}

output "harness_arn" {
  description = "ARN of the Normative Advisor harness"
  value       = aws_bedrockagentcore_harness.normative.arn
}

output "report_role_arn" {
  description = "ARN of the Report Generator harness execution role"
  value       = aws_iam_role.report.arn
}

output "report_harness_id" {
  description = "Id of the Report Generator harness"
  value       = aws_bedrockagentcore_harness.report.harness_id
}

output "report_harness_arn" {
  description = "ARN of the Report Generator harness"
  value       = aws_bedrockagentcore_harness.report.arn
}
