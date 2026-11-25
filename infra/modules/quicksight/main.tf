data "aws_caller_identity" "current" {}

locals {
  name_prefix   = "${var.project_name}-${var.environment}"
  account_name  = "${var.project_name}-${data.aws_caller_identity.current.account_id}"
  vpc_role_name = "${local.name_prefix}-quicksight-vpc"

  # One row per audit. Findings are optional, so an audit with no finding stays visible.
  compliance_sql = <<-SQL
    SELECT
      a.tenant_id,
      a.id AS audit_id,
      a.status AS audit_status,
      a.planned_date::timestamp AS planned_date,
      f.id AS finding_id,
      f.finding_type,
      f.status AS finding_status,
      f.clause_reference,
      f.created_at AS finding_created_at
    FROM audits a
    LEFT JOIN findings f
      ON f.audit_id = a.id
     AND f.tenant_id = a.tenant_id
  SQL

  # VERSION_1 rules. A null tenant_id grants every row to that QuickSight user.
  rls_sql = <<-SQL
    SELECT user_name AS "UserName", tenant_id
    FROM quicksight_row_access
  SQL
}

# aws_quicksight_account_subscription has no tags argument. common_tags stay
# on the VPC connection, the data source, both datasets, the dashboard, the
# role, and the security groups. The IAM user who applies this resource becomes the
# QuickSight admin. devops-ariel has no console sign-in, so this apply is run
# later with the console IAM user. Readers are invited in the console and are
# not created here.

resource "aws_quicksight_account_subscription" "main" {
  account_name          = local.account_name
  authentication_method = "IAM_AND_QUICKSIGHT"
  edition               = "ENTERPRISE"
  notification_email    = var.notification_email
}

data "aws_iam_policy_document" "quicksight_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["quicksight.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "vpc" {
  name               = local.vpc_role_name
  assume_role_policy = data.aws_iam_policy_document.quicksight_assume.json

  tags = merge(var.tags, {
    Name = local.vpc_role_name
  })
}

# CreateNetworkInterface does not accept a resource ARN for an ENI that does
# not exist yet. QuickSight's own sample keeps these five actions on "*".
data "aws_iam_policy_document" "vpc" {
  statement {
    sid    = "ManageQuickSightNetworkInterfaces"
    effect = "Allow"
    actions = [
      "ec2:CreateNetworkInterface",
      "ec2:ModifyNetworkInterfaceAttribute",
      "ec2:DeleteNetworkInterface",
      "ec2:DescribeSubnets",
      "ec2:DescribeSecurityGroups",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "vpc" {
  name   = local.vpc_role_name
  role   = aws_iam_role.vpc.id
  policy = data.aws_iam_policy_document.vpc.json
}

resource "aws_security_group" "quicksight" {
  name        = "${local.name_prefix}-quicksight-sg"
  description = "QuickSight ENIs that read RDS"
  vpc_id      = var.vpc_id

  egress {
    description     = "PostgreSQL to RDS"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.rds_security_group_id]
  }

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-quicksight-sg"
  })
}

resource "aws_vpc_security_group_ingress_rule" "rds_from_quicksight" {
  security_group_id            = var.rds_security_group_id
  referenced_security_group_id = aws_security_group.quicksight.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  description                  = "PostgreSQL from QuickSight"
  tags                         = var.tags
}

resource "aws_quicksight_vpc_connection" "main" {
  vpc_connection_id  = "${local.name_prefix}-vpc"
  name               = "${local.name_prefix}-vpc"
  role_arn           = aws_iam_role.vpc.arn
  security_group_ids = [aws_security_group.quicksight.id]
  subnet_ids         = var.private_subnet_ids

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-vpc"
  })

  depends_on = [aws_quicksight_account_subscription.main]
}

resource "aws_quicksight_data_source" "postgres" {
  data_source_id = "${local.name_prefix}-postgres"
  name           = "${local.name_prefix}-postgres"
  type           = "POSTGRESQL"

  parameters {
    postgresql {
      host     = var.rds_host
      port     = var.rds_port
      database = var.rds_database
    }
  }

  credentials {
    credential_pair {
      username = var.db_username
      password = var.db_password
    }
  }

  vpc_connection_properties {
    vpc_connection_arn = aws_quicksight_vpc_connection.main.arn
  }

  ssl_properties {
    disable_ssl = false
  }

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-postgres"
  })

  depends_on = [aws_quicksight_account_subscription.main]
}

resource "aws_quicksight_data_set" "rls" {
  data_set_id = "${local.name_prefix}-rls"
  name        = "${local.name_prefix}-rls"
  import_mode = "SPICE"
  use_as      = "RLS_RULES"

  physical_table_map {
    physical_table_map_id = "rls"

    custom_sql {
      data_source_arn = aws_quicksight_data_source.postgres.arn
      name            = "quicksight_row_access"
      sql_query       = local.rls_sql

      columns {
        name = "UserName"
        type = "STRING"
      }

      columns {
        name = "tenant_id"
        type = "STRING"
      }
    }
  }

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-rls"
  })
}

resource "aws_quicksight_data_set" "compliance" {
  data_set_id = "${local.name_prefix}-compliance"
  name        = "${local.name_prefix}-compliance"
  import_mode = "SPICE"

  physical_table_map {
    physical_table_map_id = "compliance"

    custom_sql {
      data_source_arn = aws_quicksight_data_source.postgres.arn
      name            = "compliance"
      sql_query       = local.compliance_sql

      columns {
        name = "tenant_id"
        type = "STRING"
      }

      columns {
        name = "audit_id"
        type = "STRING"
      }

      columns {
        name = "audit_status"
        type = "STRING"
      }

      columns {
        name = "planned_date"
        type = "DATETIME"
      }

      columns {
        name = "finding_id"
        type = "STRING"
      }

      columns {
        name = "finding_type"
        type = "STRING"
      }

      columns {
        name = "finding_status"
        type = "STRING"
      }

      columns {
        name = "clause_reference"
        type = "STRING"
      }

      columns {
        name = "finding_created_at"
        type = "DATETIME"
      }
    }
  }

  row_level_permission_data_set {
    arn               = aws_quicksight_data_set.rls.arn
    permission_policy = "GRANT_ACCESS"
    format_version    = "VERSION_1"
    namespace         = "default"
    status            = "ENABLED"
  }

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-compliance"
  })
}

resource "aws_quicksight_refresh_schedule" "compliance" {
  data_set_id = aws_quicksight_data_set.compliance.data_set_id
  schedule_id = "daily"

  schedule {
    refresh_type = "FULL_REFRESH"

    schedule_frequency {
      interval        = "DAILY"
      time_of_the_day = "10:00"
      timezone        = "UTC"
    }
  }
}

resource "aws_quicksight_refresh_schedule" "rls" {
  data_set_id = aws_quicksight_data_set.rls.data_set_id
  schedule_id = "daily"

  schedule {
    refresh_type = "FULL_REFRESH"

    schedule_frequency {
      interval        = "DAILY"
      time_of_the_day = "10:00"
      timezone        = "UTC"
    }
  }
}
