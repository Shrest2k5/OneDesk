import os
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application Info
    PROJECT_NAME: str = "OneDesk"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Security & JWT
    SECRET_KEY: str = "onedesk-dev-insecure-secret-key-change-in-production-at-least-32-chars"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"

    # Data Encryption Key (Fernet 32 url-safe base64 bytes for encrypting OAuth tokens at rest)
    # Default is provided for local dev/testing if not configured in .env
    ENCRYPTION_KEY: str = "p7X1vY3hTz9_mR8uX0wK2lO5jA6bC4eG7iH9kJ1lM3o="

    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "onedesk_db"

    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/onedesk_db"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://postgres:password@localhost:5432/onedesk_db"

    # Redis & Celery
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Zoho OAuth 2.0 Credentials
    ZOHO_CLIENT_ID: str = "zoho_client_id_placeholder"
    ZOHO_CLIENT_SECRET: str = "zoho_client_secret_placeholder"
    ZOHO_REDIRECT_URI: str = "http://localhost:8000/api/v1/integrations/zoho/callback"
    ZOHO_SCOPES: str = "ZohoCRM.modules.ALL,ZohoCRM.settings.ALL,ZohoCRM.org.READ"
    ZOHO_DEFAULT_ACCOUNTS_URL: str = "https://accounts.zoho.com"

    # Zoho Books OAuth 2.0 credentials. Keep these separate from CRM because
    # Zoho OAuth clients and redirect URIs may be registered independently.
    ZOHO_BOOKS_CLIENT_ID: str = "zoho_books_client_id_placeholder"
    ZOHO_BOOKS_CLIENT_SECRET: str = "zoho_books_client_secret_placeholder"
    ZOHO_BOOKS_REDIRECT_URI: str = "http://localhost:8000/api/v1/integrations/zoho/books/callback"
    ZOHO_BOOKS_SCOPES: str = (
        "ZohoBooks.settings.READ,ZohoBooks.contacts.READ,ZohoBooks.invoices.READ,"
        "ZohoBooks.bills.READ,ZohoBooks.expenses.READ,ZohoBooks.customerpayments.READ,"
        "ZohoBooks.vendorpayments.READ,ZohoBooks.estimates.READ,ZohoBooks.creditnotes.READ"
    )

    # Public application URL used after a provider has completed an OAuth callback.
    # This is deliberately separate from ZOHO_REDIRECT_URI: Zoho must always send
    # authorization codes to the backend callback, where they can be validated and
    # exchanged without exposing credentials to the browser application.
    FRONTEND_BASE_URL: str = "http://localhost:3000"

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()

