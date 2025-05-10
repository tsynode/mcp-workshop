terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
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

# All outputs and resource references are now defined in their respective component files:
# - product-server.tf
# - order-server.tf
# - mcp-playground.tf

# Create API Gateway for the MCP servers
resource "aws_apigatewayv2_api" "mcp_api" {
  name          = "${local.name_prefix}-mcp-api-${random_string.suffix.result}"
  protocol_type = "HTTP"
  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["POST", "GET", "OPTIONS"]
    allow_headers = ["content-type", "accept", "authorization"]
    max_age       = 300
  }
}

# Create API Gateway stage
resource "aws_apigatewayv2_stage" "mcp_api_stage" {
  api_id      = aws_apigatewayv2_api.mcp_api.id
  name        = "dev"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 100
    throttling_rate_limit  = 50
  }
}

output "deployment_info" {
  value = <<EOT
MCP Workshop Lab 03 Deployment Information
------------------------------------------
Region: ${var.aws_region}

# Lambda-based MCP Servers (via API Gateway)
Product Server: ${aws_apigatewayv2_api.mcp_api.api_endpoint}/product-server/mcp
Order Server: ${aws_apigatewayv2_api.mcp_api.api_endpoint}/order-server/mcp

# ECS/Fargate-based MCP Playground
MCP Playground: http://${module.mcp_playground_alb.lb_dns_name}

Claude Desktop Configuration:
{
  "mcp_servers": {
    "aws-product-server": {
      "url": "${aws_apigatewayv2_api.mcp_api.api_endpoint}/product-server/mcp"
    },
    "aws-order-server": {
      "url": "${aws_apigatewayv2_api.mcp_api.api_endpoint}/order-server/mcp"
    }
  }
}
EOT
}

# Output the Lambda function names
output "product_server_lambda_function_name" {
  value = aws_lambda_function.product_server.function_name
}

output "order_server_lambda_function_name" {
  value = aws_lambda_function.order_server.function_name
}

# Output the API Gateway endpoint
output "mcp_api_endpoint" {
  value = aws_apigatewayv2_api.mcp_api.api_endpoint
}

# Output the specific MCP server endpoints
output "product_server_endpoint" {
  value = "${aws_apigatewayv2_api.mcp_api.api_endpoint}/product-server/mcp"
}

output "order_server_endpoint" {
  value = "${aws_apigatewayv2_api.mcp_api.api_endpoint}/order-server/mcp"
}
