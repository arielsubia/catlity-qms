from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "Catlity QMS"
    app_version: str = "0.1.0"
    debug: bool = False

    # Database
    database_url: str = "postgresql://catlity:catlity_dev@localhost:5432/catlity_qms"

    # AWS
    aws_region: str = "us-east-1"

    # Cognito (placeholder for Task 4)
    cognito_user_pool_id: str = ""
    cognito_app_client_id: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
