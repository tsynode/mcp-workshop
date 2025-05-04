# ECR Repository for Bedrock Client
resource "aws_ecr_repository" "bedrock_client" {
  name                 = "bedrock-client"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-bedrock-client-ecr-repo"
  })
}

# CloudWatch Log Group for Bedrock Client
resource "aws_cloudwatch_log_group" "bedrock_client" {
  name              = "/ecs/bedrock-client"
  retention_in_days = 30

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-bedrock-client-logs"
  })
}

# ECS Task Definition for Bedrock Client
resource "aws_ecs_task_definition" "bedrock_client" {
  family                   = "bedrock-client"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "bedrock-client"
      image     = "${aws_ecr_repository.bedrock_client.repository_url}:latest"
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
          value = "https://${aws_lb.product_alb.dns_name}/mcp"
        },
        {
          name  = "ORDER_MCP_SERVER_URL"
          value = "https://${aws_lb.order_alb.dns_name}/mcp"
        }
      ]
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-region"        = var.aws_region
          "awslogs-group"         = aws_cloudwatch_log_group.bedrock_client.name
          "awslogs-stream-prefix" = "bedrock-client"
        }
      }
    }
  ])
  
  tags = merge(local.tags, {
    Name = "${local.name_prefix}-bedrock-client-task-definition"
  })
}

# Security Group for Bedrock Client
resource "aws_security_group" "bedrock_client_sg" {
  name        = "${local.name_prefix}-bedrock-client-sg-${random_string.suffix.result}"
  description = "Security group for Bedrock Client"
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
    Name = "${local.name_prefix}-bedrock-client-sg"
  })
}

# ECS Service for Bedrock Client
resource "aws_ecs_service" "bedrock_client" {
  name            = "bedrock-client"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.bedrock_client.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = module.vpc.private_subnets
    security_groups  = [aws_security_group.bedrock_client_sg.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.bedrock_client.arn
    container_name   = "bedrock-client"
    container_port   = 8501
  }

  depends_on = [aws_lb_listener.bedrock_client]
  
  tags = merge(local.tags, {
    Name = "${local.name_prefix}-bedrock-client-service"
  })
}

# Application Load Balancer for Bedrock Client
resource "aws_lb" "bedrock_client" {
  name               = "bedrock-client-alb-${random_string.suffix.result}"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_sg.id]
  subnets            = module.vpc.public_subnets

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-bedrock-client-alb"
  })
}

# Target Group for Bedrock Client
resource "aws_lb_target_group" "bedrock_client" {
  name        = "bedrock-client-tg-${random_string.suffix.result}"
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
    Name = "${local.name_prefix}-bedrock-client-target-group"
  })
}

# Listener for Bedrock Client ALB
resource "aws_lb_listener" "bedrock_client" {
  load_balancer_arn = aws_lb.bedrock_client.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.bedrock_client.arn
  }

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-bedrock-client-listener"
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

# Output the Bedrock Client URL
output "bedrock_client_url" {
  description = "URL for the Bedrock Client"
  value       = "http://${aws_lb.bedrock_client.dns_name}"
}

# Output the Bedrock Client ECR Repository URL
output "bedrock_client_repository_url" {
  description = "URL of the Bedrock Client ECR repository"
  value       = aws_ecr_repository.bedrock_client.repository_url
}
