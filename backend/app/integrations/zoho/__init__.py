"""Zoho CRM integration module."""
from app.integrations.zoho.integration import ZohoIntegration, zoho_integration
from app.integrations.zoho.router import router

__all__ = ["ZohoIntegration", "zoho_integration", "router"]

