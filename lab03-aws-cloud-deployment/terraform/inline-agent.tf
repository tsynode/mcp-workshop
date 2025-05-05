# ECR Repository for Inline Agent
resource "aws_ecr_repository" "inline_agent" {
  name                 = "inline-agent"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-inline-agent-ecr-repo"
  })
}

# CloudWatch Log Group for Inline Agent
resource "aws_cloudwatch_log_group" "inline_agent" {
  name              = "/ecs/inline-agent"
  retention_in_days = 30

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-inline-agent-logs"
  })
}

# ECS Task Definition for Inline Agent
resource "aws_ecs_task_definition" "inline_agent" {
  family                   = "inline-agent"
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
    aws_ecr_repository.inline_agent
  ]

  container_definitions = jsonencode([
    {
      name      = "inline-agent"
      image     = "${aws_ecr_repository.inline_agent.repository_url}:latest"
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
          "awslogs-group"         = aws_cloudwatch_log_group.inline_agent.name
          "awslogs-stream-prefix" = "inline-agent"
        }
      }
    }
  ])
  
  tags = merge(local.tags, {
    Name = "${local.name_prefix}-inline-agent-task-definition"
  })
}

# Security Group for Inline Agent
resource "aws_security_group" "inline_agent_sg" {
  name        = "${local.name_prefix}-inline-agent-sg-${random_string.suffix.result}"
  description = "Security group for Inline Agent"
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
    Name = "${local.name_prefix}-inline-agent-sg"
  })
}

# ECS Service for Inline Agent
resource "aws_ecs_service" "inline_agent" {
  name            = "inline-agent"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.inline_agent.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  
  # This ensures this resource is only created after the ECR repositories, task definition, and load balancer
  depends_on = [
    aws_ecr_repository.inline_agent,
    aws_ecs_task_definition.inline_agent,
    aws_lb_listener.inline_agent
  ]

  network_configuration {
    subnets          = module.vpc.private_subnets
    security_groups  = [aws_security_group.inline_agent_sg.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.inline_agent.arn
    container_name   = "inline-agent"
    container_port   = 8501
  }
  
  tags = merge(local.tags, {
    Name = "${local.name_prefix}-inline-agent-service"
  })
}

# Application Load Balancer for Inline Agent
resource "aws_lb" "inline_agent" {
  name               = "inline-agent-alb-${random_string.suffix.result}"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_sg.id]
  subnets            = module.vpc.public_subnets

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-inline-agent-alb"
  })
}

# Target Group for Inline Agent
resource "aws_lb_target_group" "inline_agent" {
  name        = "inline-agent-tg-${random_string.suffix.result}"
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
    Name = "${local.name_prefix}-inline-agent-target-group"
  })
}

# Listener for Inline Agent ALB
resource "aws_lb_listener" "inline_agent" {
  load_balancer_arn = aws_lb.inline_agent.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.inline_agent.arn
  }

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-inline-agent-listener"
  })
}

# Attach Bedrock Policy to ECS Task Role (reusing the existing policy)
resource "aws_iam_role_policy_attachment" "inline_agent_bedrock_policy_attachment" {
  role       = aws_iam_role.ecs_task_role.name
  policy_arn = aws_iam_policy.bedrock_access.arn
}

# Output the Inline Agent URL
output "inline_agent_url" {
  description = "URL for the Inline Agent"
  value       = "http://${aws_lb.inline_agent.dns_name}"
}

# Output the Inline Agent ECR Repository URL
output "inline_agent_repository_url" {
  description = "URL of the Inline Agent ECR repository"
  value       = aws_ecr_repository.inline_agent.repository_url
}
