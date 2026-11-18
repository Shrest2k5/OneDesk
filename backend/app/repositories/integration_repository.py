from datetime import datetime, timezone
from typing import List, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import Integration


class IntegrationRepository:
    """Repository handling database operations for Integration entity."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, integration_id: uuid.UUID) -> Optional[Integration]:
        """Retrieve an integration by UUID."""
        query = select(Integration).where(Integration.id == integration_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_user_and_id(
        self,
        user_id: uuid.UUID,
        integration_id: uuid.UUID,
    ) -> Optional[Integration]:
        """
        Retrieve an integration strictly scoped to a specific user.
        Enforces tenant isolation.
        """
        query = select(Integration).where(
            Integration.id == integration_id,
            Integration.user_id == user_id,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_all_by_user(self, user_id: uuid.UUID) -> List[Integration]:
        """Retrieve all active or configured integrations for a user."""
        query = (
            select(Integration)
            .where(Integration.user_id == user_id)
            .order_by(Integration.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_user_provider_account(
        self,
        user_id: uuid.UUID,
        provider: str,
        external_account_id: str,
        product: str = "crm",
    ) -> Optional[Integration]:
        """Find an existing connection by user, provider, and external account ID."""
        query = select(Integration).where(
            Integration.user_id == user_id,
            Integration.provider == provider,
            Integration.product == product,
            Integration.external_account_id == external_account_id,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_user_provider_product(
        self,
        user_id: uuid.UUID,
        provider: str,
        product: str,
    ) -> Optional[Integration]:
        """Find a product connection when no external organization is selected yet."""
        query = select(Integration).where(
            Integration.user_id == user_id,
            Integration.provider == provider,
            Integration.product == product,
            Integration.external_account_id.is_(None),
        )
        result = await self.session.execute(query)
        return result.scalars().first()

    async def create_or_update(
        self,
        user_id: uuid.UUID,
        provider: str,
        connection_name: str,
        access_token: str,
        product: str = "crm",
        refresh_token: Optional[str] = None,
        token_expires_at: Optional[datetime] = None,
        api_domain: Optional[str] = None,
        external_account_id: Optional[str] = None,
        status: str = "active",
    ) -> Integration:
        """
        Create a new integration or update an existing connection with refreshed credentials.
        """
        existing: Optional[Integration] = None
        if external_account_id:
            existing = await self.get_by_user_provider_account(
                user_id=user_id,
                provider=provider,
                product=product,
                external_account_id=external_account_id,
            )
        else:
            existing = await self.get_by_user_provider_product(
                user_id=user_id,
                provider=provider,
                product=product,
            )

        if existing:
            existing.connection_name = connection_name
            existing.access_token = access_token
            if refresh_token:
                existing.refresh_token = refresh_token
            existing.token_expires_at = token_expires_at
            if api_domain:
                existing.api_domain = api_domain
            existing.status = status
            existing.updated_at = datetime.now(timezone.utc)
            await self.session.flush()
            await self.session.refresh(existing)
            return existing

        new_integration = Integration(
            user_id=user_id,
            provider=provider,
            product=product,
            connection_name=connection_name,
            external_account_id=external_account_id,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
            api_domain=api_domain,
            status=status,
        )
        self.session.add(new_integration)
        await self.session.flush()
        await self.session.refresh(new_integration)
        return new_integration

    async def delete(self, integration: Integration) -> None:
        """Delete an integration."""
        await self.session.delete(integration)
        await self.session.flush()

