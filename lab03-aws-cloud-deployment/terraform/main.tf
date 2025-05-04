terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  # Uncomment this block to use Terraform Cloud for state management
  # backend "s3" {
  #   bucket = "your-terraform-state-bucket"
  #   key    = "lab03/terraform.tfstate"
  #   region = "us-west-2"
  # }
}

provider "aws" {
  region = var.aws_region
}

# Random string for unique naming
resource "random_string" "suffix" {
  length  = 8
  special = false
  upper   = false
}

locals {
  name_prefix = "mcp-workshop"
  tags = {
    Project     = "MCP Workshop"
    Lab         = "Lab03"
    Environment = "Development"
    Terraform   = "true"
  }
}

# Get availability zones for the region
data "aws_availability_zones" "available" {
  state = "available"
}

# Output the deployment info
output "deployment_info" {
  value = <<EOT
MCP Workshop Lab 03 Deployment Information
------------------------------------------
Region: ${var.aws_region}
VPC ID: ${module.vpc.vpc_id}
Product Server ALB: https://${module.product_alb.lb_dns_name}/mcp
Order Server ALB: https://${module.order_alb.lb_dns_name}/mcp

Claude Desktop Configuration:
{
  "mcpServers": {
    "aws-product-server": {
      "url": "https://${module.product_alb.lb_dns_name}/mcp"
    },
    "aws-order-server": {
      "url": "https://${module.order_alb.lb_dns_name}/mcp"
    }
  }
}
EOT
}

output "product_repository_url" {
  value = aws_ecr_repository.product_repository.repository_url
}

output "order_repository_url" {
  value = aws_ecr_repository.order_repository.repository_url
}

output "product_alb_dns" {
  value = module.product_alb.lb_dns_name
}

output "order_alb_dns" {
  value = module.order_alb.lb_dns_name
}

output "bedrock_client_repository_url" {
  value = aws_ecr_repository.bedrock_client.repository_url
}
