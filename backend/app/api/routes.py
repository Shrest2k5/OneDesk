from fastapi import APIRouter
from app.api.integrations_router import router as integrations_router
from app.auth.router import router as auth_router
from app.integrations.zoho.crm_router import router as zoho_crm_router
from app.integrations.zoho.router import router as zoho_oauth_router

api_router = APIRouter()

# Authentication endpoints: /api/v1/auth
api_router.include_router(auth_router)

# Integration connection lifecycle & OAuth: /api/v1/integrations/zoho
api_router.include_router(zoho_oauth_router)

# Generic integration management: /api/v1/integrations
api_router.include_router(integrations_router)

# Zoho CRM data retrieval endpoints: /api/v1/zoho
api_router.include_router(zoho_crm_router)


@api_router.get("/health", tags=["System"])
async def health_check():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "service": "OneDesk ERP Integration Platform",
        "version": "0.1.0",
    }
