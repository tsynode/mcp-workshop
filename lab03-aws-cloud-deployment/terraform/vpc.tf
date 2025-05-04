module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  version = "5.0.0"

  name = "${local.name_prefix}-vpc-${random_string.suffix.result}"
  cidr = var.vpc_cidr

  azs             = slice(data.aws_availability_zones.available.names, 0, var.availability_zones_count)
  private_subnets = [for i in range(var.availability_zones_count) : cidrsubnet(var.vpc_cidr, 8, i)]
  public_subnets  = [for i in range(var.availability_zones_count) : cidrsubnet(var.vpc_cidr, 8, i + var.availability_zones_count)]

  # NAT Gateway for private subnets to access internet
  enable_nat_gateway = true
  single_nat_gateway = true

  # DNS settings
  enable_dns_hostnames = true
  enable_dns_support   = true

  # VPC Flow Logs
  enable_flow_log                      = true
  create_flow_log_cloudwatch_log_group = true
  create_flow_log_cloudwatch_iam_role  = true
  flow_log_max_aggregation_interval    = 60

  # Tags
  tags = merge(local.tags, {
    Name = "${local.name_prefix}-vpc"
  })

  public_subnet_tags = {
    "kubernetes.io/role/elb" = 1
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = 1
  }
}

# Security group for ALB
resource "aws_security_group" "alb_sg" {
  name        = "${local.name_prefix}-alb-sg-${random_string.suffix.result}"
  description = "Security group for ALB"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description = "HTTP from internet"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS from internet"
    from_port   = 443
    to_port     = 443
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
    Name = "${local.name_prefix}-alb-sg"
  })
}

# Security group for ECS tasks
resource "aws_security_group" "ecs_tasks_sg" {
  name        = "${local.name_prefix}-ecs-tasks-sg-${random_string.suffix.result}"
  description = "Security group for ECS tasks"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description     = "Allow traffic from ALB"
    from_port       = 0
    to_port         = 65535
    protocol        = "tcp"
    security_groups = [aws_security_group.alb_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-ecs-tasks-sg"
  })
}
