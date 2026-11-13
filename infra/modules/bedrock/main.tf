data "aws_caller_identity" "current" {}

locals {
  kb_role_name          = "${var.project_name}-${var.environment}-bedrock-kb"
  agent_role_name       = "${var.project_name}-${var.environment}-bedrock-agent"
  vector_bucket         = "${var.project_name}-${var.environment}-vectors"
  embedding_model       = "amazon.titan-embed-text-v2:0"
  embedding_dims        = 1024
  response_profile      = "us.amazon.nova-micro-v1:0"
  harness_name          = "Normative_Advisor"
  report_harness_name   = "Report_Generator"
  report_role_name      = "${var.project_name}-${var.environment}-bedrock-report"
  report_profile        = "us.amazon.nova-micro-v1:0"
  # Literal ARN so this harness does not depend on the normative gateway
  # resource. A reference would pull the retrieve Lambda into the apply, and
  # the local zip hash does not match the published function.
  report_gateway_arn    = "arn:aws:bedrock-agentcore:${var.aws_region}:${data.aws_caller_identity.current.account_id}:gateway/catlity-qms-dev-normative-gociabb2cb"
  report_instruction    = "You are Report Generator for Catlity QMS. Write an audit report from the findings in the user message. Use these four headings, in this order: Resumen, Hallazgos, Conclusiones, Recomendaciones. If the findings are written in Spanish, write the report in Spanish. If they are written in English, write the report in English. Cite the file name of each study note you use, exactly as it appears in the passage. Do not translate file names. The notes are original study summaries in English. They are not the official text of ISO 9001, IATF 16949, or GMP. Do not invent clause numbers or requirements. If no passage covers a finding, say so in that finding and do not fill the gap from general knowledge. A Spanish finding can miss an English note. Treat a missing passage as no citation."
  gateway_name          = "${var.project_name}-${var.environment}-normative"
  gateway_role_name     = "${var.project_name}-${var.environment}-bedrock-gateway"
  retrieve_role_name    = "${var.project_name}-${var.environment}-bedrock-retrieve"
  retrieve_function     = "${var.project_name}-${var.environment}-normative-retrieve"
  normative_instruction = "You are Normative Advisor for Catlity QMS. Answer only from the study notes returned by the study-notes retrieval tool. Cite the file name of each note you use. The notes are original study summaries. They are not the official text of ISO 9001, IATF 16949, or GMP. If the notes do not cover the question, say so. Do not invent clause numbers or requirements. Call the tool once per corpus. The corpus argument is common, automotive, or pharmaceutical. Use common for every question. Also use automotive or pharmaceutical only when the question names that industry."

  corpora = {
    common = {
      prefix      = "knowledge-base/common/"
      description = "ISO 9001 study notes shared by every tenant."
    }
    automotive = {
      prefix      = "knowledge-base/automotive/"
      description = "IATF 16949 study notes for automotive tenants."
    }
    pharmaceutical = {
      prefix      = "knowledge-base/pharmaceutical/"
      description = "GMP study notes for pharmaceutical tenants."
    }
  }
}

# --- Roles Bedrock assumes ---

