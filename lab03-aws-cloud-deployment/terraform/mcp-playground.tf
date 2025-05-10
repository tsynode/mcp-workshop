# MCP Playground Component

# IAM roles and policies for ECS tasks

# ECS Task Execution Role
resource "aws_iam_role" "ecs_task_execution_role" {
  name = "${local.name_prefix}-ecs-execution-role-${random_string.suffix.result}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = local.tags
}

# Attach the ECS Task Execution Role policy
resource "aws_iam_role_policy_attachment" "ecs_task_execution_role_policy" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ECS Task Role (for container permissions)
resource "aws_iam_role" "ecs_task_role" {
  name = "${local.name_prefix}-ecs-task-role-${random_string.suffix.result}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = local.tags
}

# Attach policies to the ECS Task Role as needed
resource "aws_iam_role_policy" "ecs_task_role_policy" {
  name = "${local.name_prefix}-ecs-task-policy-${random_string.suffix.result}"
  role = aws_iam_role.ecs_task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Effect   = "Allow",
        Resource = "*"
      }
    ]
  })
}

# ECR Repository for MCP Playground (Bedrock Client)
resource "aws_ecr_repository" "mcp_playground_repository" {
  name                 = "mcp-playground"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.tags
}

# ECS Cluster for MCP Playground
resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster-${random_string.suffix.result}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = local.tags
}

# ECS Cluster Capacity Providers
resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name = aws_ecs_cluster.main.name

  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    base              = 1
    weight            = 100
    capacity_provider = "FARGATE"
  }
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
  
  # This ensures this resource is only created after the ECR repository
  depends_on = [
    aws_ecr_repository.mcp_playground_repository
  ]

  container_definitions = jsonencode([
    {
      name      = "mcp-playground"
      image     = "${aws_ecr_repository.mcp_playground_repository.repository_url}:latest"
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
          value = "${aws_apigatewayv2_api.mcp_api.api_endpoint}/product-server/mcp"
        },
        {
          name  = "ORDER_MCP_SERVER_URL"
          value = "${aws_apigatewayv2_api.mcp_api.api_endpoint}/order-server/mcp"
        },
        {
          name  = "BEDROCK_MODEL_ID"
          value = "anthropic.claude-3-haiku-20240307-v1:0"
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
  
  # This ensures this resource is only created after the ECR repository, task definition, and load balancer
  depends_on = [
    aws_ecr_repository.mcp_playground_repository,
    aws_ecs_task_definition.mcp_playground,
    module.mcp_playground_alb
  ]

  network_configuration {
    subnets          = module.vpc.private_subnets
    security_groups  = [aws_security_group.mcp_playground_sg.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = module.mcp_playground_alb.target_group_arns[0]
    container_name   = "mcp-playground"
    container_port   = 8501
  }

  # depends_on is defined above
  
  tags = merge(local.tags, {
    Name = "${local.name_prefix}-mcp-playground-service"
  })
}

# Application Load Balancer for MCP Playground
module "mcp_playground_alb" {
  source  = "terraform-aws-modules/alb/aws"
  version = "8.7.0"

  name = "mcp-pg-alb-${random_string.suffix.result}"

  load_balancer_type = "application"

  vpc_id          = module.vpc.vpc_id
  subnets         = module.vpc.public_subnets
  security_groups = [aws_security_group.alb_sg.id]

  target_groups = [
    {
      name_prefix      = "mcp-"
      backend_protocol = "HTTP"
      backend_port     = 8501
      target_type      = "ip"
      health_check = {
        enabled             = true
        interval            = 30
        path                = "/"
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

# Note: Target Group and Listener are now managed by the ALB module

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
  value       = "http://${module.mcp_playground_alb.lb_dns_name}"
}

# Output the MCP Playground ECR Repository URL
output "mcp_playground_repository_url" {
  description = "URL of the MCP Playground ECR repository"
  value       = aws_ecr_repository.mcp_playground_repository.repository_url
}
