variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-west-2"
}

variable "github_repository" {
  description = "GitHub repository name (username/repo)"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones_count" {
  description = "Number of AZs to use"
  type        = number
  default     = 2
}

# Lambda function configuration
variable "lambda_runtime" {
  description = "Runtime for Lambda functions"
  type        = string
  default     = "nodejs22.x"
}

variable "lambda_timeout" {
  description = "Timeout for Lambda functions in seconds"
  type        = number
  default     = 30
}

variable "product_server_memory" {
  description = "Memory for product server Lambda function in MB"
  type        = number
  default     = 256
}

variable "order_server_memory" {
  description = "Memory for order server Lambda function in MB"
  type        = number
  default     = 256
}

variable "health_check_path" {
  description = "Path for health check"
  type        = string
  default     = "/health"
}

variable "enable_https" {
  description = "Enable HTTPS for ALB (requires ACM certificate)"
  type        = bool
  default     = true
}

# Optional: Certificate ARN for HTTPS
variable "certificate_arn" {
  description = "ARN of ACM certificate for HTTPS"
  type        = string
  default     = ""
}