data "aws_iam_policy_document" "kb_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["bedrock.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:knowledge-base/*"]
    }
  }
}

resource "aws_iam_role" "knowledge_base" {
  name               = local.kb_role_name
  assume_role_policy = data.aws_iam_policy_document.kb_assume.json

  tags = merge(var.tags, {
    Name = local.kb_role_name
  })
}

data "aws_iam_policy_document" "kb" {
  statement {
    sid       = "ReadStudyNotes"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [var.knowledge_base_bucket_arn]
  }

  statement {
    sid       = "GetStudyNotes"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${var.knowledge_base_bucket_arn}/knowledge-base/*"]
  }

  statement {
    sid     = "EmbedStudyNotes"
    effect  = "Allow"
    actions = ["bedrock:InvokeModel"]
    resources = [
      "arn:aws:bedrock:${var.aws_region}::foundation-model/${local.embedding_model}",
    ]
  }

  statement {
    sid    = "WriteVectorIndex"
    effect = "Allow"
    actions = [
      "s3vectors:GetIndex",
      "s3vectors:PutVectors",
      "s3vectors:GetVectors",
      "s3vectors:DeleteVectors",
      "s3vectors:QueryVectors",
    ]
    resources = [for index in aws_s3vectors_index.corpus : index.index_arn]
  }
}

resource "aws_iam_role_policy" "knowledge_base" {
  name   = "${local.kb_role_name}-access"
  role   = aws_iam_role.knowledge_base.id
  policy = data.aws_iam_policy_document.kb.json
}

# The classic agent role already exists. AgentCore assumes the same role.
# Bedrock Agents classic no longer accepts CreateAgent on this account.
data "aws_iam_policy_document" "agent_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["bedrock-agentcore.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "agent" {
  name               = local.agent_role_name
  assume_role_policy = data.aws_iam_policy_document.agent_assume.json

  tags = merge(var.tags, {
    Name = local.agent_role_name
  })
}

data "aws_iam_policy_document" "agent" {
  statement {
    sid    = "InvokeResponseModel"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
    ]
    resources = [
      "arn:aws:bedrock:*::foundation-model/amazon.nova-micro-v1:0",
      "arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:inference-profile/${local.response_profile}",
    ]
  }

  statement {
    sid       = "ReadInferenceProfile"
    effect    = "Allow"
    actions   = ["bedrock:GetInferenceProfile"]
    resources = ["arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:inference-profile/${local.response_profile}"]
  }

  statement {
    sid       = "InvokeStudyNotesGateway"
    effect    = "Allow"
    actions   = ["bedrock-agentcore:InvokeGateway"]
    resources = [aws_bedrockagentcore_gateway.normative.gateway_arn]
  }

  # The managed harness image is public. The runtime pulls it when a session starts.
  statement {
    sid       = "PullManagedHarnessImage"
    effect    = "Allow"
    actions   = ["ecr-public:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid       = "BearerTokenForPublicEcr"
    effect    = "Allow"
    actions   = ["sts:GetServiceBearerToken"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "sts:AWSServiceName"
      values   = ["ecr-public.amazonaws.com"]
    }
  }

  statement {
    sid    = "WriteHarnessLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:DescribeLogStreams",
    ]
    resources = ["arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"]
  }

  statement {
    sid       = "DescribeHarnessLogGroups"
    effect    = "Allow"
    actions   = ["logs:DescribeLogGroups"]
    resources = ["arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:*"]
  }

  statement {
    sid    = "WriteHarnessLogStreams"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"]
  }

  statement {
    sid       = "AllowHarnessLogDelivery"
    effect    = "Allow"
    actions   = ["logs:PutResourcePolicy"]
    resources = ["*"]
  }

  statement {
    sid       = "PublishHarnessMetrics"
    effect    = "Allow"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["bedrock-agentcore"]
    }
  }

  statement {
    sid    = "TraceHarnessSessions"
    effect = "Allow"
    actions = [
      "xray:PutTraceSegments",
      "xray:PutTelemetryRecords",
      "xray:GetSamplingRules",
      "xray:GetSamplingTargets",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "GetHarnessWorkloadToken"
    effect = "Allow"
    actions = [
      "bedrock-agentcore:GetWorkloadAccessToken",
      "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
    ]
    resources = [
      "arn:aws:bedrock-agentcore:${var.aws_region}:${data.aws_caller_identity.current.account_id}:workload-identity-directory/default",
      "arn:aws:bedrock-agentcore:${var.aws_region}:${data.aws_caller_identity.current.account_id}:workload-identity-directory/default/workload-identity/harness_${local.harness_name}-*",
    ]
  }
}

resource "aws_iam_role_policy" "agent" {
  name   = "${local.agent_role_name}-access"
  role   = aws_iam_role.agent.id
  policy = data.aws_iam_policy_document.agent.json
}

# --- Vector store ---

resource "aws_s3vectors_vector_bucket" "normative" {
  vector_bucket_name = local.vector_bucket

  tags = merge(var.tags, {
    Name = local.vector_bucket
  })
}

resource "aws_s3vectors_index" "corpus" {
  for_each = local.corpora

  index_name         = each.key
  vector_bucket_name = aws_s3vectors_vector_bucket.normative.vector_bucket_name
  data_type          = "float32"
  dimension          = local.embedding_dims
  distance_metric    = "euclidean"

  tags = merge(var.tags, {
    Name = each.key
  })
}

# --- One knowledge base per corpus ---

resource "aws_bedrockagent_knowledge_base" "corpus" {
  for_each = local.corpora

  name     = "${var.project_name}-${var.environment}-${each.key}"
  role_arn = aws_iam_role.knowledge_base.arn

  knowledge_base_configuration {
    type = "VECTOR"

    vector_knowledge_base_configuration {
      embedding_model_arn = "arn:aws:bedrock:${var.aws_region}::foundation-model/${local.embedding_model}"

      embedding_model_configuration {
        bedrock_embedding_model_configuration {
          dimensions          = local.embedding_dims
          embedding_data_type = "FLOAT32"
        }
      }
    }
  }

  storage_configuration {
    type = "S3_VECTORS"

    s3_vectors_configuration {
      index_arn = aws_s3vectors_index.corpus[each.key].index_arn
    }
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-${each.key}"
  })

  depends_on = [aws_iam_role_policy.knowledge_base]
}

resource "aws_bedrockagent_data_source" "corpus" {
  for_each = local.corpora

  knowledge_base_id = aws_bedrockagent_knowledge_base.corpus[each.key].id
  name              = "s3-${each.key}"
  description       = each.value.description

  data_source_configuration {
    type = "S3"

    s3_configuration {
      bucket_arn         = var.knowledge_base_bucket_arn
      inclusion_prefixes = [each.value.prefix]
    }
  }

  # The default chunk is about 300 tokens. Each note is under 2 KB, so that
  # text plus the filterable metadata Bedrock stores with the chunk exceeds
  # the 2048-byte S3 Vectors limit and the ingestion job stores nothing.
  vector_ingestion_configuration {
    chunking_configuration {
      chunking_strategy = "FIXED_SIZE"

      fixed_size_chunking_configuration {
        max_tokens         = 120
        overlap_percentage = 20
      }
    }
  }
}

# --- Retrieval ---
# The AgentCore knowledge-base connector accepts only MANAGED knowledge bases.
# These three are VECTOR bases on S3 Vectors, so a Lambda calls Retrieve.

data "archive_file" "retrieve" {
  type        = "zip"
  source_file = "${path.module}/retrieve/handler.py"
  output_path = "${path.module}/retrieve.zip"
}

data "aws_iam_policy_document" "retrieve_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "retrieve" {
  name               = local.retrieve_role_name
  assume_role_policy = data.aws_iam_policy_document.retrieve_assume.json

  tags = merge(var.tags, {
    Name = local.retrieve_role_name
  })
}

data "aws_iam_policy_document" "retrieve" {
  statement {
    sid       = "RetrieveStudyNotes"
    effect    = "Allow"
    actions   = ["bedrock:Retrieve"]
    resources = [for kb in aws_bedrockagent_knowledge_base.corpus : kb.arn]
  }

  statement {
    sid    = "WriteRetrieveLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = [
      "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${local.retrieve_function}",
      "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${local.retrieve_function}:*",
    ]
  }
}

resource "aws_iam_role_policy" "retrieve" {
  name   = "${local.retrieve_role_name}-access"
  role   = aws_iam_role.retrieve.id
  policy = data.aws_iam_policy_document.retrieve.json
}

resource "aws_lambda_function" "retrieve" {
  function_name    = local.retrieve_function
  role             = aws_iam_role.retrieve.arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.retrieve.output_path
  source_code_hash = data.archive_file.retrieve.output_base64sha256
  timeout          = 15
  memory_size      = 128

  environment {
    variables = {
      KB_IDS = jsonencode({
        for key, kb in aws_bedrockagent_knowledge_base.corpus : key => kb.id
      })
    }
  }

  tags = merge(var.tags, {
    Name = local.retrieve_function
  })

  depends_on = [aws_iam_role_policy.retrieve]
}

data "aws_iam_policy_document" "gateway_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["bedrock-agentcore.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "gateway" {
  name               = local.gateway_role_name
  assume_role_policy = data.aws_iam_policy_document.gateway_assume.json

  tags = merge(var.tags, {
    Name = local.gateway_role_name
  })
}

data "aws_iam_policy_document" "gateway" {
  statement {
    sid       = "InvokeRetrieveFunction"
    effect    = "Allow"
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.retrieve.arn]
  }
}

resource "aws_iam_role_policy" "gateway" {
  name   = "${local.gateway_role_name}-access"
  role   = aws_iam_role.gateway.id
  policy = data.aws_iam_policy_document.gateway.json
}

resource "aws_bedrockagentcore_gateway" "normative" {
  name            = local.gateway_name
  role_arn        = aws_iam_role.gateway.arn
  authorizer_type = "AWS_IAM"
  protocol_type   = "MCP"
  description     = "Study-note retrieval for Normative Advisor"

  tags = merge(var.tags, {
    Name = local.gateway_name
  })

  depends_on = [aws_iam_role_policy.gateway]
}

resource "aws_bedrockagentcore_gateway_target" "study_notes" {
  name               = "study-notes"
  gateway_identifier = aws_bedrockagentcore_gateway.normative.gateway_id
  description        = "Retrieve passages from one normative knowledge base"

  credential_provider_configuration {
    gateway_iam_role {}
  }

  target_configuration {
    mcp {
      lambda {
        lambda_arn = aws_lambda_function.retrieve.arn

        tool_schema {
          inline_payload {
            name        = "retrieve_study_notes"
            description = "Search one corpus of normative study notes and return the matching passages with their file names."

            input_schema {
              type        = "object"
              description = "Corpus and question to search"

              property {
                name        = "corpus"
                type        = "string"
                description = "Which notes to search: common, automotive, or pharmaceutical."
                required    = true
              }

              property {
                name        = "query"
                type        = "string"
                description = "The question to search for in that corpus."
                required    = true
              }
            }
          }
        }
      }
    }
  }
}

# --- Normative Advisor ---
# Harness names allow letters, digits, and underscores. Memory stays off so an
# idle harness does not keep a memory store.

resource "aws_bedrockagentcore_harness" "normative" {
  harness_name       = local.harness_name
  execution_role_arn = aws_iam_role.agent.arn
  allowed_tools      = ["*"]
  max_iterations     = 6
  timeout_seconds    = 60

  model {
    bedrock_model_config {
      model_id    = local.response_profile
      temperature = 0
    }
  }

  system_prompt {
    text = local.normative_instruction
  }

  memory {
    disabled {}
  }

  tool {
    type = "agentcore_gateway"
    name = "study_notes"

    config {
      agentcore_gateway {
        gateway_arn = aws_bedrockagentcore_gateway.normative.gateway_arn

        outbound_auth {
          aws_iam = true
        }
      }
    }
  }

  tags = merge(var.tags, {
    Name = local.harness_name
  })

  depends_on = [
    aws_iam_role_policy.agent,
    aws_bedrockagentcore_gateway_target.study_notes,
  ]
}

# --- Report Generator ---
# Second harness. It reuses the study-note gateway and does not change
# Normative_Advisor. Its model id is report_profile, not response_profile.

resource "aws_iam_role" "report" {
  name               = local.report_role_name
  assume_role_policy = data.aws_iam_policy_document.agent_assume.json

  tags = merge(var.tags, {
    Name = local.report_role_name
  })
}

data "aws_iam_policy_document" "report" {
  statement {
    sid    = "InvokeResponseModel"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
    ]
    resources = [
      "arn:aws:bedrock:*::foundation-model/amazon.nova-micro-v1:0",
      "arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:inference-profile/${local.report_profile}",
    ]
  }

  statement {
    sid       = "ReadInferenceProfile"
    effect    = "Allow"
    actions   = ["bedrock:GetInferenceProfile"]
    resources = ["arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:inference-profile/${local.report_profile}"]
  }

  statement {
    sid       = "InvokeStudyNotesGateway"
    effect    = "Allow"
    actions   = ["bedrock-agentcore:InvokeGateway"]
    resources = [local.report_gateway_arn]
  }

  statement {
    sid       = "PullManagedHarnessImage"
    effect    = "Allow"
    actions   = ["ecr-public:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid       = "BearerTokenForPublicEcr"
    effect    = "Allow"
    actions   = ["sts:GetServiceBearerToken"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "sts:AWSServiceName"
      values   = ["ecr-public.amazonaws.com"]
    }
  }

  statement {
    sid    = "WriteHarnessLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:DescribeLogStreams",
    ]
    resources = ["arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"]
  }

  statement {
    sid       = "DescribeHarnessLogGroups"
    effect    = "Allow"
    actions   = ["logs:DescribeLogGroups"]
    resources = ["arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:*"]
  }

  statement {
    sid    = "WriteHarnessLogStreams"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"]
  }

  statement {
    sid       = "AllowHarnessLogDelivery"
    effect    = "Allow"
    actions   = ["logs:PutResourcePolicy"]
    resources = ["*"]
  }

  statement {
    sid       = "PublishHarnessMetrics"
    effect    = "Allow"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["bedrock-agentcore"]
    }
  }

  statement {
    sid    = "TraceHarnessSessions"
    effect = "Allow"
    actions = [
      "xray:PutTraceSegments",
      "xray:PutTelemetryRecords",
      "xray:GetSamplingRules",
      "xray:GetSamplingTargets",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "GetHarnessWorkloadToken"
    effect = "Allow"
    actions = [
      "bedrock-agentcore:GetWorkloadAccessToken",
      "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
    ]
    resources = [
      "arn:aws:bedrock-agentcore:${var.aws_region}:${data.aws_caller_identity.current.account_id}:workload-identity-directory/default",
      "arn:aws:bedrock-agentcore:${var.aws_region}:${data.aws_caller_identity.current.account_id}:workload-identity-directory/default/workload-identity/harness_${local.report_harness_name}-*",
    ]
  }
}

resource "aws_iam_role_policy" "report" {
  name   = "${local.report_role_name}-access"
  role   = aws_iam_role.report.id
  policy = data.aws_iam_policy_document.report.json
}

resource "aws_bedrockagentcore_harness" "report" {
  harness_name       = local.report_harness_name
  execution_role_arn = aws_iam_role.report.arn
  allowed_tools      = ["*"]
  max_iterations     = 4
  timeout_seconds    = 60

  model {
    bedrock_model_config {
      model_id    = local.report_profile
      temperature = 0
    }
  }

  system_prompt {
    text = local.report_instruction
  }

  memory {
    disabled {}
  }

  tool {
    type = "agentcore_gateway"
    name = "study_notes"

    config {
      agentcore_gateway {
        gateway_arn = local.report_gateway_arn

        outbound_auth {
          aws_iam = true
        }
      }
    }
  }

  tags = merge(var.tags, {
    Name = local.report_harness_name
  })

  depends_on = [aws_iam_role_policy.report]
}
