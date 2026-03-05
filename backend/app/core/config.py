from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_env: str = "development"
    app_name: str = "Risk Manager Pro"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:5173"]

    # Session & Auth Security
    session_timeout_minutes: int = 60
    auth_lockout_threshold: int = 5
    auth_lockout_window_minutes: int = 15

    # Rate Limiting
    rate_limit_default: str = "60/minute"
    rate_limit_auth: str = "20/minute"
    rate_limit_ai: str = "20/minute"

    # Database — no default; must be set via env var or .env file
    database_url: str = ""

    # Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_deployment_name: str = "gpt-4o"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"
    azure_openai_api_version: str = "2024-10-21"

    # Azure AI Search
    azure_search_endpoint: str = ""
    azure_search_index_name: str = "rmp-documents"

    # Azure Blob Storage
    azure_storage_account_name: str = ""
    azure_storage_container_name: str = "documents"
    azure_storage_audit_container: str = "audit-logs"
    azure_storage_connection_string: str = ""

    # Azure AD / Entra ID
    azure_ad_tenant_id: str = ""
    azure_ad_client_id: str = ""
    azure_ad_authority: str = ""

    @model_validator(mode="after")
    def _validate_database_url(self) -> "Settings":
        if not self.database_url:
            raise ValueError(
                "DATABASE_URL is required. Set it via environment variable or .env file."
            )
        return self

    @property
    def azure_ad_issuer(self) -> str:
        return f"https://login.microsoftonline.com/{self.azure_ad_tenant_id}/v2.0"

    @property
    def azure_ad_jwks_url(self) -> str:
        return f"https://login.microsoftonline.com/{self.azure_ad_tenant_id}/discovery/v2.0/keys"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


settings = Settings()
