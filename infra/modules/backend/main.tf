data "aws_caller_identity" "current" {}

locals {
  repository_name = "${var.project_name}-${var.environment}-backend"
  cluster_name    = "${var.project_name}-${var.environment}"
  service_name    = "${var.project_name}-${var.environment}-backend"
  log_group_name  = "/ecs/${var.project_name}-${var.environment}-backend"
  account_id      = data.aws_caller_identity.current.account_id

  # Dev uses Spot. Any other environment stays on on-demand Fargate.
  capacity_provider = var.environment == "dev" ? "FARGATE_SPOT" : "FARGATE"
}

# --- Image registry ---

resource "aws_ecr_repository" "backend" {
  name                 = local.repository_name
  image_tag_mutability = "MUTABLE"
  force_delete         = var.environment == "dev"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = merge(var.tags, {
    Name = local.repository_name
  })
}

resource "aws_ecr_lifecycle_policy" "backend" {
  repository = aws_ecr_repository.backend.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep the last 5 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 5
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# --- Logs ---

resource "aws_cloudwatch_log_group" "backend" {
  name              = local.log_group_name
  retention_in_days = 7

  tags = merge(var.tags, {
    Name = local.log_group_name
  })
}

# --- Cluster ---

resource "aws_ecs_cluster" "backend" {
  name = local.cluster_name

  setting {
    name  = "containerInsights"
    value = "disabled"
  }

  tags = merge(var.tags, {
    Name = local.cluster_name
  })
}

resource "aws_ecs_cluster_capacity_providers" "backend" {
  cluster_name       = aws_ecs_cluster.backend.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    capacity_provider = local.capacity_provider
    weight            = 1
    base              = 0
  }
}

# --- Task and service ---

resource "aws_ecs_task_definition" "backend" {
  family                   = local.service_name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name      = "backend"
      image     = "${aws_ecr_repository.backend.repository_url}:latest"
      essential = true
      portMappings = [
        {
          containerPort = 8000
          hostPort      = 8000
          protocol      = "tcp"
        }
      ]
      healthCheck = {
        command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')\""]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.backend.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "backend"
        }
      }
      environment = [
        {
          name  = "AWS_DEFAULT_REGION"
          value = var.aws_region
        }
      ]
    }
  ])

  tags = merge(var.tags, {
    Name = local.service_name
  })
}

resource "aws_ecs_service" "backend" {
  name            = local.service_name
  cluster         = aws_ecs_cluster.backend.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = var.desired_count

  # One task only. The old task stops before the new one starts, so a deploy
  # does not run two public IPv4 addresses at once.
  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  capacity_provider_strategy {
    capacity_provider = local.capacity_provider
    weight            = 1
    base              = 0
  }

  network_configuration {
    subnets          = var.public_subnet_ids
    security_groups  = [var.ecs_security_group_id]
    assign_public_ip = true
  }

  tags = merge(var.tags, {
    Name = local.service_name
  })

  depends_on = [
    aws_ecs_cluster_capacity_providers.backend,
    aws_iam_role_policy.execution,
  ]
}
