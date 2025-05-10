# IAM role for Order Server functions
resource "aws_iam_role" "order_server_role" {
  name = "${local.name_prefix}-order_server-role-${random_string.suffix.result}"

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

# Attach the AWS MCP Order Server basic execution role policy
resource "aws_iam_role_policy_attachment" "order_server_basic" {
  role       = aws_iam_role.order_server_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Create a custom policy for MCP Order Server additional permissions if needed
resource "aws_iam_policy" "order_server_policy" {
  name        = "${local.name_prefix}-order_server-policy-${random_string.suffix.result}"
  description = "Policy for MCP Order Server functions"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Effect   = "Allow"
        Resource = "*"
      }
    ]
  })

  tags = local.tags
}

# Attach the custom policy to the MCP Order Server role
resource "aws_iam_role_policy_attachment" "order_server_policy_attachment" {
  role       = aws_iam_role.order_server_role.name
  policy_arn = aws_iam_policy.order_server_policy.arn
}

# Note: ALB for Order Server has been removed as it's redundant with API Gateway access
# Lambda functions are accessed through the API Gateway endpoints defined in product-server.tf
