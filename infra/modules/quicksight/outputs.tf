output "account_name" {
  description = "QuickSight account name. The IAM user who applies this module becomes the QuickSight admin."
  value       = aws_quicksight_account_subscription.main.account_name
}

output "vpc_connection_id" {
  description = "QuickSight VPC connection used to reach the private RDS instance"
  value       = aws_quicksight_vpc_connection.main.vpc_connection_id
}

output "data_source_id" {
  description = "QuickSight data source connected to RDS PostgreSQL"
  value       = aws_quicksight_data_source.postgres.data_source_id
}

output "compliance_data_set_id" {
  description = "SPICE dataset of audits and findings, filtered by tenant_id"
  value       = aws_quicksight_data_set.compliance.data_set_id
}

output "rls_data_set_id" {
  description = "Rules dataset that maps a QuickSight user name to tenant_id"
  value       = aws_quicksight_data_set.rls.data_set_id
}

output "refresh_schedule_id" {
  description = "Daily full refresh of the compliance dataset"
  value       = aws_quicksight_refresh_schedule.compliance.schedule_id
}
