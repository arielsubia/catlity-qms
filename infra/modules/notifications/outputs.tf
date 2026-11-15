output "sender_email" {
  description = "Sandbox sender address. SES sends a verification message when this identity is created."
  value       = aws_sesv2_email_identity.sender.email_identity
}

output "sender_identity_arn" {
  description = "ARN of the SES email identity"
  value       = aws_sesv2_email_identity.sender.arn
}

output "configuration_set_name" {
  description = "SES configuration set that publishes delivery events to SNS"
  value       = aws_sesv2_configuration_set.notifications.configuration_set_name
}

output "topic_arn" {
  description = "ARN of the SNS topic that receives SES delivery, bounce, complaint, and reject events"
  value       = aws_sns_topic.notification_events.arn
}

output "finding_assigned_template_name" {
  description = "SES template for an assigned finding. Placeholders: recipient_name, finding_title, audit_name, action_url."
  value       = aws_ses_template.finding_assigned.name
}

output "corrective_action_overdue_template_name" {
  description = "SES template for an overdue corrective action. Placeholders: recipient_name, action_description, due_date, action_url."
  value       = aws_ses_template.corrective_action_overdue.name
}

output "table_name" {
  description = "Name of the notification history DynamoDB table"
  value       = aws_dynamodb_table.notifications.name
}

output "table_arn" {
  description = "ARN of the notification history DynamoDB table"
  value       = aws_dynamodb_table.notifications.arn
}
