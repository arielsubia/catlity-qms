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

module "knowledge_base" {
  source = "./modules/knowledge_base"

  project_name = var.project_name
  environment  = var.environment
  tags         = local.common_tags
}

module "bedrock" {
  source = "./modules/bedrock"

  project_name              = var.project_name
  environment               = var.environment
  aws_region                = var.aws_region
  knowledge_base_bucket_arn = module.knowledge_base.bucket_arn
  tags                      = local.common_tags
}

module "notifications" {
  source = "./modules/notifications"

  project_name = var.project_name
  environment  = var.environment
  sender_email = var.ses_sender_email
  tags         = local.common_tags
}

module "quicksight" {
  source = "./modules/quicksight"

  project_name          = var.project_name
  environment           = var.environment
  notification_email    = var.ses_sender_email
  vpc_id                = module.networking.vpc_id
  private_subnet_ids    = module.networking.private_subnet_ids
  rds_security_group_id = module.networking.rds_security_group_id
  rds_host              = module.database.rds_endpoint
  rds_port              = module.database.rds_port
  rds_database          = module.database.rds_db_name
  db_username           = var.db_username
  db_password           = var.db_password
  tags                  = local.common_tags
}
