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

# ALB for Order Server (if needed for direct access)
module "order_alb" {
  source  = "terraform-aws-modules/alb/aws"
  version = "8.7.0"

  name = "${local.name_prefix}-order-alb-${random_string.suffix.result}"

  load_balancer_type = "application"

  vpc_id          = module.vpc.vpc_id
  subnets         = module.vpc.public_subnets
  security_groups = [aws_security_group.alb_sg.id]

  target_groups = [
    {
      name_prefix      = "ord-"
      backend_protocol = "HTTP"
      backend_port     = 80
      target_type      = "lambda"
      health_check = {
        enabled             = true
        interval            = 30
        path                = "/health"
        port                = "traffic-port"
        healthy_threshold   = 3
        unhealthy_threshold = 3
        timeout             = 6
        protocol            = "HTTP"
        matcher             = "200-399"
      }
    }
  ]

  http_tcp_listeners = [
    {
      port               = 80
      protocol           = "HTTP"
      target_group_index = 0
    }
  ]

  tags = local.tags
}
