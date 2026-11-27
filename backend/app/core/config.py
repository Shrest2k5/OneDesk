from typing import List, Union
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_postgres_url(url: str, driver: str) -> str:
    """Return a PostgreSQL URL using the driver required by the caller."""
    supported_prefixes = (
        "postgres://",
        "postgresql://",
        "postgresql+asyncpg://",
        "postgresql+psycopg2://",
    )
    if not url.startswith(supported_prefixes):
        return url
    return f"postgresql+{driver}://" + url.split("://", 1)[1]


class Settings(BaseSettings):
    # Application Info
    PROJECT_NAME: str = "OneDesk"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"

    # Security & JWT
    SECRET_KEY: str | None = None
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"

    # Data Encryption Key (Fernet 32 url-safe base64 bytes for encrypting OAuth tokens at rest)
    ENCRYPTION_KEY: str | None = None

    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str | None = None
    POSTGRES_DB: str = "onedesk_db"

    DATABASE_URL: str | None = None
    DATABASE_URL_SYNC: str | None = None

    # Redis & Celery
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_URL: str | None = None
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None

    # Zoho OAuth 2.0 Credentials
    ZOHO_CLIENT_ID: str | None = None
    ZOHO_CLIENT_SECRET: str | None = None
    ZOHO_REDIRECT_URI: str | None = None
    ZOHO_SCOPES: str = "ZohoCRM.modules.ALL,ZohoCRM.settings.ALL,ZohoCRM.org.READ"
    ZOHO_DEFAULT_ACCOUNTS_URL: str = "https://accounts.zoho.com"

    # Zoho Books OAuth 2.0 credentials. Keep these separate from CRM because
    # Zoho OAuth clients and redirect URIs may be registered independently.
    ZOHO_BOOKS_CLIENT_ID: str | None = None
    ZOHO_BOOKS_CLIENT_SECRET: str | None = None
    ZOHO_BOOKS_REDIRECT_URI: str | None = None
    ZOHO_BOOKS_SCOPES: str = (
        "ZohoBooks.settings.READ,ZohoBooks.contacts.READ,ZohoBooks.invoices.READ,"
        "ZohoBooks.bills.READ,ZohoBooks.expenses.READ,ZohoBooks.customerpayments.READ,"
        "ZohoBooks.vendorpayments.READ,ZohoBooks.estimates.READ,ZohoBooks.creditnotes.READ"
        ",ZohoBooks.debitnotes.READ,ZohoBooks.invoices.READ,ZohoBooks.banking.READ"
    )

    # Microsoft Dynamics 365 Business Central OAuth 2.0 credentials.
    # The tenant value may be a directory tenant ID/domain, or a supported
    # Microsoft authority alias such as "organizations".
    BUSINESS_CENTRAL_TENANT_ID: str = "organizations"
    BUSINESS_CENTRAL_AUTHORITY_URL: str = "https://login.microsoftonline.com"
    BUSINESS_CENTRAL_CLIENT_ID: str | None = None
    BUSINESS_CENTRAL_CLIENT_SECRET: str | None = None
    BUSINESS_CENTRAL_REDIRECT_URI: str | None = None
    BUSINESS_CENTRAL_SCOPES: str = (
        "openid profile email offline_access "
        "https://api.businesscentral.dynamics.com/Financials.ReadWrite.All"
    )
    BUSINESS_CENTRAL_API_BASE_URL: str = "https://api.businesscentral.dynamics.com"
    BUSINESS_CENTRAL_ADMIN_API_VERSION: str = "v2.29"

    # Public application URL used after a provider has completed an OAuth callback.
    # This is deliberately separate from ZOHO_REDIRECT_URI: Zoho must always send
    # authorization codes to the backend callback, where they can be validated and
    # exchanged without exposing credentials to the browser application.
    # Local default; production validation still requires an explicit environment value.
    FRONTEND_BASE_URL: str | None = "http://localhost:3000"

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    @model_validator(mode="after")
    def validate_and_normalize_configuration(self):
        """Normalize Render URLs and fail fast for incomplete production settings."""
        if self.DATABASE_URL:
            self.DATABASE_URL = _normalize_postgres_url(self.DATABASE_URL, "asyncpg")
        if self.DATABASE_URL_SYNC:
            self.DATABASE_URL_SYNC = _normalize_postgres_url(
                self.DATABASE_URL_SYNC, "psycopg2"
            )
        elif self.DATABASE_URL:
            # The application and Alembic use the async URL. Keep the sync URL
            # available for compatibility without requiring a second Render secret.
            self.DATABASE_URL_SYNC = _normalize_postgres_url(
                self.DATABASE_URL, "psycopg2"
            )

        if self.ENVIRONMENT.lower() == "production":
            required = {
                "SECRET_KEY": self.SECRET_KEY,
                "ENCRYPTION_KEY": self.ENCRYPTION_KEY,
                "DATABASE_URL": self.DATABASE_URL,
                "REDIS_URL": self.REDIS_URL,
                "CELERY_BROKER_URL": self.CELERY_BROKER_URL,
                "CELERY_RESULT_BACKEND": self.CELERY_RESULT_BACKEND,
                "FRONTEND_BASE_URL": self.FRONTEND_BASE_URL,
                "BACKEND_CORS_ORIGINS": self.BACKEND_CORS_ORIGINS,
                "ZOHO_CLIENT_ID": self.ZOHO_CLIENT_ID,
                "ZOHO_CLIENT_SECRET": self.ZOHO_CLIENT_SECRET,
                "ZOHO_REDIRECT_URI": self.ZOHO_REDIRECT_URI,
                "ZOHO_BOOKS_CLIENT_ID": self.ZOHO_BOOKS_CLIENT_ID,
                "ZOHO_BOOKS_CLIENT_SECRET": self.ZOHO_BOOKS_CLIENT_SECRET,
                "ZOHO_BOOKS_REDIRECT_URI": self.ZOHO_BOOKS_REDIRECT_URI,
            }
            missing = [name for name, value in required.items() if not value]
            if missing:
                raise ValueError(
                    "Missing required production environment variables: "
                    + ", ".join(missing)
                )
            if self.DEBUG:
                raise ValueError("DEBUG must be false when ENVIRONMENT=production.")
            if len(self.SECRET_KEY) < 32:
                raise ValueError("SECRET_KEY must be at least 32 characters in production.")
            if self.SECRET_KEY == "onedesk-dev-insecure-secret-key-change-in-production-at-least-32-chars":
                raise ValueError("The development SECRET_KEY cannot be used in production.")
            if self.FRONTEND_BASE_URL.startswith("http://localhost"):
                raise ValueError("FRONTEND_BASE_URL must be explicitly set to the production frontend URL.")

        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()

