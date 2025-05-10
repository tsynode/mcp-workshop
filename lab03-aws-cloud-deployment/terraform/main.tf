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

# Create REST API Gateway for the MCP servers (matching example repo)
resource "aws_api_gateway_rest_api" "mcp_api" {
  name = "${local.name_prefix}-mcp-api-${random_string.suffix.result}"
  
  lifecycle {
    create_before_destroy = true
  }
}

# Create API Gateway deployment
resource "aws_api_gateway_deployment" "mcp_api_deployment" {
  rest_api_id = aws_api_gateway_rest_api.mcp_api.id
  
  # Depend on the API Gateway integrations
  depends_on = [
    aws_api_gateway_integration.product_server_lambda,
    aws_api_gateway_integration.order_server_lambda
  ]
  
  lifecycle {
    create_before_destroy = true
  }
  
  triggers = {
    # Always redeploy
    redeployment = timestamp()
  }
}

# Create API Gateway stage
resource "aws_api_gateway_stage" "mcp_api_stage" {
  rest_api_id   = aws_api_gateway_rest_api.mcp_api.id
  deployment_id = aws_api_gateway_deployment.mcp_api_deployment.id
  stage_name    = "dev"
}

output "deployment_info" {
  value = <<EOT
MCP Workshop Lab 03 Deployment Information
------------------------------------------
Region: ${var.aws_region}

# Lambda-based MCP Servers (via API Gateway)
Product Server: https://${aws_api_gateway_rest_api.mcp_api.id}.execute-api.${var.aws_region}.amazonaws.com/${aws_api_gateway_stage.mcp_api_stage.stage_name}/mcp
Order Server: https://${aws_api_gateway_rest_api.mcp_api.id}.execute-api.${var.aws_region}.amazonaws.com/${aws_api_gateway_stage.mcp_api_stage.stage_name}/order-mcp

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
