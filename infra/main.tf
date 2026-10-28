module "networking" {
  source = "./modules/networking"

  vpc_cidr     = var.vpc_cidr
  project_name = var.project_name
  environment  = var.environment
  tags         = local.common_tags
}

module "database" {
  source = "./modules/database"

  project_name          = var.project_name
  environment           = var.environment
  private_subnet_ids    = module.networking.private_subnet_ids
  rds_security_group_id = module.networking.rds_security_group_id
  instance_class        = "db.t3.micro"
  db_username           = var.db_username
  db_password           = var.db_password
  tags                  = local.common_tags
}

module "cognito" {
  source = "./modules/cognito"

  project_name  = var.project_name
  environment   = var.environment
  callback_urls = var.cognito_callback_urls
  logout_urls   = var.cognito_logout_urls
  tags          = local.common_tags
}

module "cost" {
  source = "./modules/cost"

  project_name          = var.project_name
  environment           = var.environment
  monthly_budget_amount = "50"
  alert_email           = var.budget_alert_email
  tags                  = local.common_tags
}

module "evidence" {
  source = "./modules/evidence"

  project_name = var.project_name
  environment  = var.environment
  tags         = local.common_tags
}
