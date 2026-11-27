from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid

import jwt

from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.base import BaseERPIntegration
from app.integrations.business_central.exceptions import BusinessCentralOAuthError
from app.integrations.business_central.client import BusinessCentralClient
from app.integrations.business_central.oauth import BusinessCentralOAuthClient
from app.integrations.business_central.token_manager import business_central_token_manager
from app.integrations.registry import integration_registry
from app.models.integration import Integration
from app.repositories.integration_repository import IntegrationRepository


class BusinessCentralIntegration(BaseERPIntegration):
    def __init__(self, oauth_client: BusinessCentralOAuthClient | None = None) -> None:
        self.oauth_client = oauth_client or BusinessCentralOAuthClient()

    @property
    def provider_name(self) -> str:
        return "business_central"

    @property
    def product_name(self) -> str:
        return "erp"

    def generate_authorization_url(self, user_id: uuid.UUID, connection_name: str, data_center: Optional[str] = None, **kwargs: Any) -> Dict[str, str]:
        return self.oauth_client.generate_authorization_url(
            user_id, connection_name, kwargs.get("integration_id")
        )

    async def handle_oauth_callback(self, code: str, state: str, session: AsyncSession) -> Integration:
        state_data = self.oauth_client.validate_state(state)
        try:
            user_id = uuid.UUID(str(state_data["sub"]))
        except (KeyError, ValueError, TypeError) as exc:
            raise BusinessCentralOAuthError("Invalid user identity in OAuth state.") from exc
        token_data = await self.oauth_client.exchange_code(code)
        expires_in = int(token_data.get("expires_in", 3600))
        tenant_id = self._tenant_id_from_token(token_data)
        repository = IntegrationRepository(session)
        integration_id = state_data.get("integration_id")
        if integration_id:
            try:
                integration = await repository.get_by_user_and_id(user_id, uuid.UUID(str(integration_id)))
            except (ValueError, TypeError) as exc:
                raise BusinessCentralOAuthError("Invalid integration identifier in OAuth state.") from exc
            if not integration or integration.provider != self.provider_name or integration.product != self.product_name:
                raise BusinessCentralOAuthError("OAuth state does not identify a valid Business Central integration.")
            integration.connection_name = state_data.get("connection_name", integration.connection_name)
            integration.access_token = token_data["access_token"]
            if token_data.get("refresh_token"):
                integration.refresh_token = token_data["refresh_token"]
            integration.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            integration.api_domain = "https://api.businesscentral.dynamics.com"
            # Reauthorization preserves the existing selected company and
            # lifecycle state. New connections remain pending until selection.
            integration.status = integration.status if integration.status == "active" else "pending"
            if tenant_id:
                integration.business_central_tenant_id = tenant_id
        else:
            if not token_data.get("refresh_token"):
                raise BusinessCentralOAuthError("Business Central token response did not contain a refresh token.")
            integration = await repository.create_or_update(
                user_id=user_id,
                provider=self.provider_name,
                product=self.product_name,
                connection_name=state_data.get("connection_name", "My Business Central"),
                access_token=token_data["access_token"],
                refresh_token=token_data["refresh_token"],
                token_expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
                api_domain="https://api.businesscentral.dynamics.com",
                status="pending",
            )
            integration.business_central_tenant_id = tenant_id
        await session.commit()
        await session.refresh(integration)
        return integration

    @staticmethod
    def _tenant_id_from_token(token_data: Dict[str, Any]) -> Optional[str]:
        configured = str(settings.BUSINESS_CENTRAL_TENANT_ID or "")
        if configured and configured.lower() not in {"common", "organizations", "consumers"}:
            return configured
        id_token = token_data.get("id_token")
        if not id_token:
            return None
        try:
            claims = jwt.decode(id_token, options={"verify_signature": False})
            tenant_id = claims.get("tid")
            return str(tenant_id).strip() if tenant_id else None
        except jwt.PyJWTError:
            return None

    def client(self, integration: Integration, session: AsyncSession) -> BusinessCentralClient:
        return BusinessCentralClient(integration, session)

    async def discover_environments(self, integration: Integration, session: AsyncSession) -> Dict[str, Any]:
        return await self.client(integration, session).list_environments()

    async def discover_companies(
        self, integration: Integration, environment_name: str, session: AsyncSession
    ) -> List[Dict[str, Any]]:
        return await self.client(integration, session).list_companies(environment_name)

    async def refresh_access_token(self, integration: Integration, session: AsyncSession) -> Integration:
        await business_central_token_manager.refresh_access_token(integration, session)
        return integration

    async def get_connection_status(self, integration: Integration, session: AsyncSession) -> Dict[str, Any]:
        return {
            "status": "connected" if integration.status == "active" else integration.status,
            "provider": self.provider_name,
            "product": self.product_name,
            "connection_name": integration.connection_name,
            "api_domain": integration.api_domain,
            "token_status": "expired" if business_central_token_manager.is_token_expired(integration) else "valid",
        }

    async def fetch_records(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        raise NotImplementedError("Business Central synchronization is planned for a later milestone.")

    async def get_record(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        raise NotImplementedError("Business Central synchronization is planned for a later milestone.")


business_central_integration = BusinessCentralIntegration()
integration_registry.register(business_central_integration)
