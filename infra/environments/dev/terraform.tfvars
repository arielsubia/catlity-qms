aws_region         = "us-east-1"
environment        = "dev"
project_name       = "catlity-qms"
vpc_cidr           = "10.0.0.0/16"
budget_alert_email = "alerts@phildev.com"

# db_username and db_password should be provided via:
# - Environment variables: TF_VAR_db_username, TF_VAR_db_password
# - Or via -var flag at plan/apply time
# NEVER commit credentials to version control
