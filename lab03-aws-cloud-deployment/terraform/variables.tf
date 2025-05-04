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

variable "container_port_product" {
  description = "Port exposed by the product server container"
  type        = number
  default     = 3000
}

variable "container_port_order" {
  description = "Port exposed by the order server container"
  type        = number
  default     = 3001
}

variable "product_server_image" {
  description = "Docker image for product server"
  type        = string
  default     = "product-server:latest"
}

variable "order_server_image" {
  description = "Docker image for order server"
  type        = string
  default     = "order-server:latest"
}

variable "product_server_cpu" {
  description = "CPU units for product server (1024 = 1 vCPU)"
  type        = number
  default     = 256
}

variable "product_server_memory" {
  description = "Memory for product server in MiB"
  type        = number
  default     = 512
}

variable "order_server_cpu" {
  description = "CPU units for order server (1024 = 1 vCPU)"
  type        = number
  default     = 256
}

variable "order_server_memory" {
  description = "Memory for order server in MiB"
  type        = number
  default     = 512
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
