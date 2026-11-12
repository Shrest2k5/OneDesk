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


class ZohoIntegration(BaseERPIntegration):
    """Zoho CRM Provider Implementation adhering to the BaseERPIntegration interface."""

    def __init__(self, oauth_client: Optional[ZohoOAuthClient] = None) -> None:
        self.oauth_client = oauth_client or ZohoOAuthClient()

    @property
    def provider_name(self) -> str:
        return "zoho"

    def generate_authorization_url(
        self,
        user_id: uuid.UUID,
        connection_name: str,
        data_center: Optional[str] = "us",
        **kwargs: Any,
    ) -> Dict[str, str]:
        """Generate authorization URL and state token for Zoho OAuth 2.0."""
        return self.oauth_client.generate_authorization_url(
            user_id=user_id,
            connection_name=connection_name,
            data_center=data_center or "us",
        )

    async def handle_oauth_callback(
        self,
        code: str,
        state: str,
        session: AsyncSession,
    ) -> Integration:
        """
        Validate state token, exchange authorization code for tokens,
        retrieve organization ID, and store the integration record with encrypted tokens.
        """
        # 1. Validate State
        state_data = self.oauth_client.validate_state(state)
        user_id_str = state_data.get("sub")
        connection_name = state_data.get("connection_name", "Zoho CRM Connection")
        dc = state_data.get("dc", "us")

        if not user_id_str:
            raise ZohoOAuthError("State token missing user identity.")

        try:
            user_id = uuid.UUID(user_id_str)
        except (ValueError, TypeError):
            raise ZohoOAuthError("Invalid user ID in state token.")

        # 2. Resolve accounts domain
        dc_info = self.oauth_client.get_data_center_info(dc)
        accounts_url = dc_info["accounts"]

        # 3. Exchange code for tokens
        token_data = await self.oauth_client.exchange_code(code, accounts_url)
        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")
        api_domain = token_data.get("api_domain") or dc_info["api"]
        expires_in = token_data.get("expires_in", 3600)

        token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        # 4. Attempt to fetch Zoho organization ID as external_account_id
        org_id = await self.oauth_client.fetch_organization_id(access_token, api_domain)
        if not org_id:
            # Fallback to connection identifier if org endpoint isn't accessible
            org_id = f"zoho_acc_{user_id.hex[:8]}"

        # 5. Persist or update Integration entity
        repo = IntegrationRepository(session)
        integration = await repo.create_or_update(
            user_id=user_id,
            provider=self.provider_name,
            connection_name=connection_name,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
            api_domain=api_domain,
            external_account_id=org_id,
            status="active",
        )
        await session.commit()
        await session.refresh(integration)

        logger.info(
            f"Successfully connected Zoho integration: id={integration.id}, "
            f"org_id={org_id}, user_id={user_id}"
        )
        return integration

    async def refresh_access_token(
        self,
        integration: Integration,
        session: AsyncSession,
    ) -> Integration:
        """Refresh expired access token using ZohoTokenManager."""
        from app.integrations.zoho.token_manager import zoho_token_manager
        await zoho_token_manager.refresh_access_token(integration, session)
        return integration

    async def get_connection_status(
        self,
        integration: Integration,
        session: AsyncSession,
    ) -> Dict[str, Any]:
        """Validate connection by making a lightweight check to Zoho CRM org endpoint."""
        from app.integrations.zoho.client import ZohoClient
        client = ZohoClient(integration, session)
        try:
            org_data = await client.get_organization()
            orgs = org_data.get("org", [])
            org_name = orgs[0].get("company_name", "Zoho CRM") if orgs else "Zoho CRM"
            return {
                "status": "connected",
                "provider": self.provider_name,
                "connection_name": integration.connection_name,
                "api_domain": integration.api_domain,
                "organization_name": org_name,
                "token_status": "valid",
            }
        except Exception as e:
            logger.warning(f"Connection check failed for integration {integration.id}: {e}")
            return {
                "status": "error" if integration.status != "revoked" else "revoked",
                "provider": self.provider_name,
                "connection_name": integration.connection_name,
                "error": str(e),
                "token_status": integration.status,
            }

    async def fetch_records(
        self,
        integration: Integration,
        resource_type: str,
        page: int = 1,
        per_page: int = 200,
        fields: Optional[List[str]] = None,
        modified_since: Optional[str] = None,
        session: Optional[AsyncSession] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Fetch records from Zoho CRM via ZohoClient."""
        if not session:
            raise ValueError("Database session is required for ZohoClient operations.")
        from app.integrations.zoho.client import ZohoClient
        client = ZohoClient(integration, session)
        return await client.fetch_records(
            module=resource_type,
            page=page,
            per_page=per_page,
            fields=fields,
            modified_since=modified_since,
        )

    async def get_record(
        self,
        integration: Integration,
        resource_type: str,
        record_id: str,
        fields: Optional[List[str]] = None,
        session: Optional[AsyncSession] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Retrieve single record from Zoho CRM via ZohoClient."""
        if not session:
            raise ValueError("Database session is required for ZohoClient operations.")
        from app.integrations.zoho.client import ZohoClient
        client = ZohoClient(integration, session)
        return await client.get_record(
            module=resource_type,
            record_id=record_id,
            fields=fields,
        )


# Register Zoho implementation in global integration registry
zoho_integration = ZohoIntegration()
integration_registry.register(zoho_integration)

