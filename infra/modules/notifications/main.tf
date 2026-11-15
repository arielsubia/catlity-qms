data "aws_caller_identity" "current" {}

locals {
  configuration_set_name = "${var.project_name}-${var.environment}-notifications"
  topic_name             = "${var.project_name}-${var.environment}-notification-events"
  table_name             = "${var.project_name}-${var.environment}-notifications"
}

# --- Sandbox sender ---

resource "aws_sesv2_configuration_set" "notifications" {
  configuration_set_name = local.configuration_set_name

  tags = merge(var.tags, {
    Name = local.configuration_set_name
  })
}

resource "aws_sesv2_email_identity" "sender" {
  email_identity         = var.sender_email
  configuration_set_name = aws_sesv2_configuration_set.notifications.configuration_set_name

  tags = merge(var.tags, {
    Name = var.sender_email
  })
}

# --- Delivery events ---

resource "aws_sns_topic" "notification_events" {
  name = local.topic_name

  tags = merge(var.tags, {
    Name = local.topic_name
  })
}

data "aws_iam_policy_document" "notification_events" {
  statement {
    sid       = "AllowSesPublish"
    effect    = "Allow"
    actions   = ["SNS:Publish"]
    resources = [aws_sns_topic.notification_events.arn]

    principals {
      type        = "Service"
      identifiers = ["ses.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }

    condition {
      test     = "ArnEquals"
      variable = "AWS:SourceArn"
      values   = [aws_sesv2_configuration_set.notifications.arn]
    }
  }
}

resource "aws_sns_topic_policy" "notification_events" {
  arn    = aws_sns_topic.notification_events.arn
  policy = data.aws_iam_policy_document.notification_events.json
}

resource "aws_sesv2_configuration_set_event_destination" "notification_events" {
  configuration_set_name = aws_sesv2_configuration_set.notifications.configuration_set_name
  event_destination_name = "notification-events"

  event_destination {
    enabled              = true
    matching_event_types = ["DELIVERY", "BOUNCE", "COMPLAINT", "REJECT"]

    sns_destination {
      topic_arn = aws_sns_topic.notification_events.arn
    }
  }

  depends_on = [aws_sns_topic_policy.notification_events]
}

# --- Email templates ---
# aws_ses_template has no tags argument. common_tags stay on the identity,
# the configuration set, the topic, and the table.

resource "aws_ses_template" "finding_assigned" {
  name    = "finding-assigned"
  subject = "Hallazgo asignado"
  html    = "<p>Hola {{recipient_name}},</p><p>Se te asignó el hallazgo {{finding_title}} en la auditoría {{audit_name}}.</p><p><a href=\"{{action_url}}\">Ver el hallazgo</a></p>"
  text    = "Hola {{recipient_name}},\n\nSe te asignó el hallazgo {{finding_title}} en la auditoría {{audit_name}}.\n\nVer el hallazgo: {{action_url}}\n"
}

resource "aws_ses_template" "corrective_action_overdue" {
  name    = "corrective-action-overdue"
  subject = "Acción correctiva vencida"
  html    = "<p>Hola {{recipient_name}},</p><p>La acción {{action_description}} venció el {{due_date}}.</p><p><a href=\"{{action_url}}\">Ver la acción</a></p>"
  text    = "Hola {{recipient_name}},\n\nLa acción {{action_description}} venció el {{due_date}}.\n\nVer la acción: {{action_url}}\n"
}

# --- Notification history ---

resource "aws_dynamodb_table" "notifications" {
  name         = local.table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "tenant_id"
  range_key    = "notification_id"

  attribute {
    name = "tenant_id"
    type = "S"
  }

  attribute {
    name = "notification_id"
    type = "S"
  }

  # AWS owned key is the default and has no monthly CMK charge.
  point_in_time_recovery {
    enabled = false
  }

  deletion_protection_enabled = false

  tags = merge(var.tags, {
    Name = local.table_name
  })
}
