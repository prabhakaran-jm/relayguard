output "lambda_function_name" {
  description = "Deployed RelayGuard worker Lambda function name"
  value       = aws_lambda_function.worker.function_name
}

output "lambda_function_arn" {
  description = "Deployed RelayGuard worker Lambda function ARN"
  value       = aws_lambda_function.worker.arn
}

output "lambda_execution_role_arn" {
  description = "IAM role ARN used by the worker Lambda"
  value       = aws_iam_role.lambda_execution.arn
}

output "aws_region" {
  description = "AWS region for the worker Lambda"
  value       = var.aws_region
}
