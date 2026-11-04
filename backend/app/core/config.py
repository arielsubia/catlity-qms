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
    evidence_bucket_name: str = "catlity-qms-dev-evidence"
    evidence_table_name: str = "catlity-qms-dev-evidence"

    # Cognito
    cognito_user_pool_id: str = ""
    cognito_app_client_id: str = ""

    # Normative Advisor. These ids already exist in us-east-1.
    normative_harness_arn: str = (
        "arn:aws:bedrock-agentcore:us-east-1:265751834002:"
        "harness/Normative_Advisor-CLJ73dVHYz"
    )
    normative_kb_common_id: str = "OTQJ8TMBNI"
    normative_kb_automotive_id: str = "QWONN58E2H"
    normative_kb_pharmaceutical_id: str = "DX3IVAFQ6K"

    @property
    def cognito_issuer(self) -> str:
        """OpenID Connect issuer URL for the configured user pool."""
        return (
            f"https://cognito-idp.{self.aws_region}.amazonaws.com/"
            f"{self.cognito_user_pool_id}"
        )

    @property
    def cognito_jwks_url(self) -> str:
        """URL of the JSON Web Key Set used to verify token signatures."""
        return f"{self.cognito_issuer}/.well-known/jwks.json"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
