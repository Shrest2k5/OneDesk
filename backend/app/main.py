from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import api_router
from app.core.config import settings
from app.core.logging import logger, setup_logging
from app.core.security import sanitize_data, validate_encryption_key
from app.integrations.zoho.exceptions import (
    ZohoAPIError,
    ZohoIntegrationError,
    ZohoOAuthError,
    ZohoRateLimitError,
    ZohoTokenExpiredError,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifespan handler."""
    setup_logging()
    logger.info(f"Starting {settings.PROJECT_NAME} in [{settings.ENVIRONMENT}] mode...")

    # Fast startup validation: verify encryption key is configured and valid Fernet
    try:
        validate_encryption_key()
        logger.info("Fernet token encryption key verified successfully.")
    except Exception as exc:
        logger.critical(f"FATAL: Encryption configuration failed: {exc}")
        raise

    yield
    logger.info(f"Shutting down {settings.PROJECT_NAME}...")


def create_application() -> FastAPI:
    """FastAPI application factory with centralized exception handlers and CORS."""
    application = FastAPI(
        title="OneDesk — Unified ERP Integration Platform",
        description=(
            "Centralized ERP integration platform providing a unified REST API layer "
            "for multi-ERP connectivity, OAuth 2.0 authorization, data retrieval, "
            "and synchronization."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        lifespan=lifespan,
    )

    # Configure CORS
    if settings.BACKEND_CORS_ORIGINS:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # --- Centralized Exception Handlers ---
    @application.exception_handler(ZohoTokenExpiredError)
    async def zoho_token_expired_handler(request: Request, exc: ZohoTokenExpiredError):
        logger.warning(f"Zoho token expired or revoked: {exc}")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "token_expired_or_revoked",
                "message": str(exc),
                "details": sanitize_data(exc.details),
            },
        )

    @application.exception_handler(ZohoRateLimitError)
    async def zoho_rate_limit_handler(request: Request, exc: ZohoRateLimitError):
        logger.warning(f"Zoho rate limit hit: {exc}")
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": "60"},
            content={
                "error": "rate_limit_exceeded",
                "message": str(exc),
                "details": sanitize_data(exc.details),
            },
        )

    @application.exception_handler(ZohoOAuthError)
    async def zoho_oauth_handler(request: Request, exc: ZohoOAuthError):
        logger.warning(f"Zoho OAuth error: {exc}")
        return JSONResponse(
            status_code=exc.status_code or status.HTTP_400_BAD_REQUEST,
            content={
                "error": "oauth_authorization_error",
                "message": str(exc),
                "details": sanitize_data(exc.details),
            },
        )

    @application.exception_handler(ZohoAPIError)
    async def zoho_api_error_handler(request: Request, exc: ZohoAPIError):
        logger.error(f"Zoho API error: {exc}")
        return JSONResponse(
            status_code=exc.status_code or status.HTTP_502_BAD_GATEWAY,
            content={
                "error": "external_api_error",
                "message": str(exc),
                "details": sanitize_data(exc.details),
            },
        )

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled internal server error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_server_error",
                "message": "An unexpected server error occurred. Please contact platform support.",
            },
        )

    # Mount API routers
    application.include_router(api_router, prefix=settings.API_V1_STR)

    @application.get("/health", tags=["System"])
    async def root_health():
        return {
            "status": "healthy",
            "service": "OneDesk ERP Integration Platform",
            "environment": settings.ENVIRONMENT,
        }

    return application


app = create_application()
