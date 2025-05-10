###############################################
# Product Server-based MCP Servers Configuration
###############################################

# IAM Role for Product and Order Server Lambda functions
resource "aws_iam_role" "product_server_role" {
  name = "${local.name_prefix}-product-server-role-${random_string.suffix.result}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = local.tags
}

# Attach the AWS Lambda basic execution role policy
resource "aws_iam_role_policy_attachment" "product_server_basic" {
  role       = aws_iam_role.product_server_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Create a Product Server function for the Product MCP Server
resource "aws_lambda_function" "product_server" {
  function_name = "${local.name_prefix}-product-server-${random_string.suffix.result}"
  role          = aws_iam_role.product_server_role.arn
  handler       = "run.sh"
  runtime       = var.lambda_runtime
  timeout       = var.lambda_timeout
  memory_size   = var.product_server_memory

  # Use Lambda Web Adapter Layer
  layers = [
    "arn:aws:lambda:${var.aws_region}:753240598075:layer:LambdaAdapterLayerX86:25"
  ]

  # Package the source code
  filename         = data.archive_file.product_server_zip.output_path
  source_code_hash = data.archive_file.product_server_zip.output_base64sha256

  environment {
    variables = {
      AWS_LAMBDA_EXEC_WRAPPER = "/opt/bootstrap"
      AWS_LWA_PORT = "8080"
      PORT = "8080"
    }
  }

  tags = local.tags
}

# Create a Product Server function for the Order MCP Server
resource "aws_lambda_function" "order_server" {
  function_name = "${local.name_prefix}-order-server-${random_string.suffix.result}"
  role          = aws_iam_role.product_server_role.arn
  handler       = "run.sh"
  runtime       = var.lambda_runtime
  timeout       = var.lambda_timeout
  memory_size   = var.order_server_memory

  # Use Lambda Web Adapter Layer
  layers = [
    "arn:aws:lambda:${var.aws_region}:753240598075:layer:LambdaAdapterLayerX86:25"
  ]

  # Package the source code
  filename         = data.archive_file.order_server_zip.output_path
  source_code_hash = data.archive_file.order_server_zip.output_base64sha256

  environment {
    variables = {
      AWS_LAMBDA_EXEC_WRAPPER = "/opt/bootstrap"
      AWS_LWA_PORT = "8080"
      PORT = "8080"
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
# Create API Gateway resources for the product server
resource "aws_api_gateway_resource" "product_server_mcp" {
  rest_api_id = aws_api_gateway_rest_api.mcp_api.id
  parent_id   = aws_api_gateway_rest_api.mcp_api.root_resource_id
  path_part   = "mcp"
}

resource "aws_api_gateway_method" "product_server_any" {
  rest_api_id   = aws_api_gateway_rest_api.mcp_api.id
  resource_id   = aws_api_gateway_resource.product_server_mcp.id
  authorization = "NONE"
  http_method   = "ANY"
}

resource "aws_api_gateway_integration" "product_server_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.mcp_api.id
  resource_id             = aws_api_gateway_resource.product_server_mcp.id
  http_method             = aws_api_gateway_method.product_server_any.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.product_server.invoke_arn
}

# Create API Gateway resources for the order server
resource "aws_api_gateway_resource" "order_server_mcp" {
  rest_api_id = aws_api_gateway_rest_api.mcp_api.id
  parent_id   = aws_api_gateway_rest_api.mcp_api.root_resource_id
  path_part   = "order-mcp"
}

resource "aws_api_gateway_method" "order_server_any" {
  rest_api_id   = aws_api_gateway_rest_api.mcp_api.id
  resource_id   = aws_api_gateway_resource.order_server_mcp.id
  authorization = "NONE"
  http_method   = "ANY"
}

resource "aws_api_gateway_integration" "order_server_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.mcp_api.id
  resource_id             = aws_api_gateway_resource.order_server_mcp.id
  http_method             = aws_api_gateway_method.order_server_any.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.order_server.invoke_arn
}

# Grant API Gateway permission to invoke the product server Product Server
resource "aws_lambda_permission" "product_server_permission" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.product_server.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.mcp_api.execution_arn}/*/*/*"
}

# Grant API Gateway permission to invoke the order server Product Server
resource "aws_lambda_permission" "order_server_permission" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.order_server.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.mcp_api.execution_arn}/*/*/*"
}

# Note: ALB for Product Server has been removed as it's redundant with API Gateway access
# Lambda functions are accessed through the API Gateway endpoints defined above

# Outputs for the Lambda functions are defined in main.tf
# API Gateway endpoint is defined in main.tf
# Product server endpoint is defined in main.tf
# Order server endpoint is defined in main.tf
