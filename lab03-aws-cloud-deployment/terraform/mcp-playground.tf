# ECR Repository for MCP Playground
resource "aws_ecr_repository" "mcp_playground" {
  name                 = "mcp-playground"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-mcp-playground-ecr-repo"
  })
}

# CloudWatch Log Group for MCP Playground
resource "aws_cloudwatch_log_group" "mcp_playground" {
  name              = "/ecs/mcp-playground"
  retention_in_days = 30

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-mcp-playground-logs"
  })
}

# ECS Task Definition for MCP Playground
resource "aws_ecs_task_definition" "mcp_playground" {
  family                   = "mcp-playground"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn
  
  # This ensures this resource is only created after the ECR repositories
  depends_on = [
    aws_ecr_repository.product_repository,
    aws_ecr_repository.order_repository,
    aws_ecr_repository.mcp_playground
  ]

  container_definitions = jsonencode([
    {
      name      = "mcp-playground"
      image     = "${aws_ecr_repository.mcp_playground.repository_url}:latest"
      essential = true
      
      portMappings = [
        {
          containerPort = 8501
          hostPort      = 8501
          protocol      = "tcp"
        }
      ]
      
      environment = [
        {
          name  = "PRODUCT_MCP_SERVER_URL"
          value = "https://${module.product_alb.lb_dns_name}/mcp"
        },
        {
          name  = "ORDER_MCP_SERVER_URL"
          value = "https://${module.order_alb.lb_dns_name}/mcp"
        }
      ]
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-region"        = var.aws_region
          "awslogs-group"         = aws_cloudwatch_log_group.mcp_playground.name
          "awslogs-stream-prefix" = "mcp-playground"
        }
      }
    }
  ])
  
  tags = merge(local.tags, {
    Name = "${local.name_prefix}-mcp-playground-task-definition"
  })
}

# Security Group for MCP Playground
resource "aws_security_group" "mcp_playground_sg" {
  name        = "${local.name_prefix}-mcp-playground-sg-${random_string.suffix.result}"
  description = "Security group for MCP Playground"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 8501
    to_port     = 8501
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-mcp-playground-sg"
  })
}

# ECS Service for MCP Playground
resource "aws_ecs_service" "mcp_playground" {
  name            = "mcp-playground"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.mcp_playground.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  
  # This ensures this resource is only created after the ECR repositories, task definition, and load balancer
  depends_on = [
    aws_ecr_repository.mcp_playground,
    aws_ecs_task_definition.mcp_playground,
    aws_lb_listener.mcp_playground
  ]

  network_configuration {
    subnets          = module.vpc.private_subnets
    security_groups  = [aws_security_group.mcp_playground_sg.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.mcp_playground.arn
    container_name   = "mcp-playground"
    container_port   = 8501
  }

  # depends_on is defined above
  
  tags = merge(local.tags, {
    Name = "${local.name_prefix}-mcp-playground-service"
  })
}

# Application Load Balancer for MCP Playground
resource "aws_lb" "mcp_playground" {
  name               = "mcp-playground-alb-${random_string.suffix.result}"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_sg.id]
  subnets            = module.vpc.public_subnets

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-mcp-playground-alb"
  })
}

# Target Group for MCP Playground
resource "aws_lb_target_group" "mcp_playground" {
  name        = "mcp-playground-tg-${random_string.suffix.result}"
  port        = 8501
  protocol    = "HTTP"
  vpc_id      = module.vpc.vpc_id
  target_type = "ip"

  health_check {
    path                = "/"
    port                = 8501
    protocol            = "HTTP"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 3
    unhealthy_threshold = 3
    matcher             = "200"
  }
  
  tags = merge(local.tags, {
    Name = "${local.name_prefix}-mcp-playground-target-group"
  })
}

# Listener for MCP Playground ALB
resource "aws_lb_listener" "mcp_playground" {
  load_balancer_arn = aws_lb.mcp_playground.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.mcp_playground.arn
  }

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-mcp-playground-listener"
  })
}

# IAM Policy for Bedrock Access
resource "aws_iam_policy" "bedrock_access" {
  name        = "bedrock-access-policy"
  description = "Policy for accessing Amazon Bedrock"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "bedrock:InvokeModel",
          "bedrock:Converse"
        ]
        Effect   = "Allow"
        Resource = "*"
      }
    ]
  })
}

# Attach Bedrock Policy to ECS Task Role
resource "aws_iam_role_policy_attachment" "bedrock_policy_attachment" {
  role       = aws_iam_role.ecs_task_role.name
  policy_arn = aws_iam_policy.bedrock_access.arn
}

# Output the MCP Playground URL
output "mcp_playground_url" {
  description = "URL for the MCP Playground"
  value       = "http://${aws_lb.mcp_playground.dns_name}"
}

# Output the MCP Playground ECR Repository URL
output "mcp_playground_repository_url" {
  description = "URL of the MCP Playground ECR repository"
  value       = aws_ecr_repository.mcp_playground.repository_url
}
