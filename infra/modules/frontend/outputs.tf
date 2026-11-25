output "bucket_name" {
  description = "Name of the private frontend bucket"
  value       = aws_s3_bucket.frontend.id
}

output "bucket_arn" {
  description = "ARN of the private frontend bucket"
  value       = aws_s3_bucket.frontend.arn
}

output "distribution_id" {
  description = "CloudFront distribution that serves the frontend"
  value       = aws_cloudfront_distribution.frontend.id
}

output "distribution_arn" {
  description = "ARN of the frontend CloudFront distribution"
  value       = aws_cloudfront_distribution.frontend.arn
}

output "distribution_domain_name" {
  description = "Hostname CloudFront assigns, such as d111111abcdef8.cloudfront.net"
  value       = aws_cloudfront_distribution.frontend.domain_name
}

output "github_deploy_role_arn" {
  description = "Role assumed by the frontend deploy workflow on main"
  value       = aws_iam_role.github_deploy.arn
}
