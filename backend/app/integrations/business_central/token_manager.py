import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.integrations.business_central.exceptions import BusinessCentralOAuthError, BusinessCentralTokenExpiredError
from app.integrations.business_central.oauth import BusinessCentralOAuthClient
from app.models.integration import Integration


class BusinessCentralTokenManager:
    def __init__(self, oauth_client: BusinessCentralOAuthClient | None = None) -> None:
        self.oauth_client = oauth_client or BusinessCentralOAuthClient()
        self._locks: Dict[str, asyncio.Lock] = {}

    def _get_lock(self, integration_id: str) -> asyncio.Lock:
        return self._locks.setdefault(integration_id, asyncio.Lock())

    @staticmethod
    def is_token_expired(integration: Integration, safety_buffer_seconds: int = 300) -> bool:
        if not integration.access_token or not integration.token_expires_at:
            return True
        expires_at = integration.token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return (expires_at - datetime.now(timezone.utc)).total_seconds() < safety_buffer_seconds

    async def refresh_access_token(self, integration: Integration, session: AsyncSession, force: bool = False) -> str:
        async with self._get_lock(str(integration.id)):
            if not force and integration.access_token and not self.is_token_expired(integration, 60):
                return integration.access_token
            if not integration.refresh_token:
                integration.status = "revoked"
                await session.commit()
                raise BusinessCentralTokenExpiredError("No Business Central refresh token is available.")
            try:
                result = await self.oauth_client.refresh_token(integration.refresh_token)
            except BusinessCentralOAuthError as exc:
                if exc.status_code in {400, 401} and "invalid or revoked" in str(exc).lower():
                    integration.status = "revoked"
                    await session.commit()
                    raise BusinessCentralTokenExpiredError(str(exc)) from exc
                raise
            integration.access_token = result["access_token"]
            integration.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(result.get("expires_in", 3600)))
            if result.get("refresh_token"):
                integration.refresh_token = result["refresh_token"]
            integration.status = "active"
            integration.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(integration)
            logger.info("Refreshed Business Central access token for integration %s", integration.id)
            return integration.access_token

    async def get_valid_access_token(self, integration: Integration, session: AsyncSession) -> str:
        if integration.status == "revoked":
            raise BusinessCentralTokenExpiredError("Business Central connection is revoked.")
        if self.is_token_expired(integration):
            return await self.refresh_access_token(integration, session)
        return integration.access_token


business_central_token_manager = BusinessCentralTokenManager()
