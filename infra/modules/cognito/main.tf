# --- Cognito User Pool ---

resource "aws_cognito_user_pool" "main" {
  name = "${var.project_name}-${var.environment}-user-pool"

  # Users sign in with their email address
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 7
  }

  # Standard attribute
  schema {
    name                     = "email"
    attribute_data_type      = "String"
    required                 = true
    mutable                  = true
    developer_only_attribute = false

    string_attribute_constraints {
      min_length = 5
      max_length = 255
    }
  }

  # Custom attribute: tenant_id (multi-tenant isolation)
  schema {
    name                     = "tenant_id"
    attribute_data_type      = "String"
    required                 = false
    mutable                  = true
    developer_only_attribute = false

    string_attribute_constraints {
      min_length = 1
      max_length = 36
    }
  }

  # Custom attribute: role (application-level role)
  schema {
    name                     = "role"
    attribute_data_type      = "String"
    required                 = false
    mutable                  = true
    developer_only_attribute = false

    string_attribute_constraints {
      min_length = 1
      max_length = 50
    }
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  admin_create_user_config {
    allow_admin_create_user_only = false
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-user-pool"
  })
}

# --- User Pool Groups (application roles) ---

resource "aws_cognito_user_group" "admin" {
  name         = "admin"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Tenant administrators with full access"
  precedence   = 1
}

resource "aws_cognito_user_group" "qa_manager" {
  name         = "qa_manager"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Quality assurance managers"
  precedence   = 2
}

resource "aws_cognito_user_group" "auditor" {
  name         = "auditor"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Auditors who conduct audits and register findings"
  precedence   = 3
}

resource "aws_cognito_user_group" "auditee" {
  name         = "auditee"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Auditees who respond to findings and corrective actions"
  precedence   = 4
}

resource "aws_cognito_user_group" "lead_auditor" {
  name         = "lead_auditor"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Heads of the internal audit function who assign auditors"
  precedence   = 5
}

# --- App Client (frontend SPA, no client secret for public client) ---

resource "aws_cognito_user_pool_client" "frontend" {
  name         = "${var.project_name}-${var.environment}-frontend-client"
  user_pool_id = aws_cognito_user_pool.main.id

  generate_secret = false

  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_PASSWORD_AUTH",
  ]

  supported_identity_providers = ["COGNITO"]

  callback_urls = var.callback_urls
  logout_urls   = var.logout_urls

  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["email", "openid", "profile"]
  allowed_oauth_flows_user_pool_client = true

  access_token_validity  = 1
  id_token_validity      = 1
  refresh_token_validity = 30

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  prevent_user_existence_errors = "ENABLED"

  read_attributes = [
    "email",
    "email_verified",
    "custom:tenant_id",
    "custom:role",
  ]

  # Tenant and role are server-assigned. The app client must not write them.
  write_attributes = [
    "email",
  ]
}

# --- Hosted UI domain (used by the OAuth code flow) ---

resource "aws_cognito_user_pool_domain" "main" {
  domain       = "${var.project_name}-${var.environment}"
  user_pool_id = aws_cognito_user_pool.main.id
}
