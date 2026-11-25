output "ecr_repository_url" {
  description = "URL used to push and pull the backend image"
  value       = aws_ecr_repository.backend.repository_url
}

output "ecr_repository_name" {
  description = "ECR repository name"
  value       = aws_ecr_repository.backend.name
}

output "cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.backend.name
}

output "service_name" {
  description = "ECS service name"
  value       = aws_ecs_service.backend.name
}

output "task_role_arn" {
  description = "Task role. The evidence bucket policy already allows this name."
  value       = aws_iam_role.task.arn
}

output "execution_role_arn" {
  description = "Role that pulls the image and writes logs"
  value       = aws_iam_role.execution.arn
}

output "github_deploy_role_arn" {
  description = "Role assumed by GitHub Actions on a push to main"
  value       = aws_iam_role.github_deploy.arn
}

output "log_group_name" {
  description = "CloudWatch log group for the backend task"
  value       = aws_cloudwatch_log_group.backend.name
}
