from typing import Any, Dict, List, Optional
import uuid
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.integrations.registry import integration_registry
from app.models.integration import Integration
from app.repositories.integration_repository import IntegrationRepository


class IntegrationService:
    """Business logic service for managing connected ERP integrations and access control."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = IntegrationRepository(session)

    async def list_user_integrations(self, user_id: uuid.UUID) -> List[Integration]:
        """List all connected ERP integrations belonging to the user."""
        return await self.repo.get_all_by_user(user_id)

    async def get_user_integration(
        self,
        user_id: uuid.UUID,
        integration_id: uuid.UUID,
    ) -> Integration:
        """
        Retrieve a specific integration, strictly enforcing tenant ownership.
        Prevents unauthorized cross-tenant access.
        """
        integration = await self.repo.get_by_user_and_id(user_id, integration_id)
        if not integration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Integration connection '{integration_id}' not found.",
            )
        return integration

    async def delete_user_integration(
        self,
        user_id: uuid.UUID,
        integration_id: uuid.UUID,
    ) -> None:
        """Disconnect and delete an ERP integration."""
        integration = await self.get_user_integration(user_id, integration_id)
        await self.repo.delete(integration)
        await self.session.commit()
        logger.info(f"Disconnected integration {integration_id} for user {user_id}.")

    async def get_integration_status(
        self,
        user_id: uuid.UUID,
        integration_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """Check live connection status against the external provider."""
        integration = await self.get_user_integration(user_id, integration_id)
        provider = integration_registry.get(integration.provider)
        if not provider:
            return {
                "status": integration.status,
                "provider": integration.provider,
                "error": "Provider implementation not registered in platform.",
            }

        return await provider.get_connection_status(integration, self.session)

    async def resolve_active_integration(
        self,
        user_id: uuid.UUID,
        integration_id: Optional[uuid.UUID] = None,
        provider_name: str = "zoho",
    ) -> Integration:
        """
        Resolve an active integration for data retrieval operations.
        If integration_id is provided, validates ownership.
        If omitted, defaults to the user's primary active connection for the provider.
        """
        if integration_id:
            integration = await self.get_user_integration(user_id, integration_id)
            if integration.status == "revoked":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Integration '{integration_id}' is revoked. Please re-authorize.",
                )
            return integration

        # Auto-resolve first active integration
        all_integrations = await self.repo.get_all_by_user(user_id)
        active = [i for i in all_integrations if i.provider == provider_name and i.status == "active"]
        if not active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No active {provider_name.upper()} connection found. Please connect your account first.",
            )
        return active[0]

