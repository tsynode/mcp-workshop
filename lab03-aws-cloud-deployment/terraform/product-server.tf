###############################################
# Product Server-based MCP Servers Configuration
###############################################

# Create a Product Server function for the Product MCP Server
resource "aws_lambda_function" "product_server" {
  function_name = "${local.name_prefix}-product-server-${random_string.suffix.result}"
  role          = aws_iam_role.product_server_role.arn
  handler       = "index.handler"
  runtime       = var.lambda_runtime
  timeout       = var.lambda_timeout
  memory_size   = var.product_server_memory

  # Use Lambda Web Adapter Layer
  layers = [
    "arn:aws:lambda:${var.aws_region}:753240598075:layer:LambdaAdapterLayerX86:17"
  ]

  # Package the source code
  filename         = data.archive_file.product_server_zip.output_path
  source_code_hash = data.archive_file.product_server_zip.output_base64sha256

  environment {
    variables = {
      AWS_LAMBDA_EXEC_WRAPPER = "/opt/bootstrap"
      PORT                    = "8080"
    }
  }

  tags = local.tags
}

# Create a Product Server function for the Order MCP Server
resource "aws_lambda_function" "order_server" {
  function_name = "${local.name_prefix}-order-server-${random_string.suffix.result}"
  role          = aws_iam_role.product_server_role.arn
  handler       = "index.handler"
  runtime       = var.lambda_runtime
  timeout       = var.lambda_timeout
  memory_size   = var.order_server_memory

  # Use Lambda Web Adapter Layer
  layers = [
    "arn:aws:lambda:${var.aws_region}:753240598075:layer:LambdaAdapterLayerX86:17"
  ]

  # Package the source code
  filename         = data.archive_file.order_server_zip.output_path
  source_code_hash = data.archive_file.order_server_zip.output_base64sha256

  environment {
    variables = {
      AWS_LAMBDA_EXEC_WRAPPER = "/opt/bootstrap"
      PORT                    = "8080"
    }
  }

  tags = local.tags
}

# Create a ZIP archive of the product server code
data "archive_file" "product_server_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src/product-server"
  output_path = "${path.module}/product_server.zip"
}

# Create a ZIP archive of the order server code
data "archive_file" "order_server_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src/order-server"
  output_path = "${path.module}/order_server.zip"
}

# Use the API Gateway defined in main.tf

# Create API Gateway integration for the product server
resource "aws_apigatewayv2_integration" "product_server_integration" {
  api_id             = aws_apigatewayv2_api.mcp_api.id
  integration_type   = "AWS_PROXY"
  integration_uri    = aws_lambda_function.product_server.invoke_arn
  integration_method = "POST"
  payload_format_version = "2.0"
}

# Create API Gateway integration for the order server
resource "aws_apigatewayv2_integration" "order_server_integration" {
  api_id             = aws_apigatewayv2_api.mcp_api.id
  integration_type   = "AWS_PROXY"
  integration_uri    = aws_lambda_function.order_server.invoke_arn
  integration_method = "POST"
  payload_format_version = "2.0"
}

# Create API Gateway route for the product server
resource "aws_apigatewayv2_route" "product_server_route" {
  api_id    = aws_apigatewayv2_api.mcp_api.id
  route_key = "ANY /product-server/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.product_server_integration.id}"
}

# Create API Gateway route for the order server
resource "aws_apigatewayv2_route" "order_server_route" {
  api_id    = aws_apigatewayv2_api.mcp_api.id
  route_key = "ANY /order-server/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.order_server_integration.id}"
}

# Grant API Gateway permission to invoke the product server Product Server
resource "aws_lambda_permission" "product_server_permission" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.product_server.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.mcp_api.execution_arn}/*/*/product-server/*"
}

# Grant API Gateway permission to invoke the order server Product Server
resource "aws_lambda_permission" "order_server_permission" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.order_server.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.mcp_api.execution_arn}/*/*/order-server/*"
}

# Outputs for the Lambda functions are defined in main.tf
# API Gateway endpoint is defined in main.tf
# Product server endpoint is defined in main.tf
# Order server endpoint is defined in main.tf
