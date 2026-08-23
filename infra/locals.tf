locals {
  common_tags = {
    Project     = "catlity-qms"
    Environment = var.environment
    ManagedBy   = "terraform"
    Owner       = "phil-dev"
  }
}
