resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-cluster"
  })
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "product_server" {
  name              = "/ecs/${local.name_prefix}-product-server"
  retention_in_days = 30

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-product-server-logs"
  })
}

resource "aws_cloudwatch_log_group" "order_server" {
  name              = "/ecs/${local.name_prefix}-order-server"
  retention_in_days = 30

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-order-server-logs"
  })
}

# Task Definition for Product Server
resource "aws_ecs_task_definition" "product_server" {
  family                   = "${local.name_prefix}-product-server"
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.product_server_cpu
  memory                   = var.product_server_memory

  container_definitions = jsonencode([
    {
      name      = "product-server"
      image     = "${aws_ecr_repository.product_repository.repository_url}:latest"
      essential = true
      
      portMappings = [
        {
          containerPort = var.container_port_product
          hostPort      = var.container_port_product
          protocol      = "tcp"
        }
      ]
      
      environment = [
        {
          name  = "PORT"
          value = tostring(var.container_port_product)
        },
        {
          name  = "NODE_ENV"
          value = "production"
        }
      ]
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.product_server.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
      
      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:${var.container_port_product}/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-product-server-task"
  })
}

# Task Definition for Order Server
resource "aws_ecs_task_definition" "order_server" {
  family                   = "${local.name_prefix}-order-server"
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.order_server_cpu
  memory                   = var.order_server_memory

  container_definitions = jsonencode([
    {
      name      = "order-server"
      image     = "${aws_ecr_repository.order_repository.repository_url}:latest"
      essential = true
      
      portMappings = [
        {
          containerPort = var.container_port_order
          hostPort      = var.container_port_order
          protocol      = "tcp"
        }
      ]
      
      environment = [
        {
          name  = "PORT"
          value = tostring(var.container_port_order)
        },
        {
          name  = "NODE_ENV"
          value = "production"
        }
      ]
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.order_server.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
      
      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:${var.container_port_order}/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-order-server-task"
  })
}

# ECS Service for Product Server
resource "aws_ecs_service" "product_service" {
  name                               = "product-service"
  cluster                            = aws_ecs_cluster.main.id
  task_definition                    = aws_ecs_task_definition.product_server.arn
  desired_count                      = 1
  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200
  launch_type                        = "FARGATE"
  scheduling_strategy                = "REPLICA"
  health_check_grace_period_seconds  = 60

  network_configuration {
    security_groups  = [aws_security_group.ecs_tasks_sg.id]
    subnets          = module.vpc.private_subnets
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = module.product_alb.target_group_arns[0]
    container_name   = "product-server"
    container_port   = var.container_port_product
  }

  lifecycle {
    ignore_changes = [desired_count]
  }

  depends_on = [module.product_alb]

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-product-service"
  })
}

# ECS Service for Order Server
resource "aws_ecs_service" "order_service" {
  name                               = "order-service"
  cluster                            = aws_ecs_cluster.main.id
  task_definition                    = aws_ecs_task_definition.order_server.arn
  desired_count                      = 1
  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200
  launch_type                        = "FARGATE"
  scheduling_strategy                = "REPLICA"
  health_check_grace_period_seconds  = 60

  network_configuration {
    security_groups  = [aws_security_group.ecs_tasks_sg.id]
    subnets          = module.vpc.private_subnets
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = module.order_alb.target_group_arns[0]
    container_name   = "order-server"
    container_port   = var.container_port_order
  }

  lifecycle {
    ignore_changes = [desired_count]
  }

  depends_on = [module.order_alb]

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-order-service"
  })
}

# Auto Scaling for Product Server
resource "aws_appautoscaling_target" "product_server" {
  max_capacity       = 5
  min_capacity       = 1
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.product_service.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "product_server_cpu" {
  name               = "${local.name_prefix}-product-server-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.product_server.resource_id
  scalable_dimension = aws_appautoscaling_target.product_server.scalable_dimension
  service_namespace  = aws_appautoscaling_target.product_server.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 70
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}

# Auto Scaling for Order Server
resource "aws_appautoscaling_target" "order_server" {
  max_capacity       = 5
  min_capacity       = 1
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.order_service.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "order_server_cpu" {
  name               = "${local.name_prefix}-order-server-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.order_server.resource_id
  scalable_dimension = aws_appautoscaling_target.order_server.scalable_dimension
  service_namespace  = aws_appautoscaling_target.order_server.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 70
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}
