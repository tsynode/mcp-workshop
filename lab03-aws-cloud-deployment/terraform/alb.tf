module "product_alb" {
  source  = "terraform-aws-modules/alb/aws"
  version = "~> 8.0"

  name = "mcp-prod-alb"

  load_balancer_type = "application"

  vpc_id          = module.vpc.vpc_id
  subnets         = module.vpc.public_subnets
  security_groups = [aws_security_group.alb_sg.id]

  # HTTPS listener with redirect from HTTP
  http_tcp_listeners = [
    {
      port               = 80
      protocol           = "HTTP"
      target_group_index = 0
      action_type        = "redirect"
      redirect = {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }
  ]

  # HTTPS listener
  https_listeners = var.enable_https ? [
    {
      port               = 443
      protocol           = "HTTPS"
      certificate_arn    = var.certificate_arn != "" ? var.certificate_arn : aws_acm_certificate.self_signed_cert[0].arn
      target_group_index = 0
    }
  ] : []

  # Target group for the product server
  target_groups = [
    {
      name                 = "mcp-prod-tg"
      backend_protocol     = "HTTP"
      backend_port         = var.container_port_product
      target_type          = "ip"
      deregistration_delay = 60
      health_check = {
        enabled             = true
        interval            = 30
        path                = var.health_check_path
        port                = "traffic-port"
        healthy_threshold   = 3
        unhealthy_threshold = 3
        timeout             = 6
        protocol            = "HTTP"
        matcher             = "200-299"
      }
    }
  ]

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-product-alb"
  })
}

module "order_alb" {
  source  = "terraform-aws-modules/alb/aws"
  version = "~> 8.0"

  name = "mcp-order-alb"

  load_balancer_type = "application"

  vpc_id          = module.vpc.vpc_id
  subnets         = module.vpc.public_subnets
  security_groups = [aws_security_group.alb_sg.id]

  # HTTP listener with redirect to HTTPS
  http_tcp_listeners = [
    {
      port               = 80
      protocol           = "HTTP"
      target_group_index = 0
      action_type        = "redirect"
      redirect = {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }
  ]

  # HTTPS listener
  https_listeners = var.enable_https ? [
    {
      port               = 443
      protocol           = "HTTPS"
      certificate_arn    = var.certificate_arn != "" ? var.certificate_arn : aws_acm_certificate.self_signed_cert[0].arn
      target_group_index = 0
    }
  ] : []

  # Target group for the order server
  target_groups = [
    {
      name                 = "mcp-order-tg"
      backend_protocol     = "HTTP"
      backend_port         = var.container_port_order
      target_type          = "ip"
      deregistration_delay = 60
      health_check = {
        enabled             = true
        interval            = 30
        path                = var.health_check_path
        port                = "traffic-port"
        healthy_threshold   = 3
        unhealthy_threshold = 3
        timeout             = 6
        protocol            = "HTTP"
        matcher             = "200-299"
      }
    }
  ]

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-order-alb"
  })
}

# Self-signed certificate for development (only used if no certificate ARN is provided)
resource "tls_private_key" "self_signed" {
  count     = var.enable_https && var.certificate_arn == "" ? 1 : 0
  algorithm = "RSA"
}

resource "tls_self_signed_cert" "self_signed" {
  count           = var.enable_https && var.certificate_arn == "" ? 1 : 0
  private_key_pem = tls_private_key.self_signed[0].private_key_pem

  subject {
    common_name  = "mcp-workshop.example.com"
    organization = "MCP Workshop"
  }

  validity_period_hours = 24 * 30 # 30 days

  allowed_uses = [
    "key_encipherment",
    "digital_signature",
    "server_auth",
  ]
}

resource "aws_acm_certificate" "self_signed_cert" {
  count            = var.enable_https && var.certificate_arn == "" ? 1 : 0
  private_key      = tls_private_key.self_signed[0].private_key_pem
  certificate_body = tls_self_signed_cert.self_signed[0].cert_pem

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-self-signed-cert"
  })
}
