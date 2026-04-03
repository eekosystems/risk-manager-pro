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
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from JSON array or comma-separated string."""
        raw = self.cors_origins.strip()
        if raw.startswith("["):
            import json
            return json.loads(raw)
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    # Session & Auth Security
    session_timeout_minutes: int = 60
    auth_lockout_threshold: int = 5
    auth_lockout_window_minutes: int = 15

    # Rate Limiting
    rate_limit_default: str = "200/minute"
    rate_limit_auth: str = "30/minute"
    rate_limit_ai: str = "30/minute"
    rate_limit_storage_uri: str = ""  # Redis URL for multi-instance; empty = in-memory

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

    # Microsoft Graph API
    invitation_redirect_url: str = ""

    # Document processing
    chunk_size_tokens: int = 500
    chunk_overlap_tokens: int = 50
    max_file_size_bytes: int = 50 * 1024 * 1024  # 50 MB
    embedding_batch_size: int = 16
    search_index_batch_size: int = 100

    # HTTP timeouts
    graph_api_timeout: float = 30.0

    # Session management
    last_login_throttle_seconds: int = 300  # 5 minutes
    last_activity_throttle_seconds: int = 300  # 5 minutes

    @model_validator(mode="after")
    def _validate_database_url(self) -> "Settings":
        if not self.database_url:
            raise ValueError(
                "DATABASE_URL is required. Set it via environment variable or .env file."
            )
        # asyncpg doesn't support ?sslmode=... — convert to ?ssl=...
        url = self.database_url
        if "sslmode=" in url:
            url = url.replace("sslmode=require", "ssl=require")
            url = url.replace("sslmode=verify-full", "ssl=verify-full")
            url = url.replace("sslmode=verify-ca", "ssl=verify-ca")
            url = url.replace("sslmode=prefer", "ssl=prefer")
            self.database_url = url
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
