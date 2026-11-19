from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.integrations.base import BaseERPIntegration
from app.integrations.registry import integration_registry
from app.integrations.zoho.exceptions import ZohoOAuthError
from app.integrations.zoho.oauth import ZohoOAuthClient
from app.models.integration import Integration
from app.repositories.integration_repository import IntegrationRepository


class ZohoBooksIntegration(BaseERPIntegration):
    """Zoho Books OAuth lifecycle and paginated record retrieval."""

    def __init__(self, oauth_client: Optional[ZohoOAuthClient] = None) -> None:
        self.oauth_client = oauth_client or ZohoOAuthClient(product="books")

    @property
    def provider_name(self) -> str:
        return "zoho"

    @property
    def product_name(self) -> str:
        return "books"

    def generate_authorization_url(
        self,
        user_id: uuid.UUID,
        connection_name: str,
        data_center: Optional[str] = "us",
        **kwargs: Any,
    ) -> Dict[str, str]:
        return self.oauth_client.generate_authorization_url(
            user_id=user_id,
            connection_name=connection_name,
            data_center=data_center,
            product=self.product_name,
        )

    async def handle_oauth_callback(
        self,
        code: str,
        state: str,
        session: AsyncSession,
    ) -> Integration:
        state_data = self.oauth_client.validate_state(state)
        user_id_str = state_data.get("sub")
        connection_name = state_data.get("connection_name", "My Zoho Books")
        dc = state_data.get("dc", "us")
        if not user_id_str:
            raise ZohoOAuthError("State token missing user identity.")

        try:
            user_id = uuid.UUID(user_id_str)
        except (ValueError, TypeError):
            raise ZohoOAuthError("Invalid user ID in state token.")

        dc_info = self.oauth_client.get_data_center_info(dc)
        token_data = await self.oauth_client.exchange_code(code, dc_info["accounts"])
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        if not access_token or not refresh_token:
            raise ZohoOAuthError("Zoho Books token response is missing required credentials.")

        expires_in = token_data.get("expires_in", 3600)
        integration = await IntegrationRepository(session).create_or_update(
            user_id=user_id,
            provider=self.provider_name,
            product=self.product_name,
            connection_name=connection_name,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
            api_domain=token_data.get("api_domain") or dc_info["api"],
            external_account_id=None,
            status="active",
        )
        await session.commit()
        await session.refresh(integration)
        logger.info("Successfully connected Zoho Books integration: id=%s, user_id=%s", integration.id, user_id)
        return integration

    async def refresh_access_token(self, integration: Integration, session: AsyncSession) -> Integration:
        from app.integrations.zoho.token_manager import zoho_token_manager
        await zoho_token_manager.refresh_access_token(integration, session)
        return integration

    async def get_connection_status(self, integration: Integration, session: AsyncSession) -> Dict[str, Any]:
        # Organization/API verification belongs to Milestone 4. This endpoint
        # reports persisted connection state without making a Books data call.
        return {
            "status": "connected" if integration.status == "active" else integration.status,
            "provider": self.provider_name,
            "product": self.product_name,
            "connection_name": integration.connection_name,
            "api_domain": integration.api_domain,
            "token_status": "stored" if integration.access_token else "missing",
        }

    async def fetch_records(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Adapt the shared sync contract to the Books page response shape."""
        integration = kwargs.get("integration")
        resource_type = kwargs.get("resource_type")
        page = int(kwargs.get("page", 1))
        per_page = int(kwargs.get("per_page", 200))
        session = kwargs.get("session")
        if not integration or not integration.selected_organization_id:
            raise ValueError("A selected Books organization is required")
        if session is None:
            raise ValueError("A database session is required for Books synchronization")

        from app.integrations.zoho.books_client import ZohoBooksClient

        client = ZohoBooksClient(integration, session)
        if resource_type == "contacts":
            response = await client.list_contacts_page(integration.selected_organization_id, page, per_page)
            items = response["contacts"]
        elif resource_type == "invoices":
            response = await client.list_invoices_page(integration.selected_organization_id, page, per_page)
            items = response["invoices"]
        else:
            raise ValueError(f"Books synchronization does not support resource '{resource_type}'")

        page_context = response.get("page_context") or {}
        return {"data": items, "info": {"more_records": bool(page_context.get("has_more_page", False))}}

    async def get_record(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        raise NotImplementedError("Zoho Books data retrieval is not implemented yet.")


zoho_books_integration = ZohoBooksIntegration()
integration_registry.register(zoho_books_integration)
