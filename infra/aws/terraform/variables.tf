variable "aws_region" {
  description = "AWS region for the RelayGuard worker Lambda"
  type        = string
  default     = "us-east-1"
}

variable "function_name" {
  description = "Lambda function name"
  type        = string
  default     = "relayguard-worker"
}

variable "lambda_runtime" {
  description = "Python runtime for the worker Lambda"
  type        = string
  default     = "python3.12"
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 60
}

variable "lambda_memory_size" {
  description = "Lambda memory in MB"
  type        = number
  default     = 512
}

variable "lambda_package_path" {
  description = "Path to the built Lambda deployment zip"
  type        = string
  default     = "../build/lambda.zip"
}

variable "database_secret_arn" {
  description = "Secrets Manager ARN containing the CockroachDB Cloud DATABASE_URL"
  type        = string
}

variable "database_secret_name" {
  description = "Secrets Manager name passed to RELAYGUARD_DATABASE_SECRET_NAME"
  type        = string
}

variable "action_selector" {
  description = "RelayGuard action selector mode"
  type        = string
  default     = "mock"
}

variable "lease_ttl_seconds" {
  description = "Incident lease TTL used by RelayGuard workers"
  type        = number
  default     = 3
}
