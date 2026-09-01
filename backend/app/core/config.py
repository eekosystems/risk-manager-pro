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

            return list(json.loads(raw))
        return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]

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
    # Comma-separated addresses that are granted platform administration on
    # sign-in. is_platform_admin is otherwise a database-only flag with no way
    # to obtain it through the app, which left a new deployment with no admin
    # at all. Grant-only: removing an address here never revokes access, so it
    # cannot fight the in-app toggle.
    platform_admin_emails: str = ""
    azure_ad_authority: str = ""

    # Microsoft Graph API
    invitation_redirect_url: str = ""

    # Document processing
    chunk_size_tokens: int = 500
    chunk_overlap_tokens: int = 50
    # 2 GB ceiling. The /upload endpoint streams the body straight to Blob in
    # chunks (never buffering the whole file), so it accepts files this large
    # on a small container; the cap is enforced mid-stream.
    max_file_size_bytes: int = 2 * 1024 * 1024 * 1024  # 2 GB
    embedding_batch_size: int = 100
    search_index_batch_size: int = 100
    processing_concurrency: int = 5
    # Large-file guards: above this size we stream-process from disk, skip
    # per-page PDF vision (unbounded GPT-4o cost on huge scanned PDFs), and
    # cap the number of indexed chunks so the search index can't be flooded.
    large_file_threshold_bytes: int = 100 * 1024 * 1024  # 100 MB
    max_indexed_chunks: int = 20_000

    # Killswitch for smart-routing of chat messages to the correct FunctionType.
    # Set to false on the Container App to disable routing without a rebuild
    # if it ever misbehaves in production.
    chat_smart_routing: bool = True

    # Risk-outcome import filter rules
    # When False (default), the importer runs in SHADOW mode: every classification
    # is stamped on each row and logged, but nothing is filtered out. Flip to True
    # to actually drop pre-2018 / 6x6-post-2018 reports and route 4x4-post-2018
    # rows to the flagged-for-review queue.
    risk_import_enforce: bool = False
    # Reports earlier than this year are dropped on import when enforcement is on.
    risk_import_min_year: int = 2018

    # SharePoint / Document Crawler
    sharepoint_tenant_id: str = ""
    sharepoint_client_id: str = ""
    sharepoint_client_secret: str = ""
    sharepoint_site_url: str = "https://faithgroupllc.sharepoint.com/sites/RiskManagerPro"
    # Path inside the primary drive whose children are the airport folders.
    # Supports nested paths (slashes). Graph path lookups are case-insensitive.
    # Leave blank to treat the drive root as the airport folder parent.
    sharepoint_airport_root_folder: str = (
        "RMP Master Directory/Airport - Safety Risk Management Documents"
    )

    # Azure AI Document Intelligence (OCR fallback for scanned PDFs)
    azure_doc_intelligence_endpoint: str = ""
    azure_doc_intelligence_key: str = ""

    # HTTP timeouts
    graph_api_timeout: float = 30.0

    # Azure Communication Services (QA/QC email notifications)
    acs_endpoint: str = ""
    acs_sender_address: str = ""
    acs_reply_to_address: str = ""
    app_public_url: str = ""

    # QA/QC digest worker
    qaqc_digest_send_hour_utc: int = 13  # 08:00 Central, default
    qaqc_digest_enabled: bool = True
    qaqc_preference_token_secret: str = ""

    # Session management
    last_login_throttle_seconds: int = 300  # 5 minutes
    last_activity_throttle_seconds: int = 300  # 5 minutes

    # RBAC enforcement on risks/documents/chat endpoints. Enforced by default;
    # production refuses to boot with it disabled (see validator below). Set
    # RMP_ENFORCE_RBAC=false only in non-prod during a membership-backfill window.
    enforce_rbac: bool = True

    # Azure Monitor / Application Insights
    applicationinsights_connection_string: str = ""
    otel_service_name: str = "risk-manager-pro-api"
    otel_traces_sampler_arg: float = 1.0

    # Audit log WORM export
    audit_blob_circuit_breaker_threshold: int = 5
    audit_blob_circuit_breaker_window_seconds: int = 60

    @model_validator(mode="after")
    def _validate_database_url(self) -> "Settings":
        if not self.database_url:
            raise ValueError(
                "DATABASE_URL is required. Set it via environment variable or .env file."
            )
        url = self.database_url
        # asyncpg doesn't support ?sslmode=... — convert to ?ssl=...
        if "sslmode=" in url:
            url = url.replace("sslmode=require", "ssl=require")
            url = url.replace("sslmode=verify-full", "ssl=verify-full")
            url = url.replace("sslmode=verify-ca", "ssl=verify-ca")
            url = url.replace("sslmode=prefer", "ssl=prefer")
        self.database_url = url
        return self

    @model_validator(mode="after")
    def _enforce_rbac_in_production(self) -> "Settings":
        if self.app_env == "production" and not self.enforce_rbac:
            raise ValueError("enforce_rbac must be true in production (set RMP_ENFORCE_RBAC=true)")
        return self

    @model_validator(mode="after")
    def _validate_preference_token_secret(self) -> "Settings":
        # H-6: the HMAC secret for QA/QC preference tokens defaults to "" and was
        # only checked at first use, so a production deploy with the env var missed
        # (or set to a short/guessable value) would boot cleanly and only fail when
        # the first preference link was clicked. Refuse to boot instead.
        if self.app_env == "production" and len(self.qaqc_preference_token_secret) < 32:
            raise ValueError(
                "qaqc_preference_token_secret must be at least 32 chars in production "
                "(set RMP_QAQC_PREFERENCE_TOKEN_SECRET)"
            )
        return self

    @model_validator(mode="after")
    def _validate_production_safety(self) -> "Settings":
        # Hardening: refuse to boot a production instance with a configuration the
        # security review flagged as silently weakening posture — an unset tenant
        # (the single-tenant JWT assertion can't be enforced) or a wildcard CORS
        # origin. Fail at startup rather than serving in a degraded state.
        if self.app_env != "production":
            return self
        if not self.azure_ad_tenant_id:
            raise ValueError(
                "azure_ad_tenant_id must be set in production (set AZURE_AD_TENANT_ID)"
            )
        if "*" in self.cors_origins:
            raise ValueError(
                "cors_origins must not contain '*' in production "
                "(set CORS_ORIGINS to explicit origins)"
            )
        return self

    @property
    def azure_ad_issuer(self) -> str:
        return f"https://login.microsoftonline.com/{self.azure_ad_tenant_id}/v2.0"

    @property
    def azure_ad_issuer_v1(self) -> str:
        return f"https://sts.windows.net/{self.azure_ad_tenant_id}/"

    @property
    def azure_ad_jwks_url(self) -> str:
        return f"https://login.microsoftonline.com/{self.azure_ad_tenant_id}/discovery/v2.0/keys"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def platform_admin_email_set(self) -> frozenset[str]:
        """Bootstrap platform admins, lowercased for case-insensitive matching."""
        return frozenset(
            part.strip().lower() for part in self.platform_admin_emails.split(",") if part.strip()
        )


settings = Settings()
