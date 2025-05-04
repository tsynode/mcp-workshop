resource "aws_ecr_repository" "product_repository" {
  name                 = "${local.name_prefix}-product-server"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-product-server-repo"
  })
}

resource "aws_ecr_repository" "order_repository" {
  name                 = "${local.name_prefix}-order-server"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-order-server-repo"
  })
}

# ECR Lifecycle Policy - Keep only the latest 5 images
resource "aws_ecr_lifecycle_policy" "product_lifecycle_policy" {
  repository = aws_ecr_repository.product_repository.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 5 images"
        selection = {
          tagStatus     = "any"
          countType     = "imageCountMoreThan"
          countNumber   = 5
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

resource "aws_ecr_lifecycle_policy" "order_lifecycle_policy" {
  repository = aws_ecr_repository.order_repository.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 5 images"
        selection = {
          tagStatus     = "any"
          countType     = "imageCountMoreThan"
          countNumber   = 5
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
