import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.integrations.zoho.exceptions import ZohoOAuthError, ZohoTokenExpiredError
from app.integrations.zoho.oauth import ZOHO_DATA_CENTERS
from app.models.integration import Integration


class ZohoTokenManager:
    """
    Manages OAuth token lifecycle for Zoho CRM integrations.
    Handles proactive and reactive token refreshing, concurrency locks,
    and revoked token state management.
    """

    def __init__(self) -> None:
        # In-memory async locks per integration ID to prevent duplicate concurrent refresh requests
        self._locks: Dict[str, asyncio.Lock] = {}

    def _get_lock(self, integration_id: str) -> asyncio.Lock:
        if integration_id not in self._locks:
            self._locks[integration_id] = asyncio.Lock()
        return self._locks[integration_id]

    @staticmethod
    def _resolve_accounts_url(api_domain: Optional[str]) -> str:
        """Resolve accounts URL matching the integration's API domain."""
        if not api_domain:
            return "https://accounts.zoho.com"

        api_domain_lower = api_domain.lower()
        for dc_key, dc_data in ZOHO_DATA_CENTERS.items():
            if dc_data["api"] in api_domain_lower or dc_key in api_domain_lower:
                return dc_data["accounts"]

        if ".eu" in api_domain_lower:
            return "https://accounts.zoho.eu"
        elif ".in" in api_domain_lower:
            return "https://accounts.zoho.in"
        elif ".cn" in api_domain_lower:
            return "https://accounts.zoho.com.cn"
        elif ".au" in api_domain_lower:
            return "https://accounts.zoho.com.au"
        elif ".ca" in api_domain_lower:
            return "https://accounts.zoho.ca"
        elif ".jp" in api_domain_lower:
            return "https://accounts.zoho.jp"

        return "https://accounts.zoho.com"

    @staticmethod
    def _credentials_for(integration: Integration) -> tuple[str, str]:
        if integration.product == "books":
            return settings.ZOHO_BOOKS_CLIENT_ID, settings.ZOHO_BOOKS_CLIENT_SECRET
        return settings.ZOHO_CLIENT_ID, settings.ZOHO_CLIENT_SECRET

    def is_token_expired(self, integration: Integration, safety_buffer_seconds: int = 300) -> bool:
        """
        Check if the access token is expired or close to expiring (default 5-minute buffer).
        """
        if not integration.access_token:
            return True
        if not integration.token_expires_at:
            return True

        # Ensure timezone-aware comparison
        now = datetime.now(timezone.utc)
        expires_at = integration.token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        return (expires_at - now).total_seconds() < safety_buffer_seconds

    async def refresh_access_token(
        self,
        integration: Integration,
        session: AsyncSession,
        force: bool = False,
    ) -> str:
        """
        Exchange refresh token for a fresh access token using Zoho OAuth token endpoint.
        Uses per-integration lock to prevent duplicate concurrent refresh calls.
        """
        lock = self._get_lock(str(integration.id))

        async with lock:
            if not force and not self.is_token_expired(integration, safety_buffer_seconds=60) and integration.access_token:
                logger.info(f"Token for integration {integration.id} is already valid.")
                return integration.access_token

            refresh_token = integration.refresh_token
            if not refresh_token:
                integration.status = "revoked"
                await session.commit()
                logger.error(f"Integration {integration.id} has no refresh token stored.")
                raise ZohoTokenExpiredError("No refresh token available. Connection must be re-authorized.")

            accounts_url = self._resolve_accounts_url(integration.api_domain)
            token_endpoint = f"{accounts_url.rstrip('/')}/oauth/v2/token"

            data = {
                "grant_type": "refresh_token",
                "client_id": self._credentials_for(integration)[0],
                "client_secret": self._credentials_for(integration)[1],
                "refresh_token": refresh_token,
            }

            logger.info(f"Refreshing access token for integration {integration.id} via {accounts_url}...")

            async with httpx.AsyncClient(timeout=30.0) as client:
                try:
                    response = await client.post(token_endpoint, data=data)
                except httpx.TimeoutException:
                    logger.error(f"Timeout refreshing Zoho token for integration {integration.id}.")
                    raise ZohoOAuthError("Network timeout refreshing Zoho access token.")
                except httpx.RequestError as exc:
                    logger.error(f"Network error refreshing Zoho token for integration {integration.id}: {type(exc).__name__}")
                    raise ZohoOAuthError("Network communication failure during token refresh.")

            try:
                result = response.json()
            except Exception:
                result = {}

            if response.status_code != 200 or "error" in result:
                err_code = result.get("error", f"HTTP {response.status_code}")
                logger.error(f"Zoho token refresh failed for integration {integration.id}: {err_code}")

                # If token is permanently revoked or invalid
                if err_code in ["invalid_code", "invalid_refresh_token", "invalid_client", "access_denied"]:
                    integration.status = "revoked"
                    await session.commit()
                    raise ZohoTokenExpiredError(
                        f"Zoho refresh token is revoked or invalid ({err_code}). Re-authorization is required."
                    )

                raise ZohoOAuthError(f"Failed to refresh Zoho token: {err_code}")

            new_access_token = result.get("access_token")
            if not new_access_token:
                raise ZohoOAuthError("Zoho token refresh response did not contain an access_token.")

            expires_in = result.get("expires_in", 3600)
            api_domain = result.get("api_domain")

            # Update access token (encrypted on bind)
            integration.access_token = new_access_token
            integration.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            if api_domain:
                integration.api_domain = api_domain

            # Handle token rotation: update refresh token only if a new one is returned
            new_refresh_token = result.get("refresh_token")
            if new_refresh_token and str(new_refresh_token).strip():
                logger.info(f"Preserving rotated refresh token for integration {integration.id}.")
                integration.refresh_token = new_refresh_token
            # Note: If no new refresh_token is returned, the existing integration.refresh_token is preserved untouched.

            integration.status = "active"
            integration.updated_at = datetime.now(timezone.utc)

            await session.commit()
            await session.refresh(integration)

            logger.info(f"Successfully refreshed access token for integration {integration.id}.")
            return new_access_token

    async def get_valid_access_token(
        self,
        integration: Integration,
        session: AsyncSession,
    ) -> str:
        """
        Return a valid, non-expired access token. Automatically refreshes if expired.
        """
        if integration.status == "revoked":
            raise ZohoTokenExpiredError("Integration has been revoked. Re-authorization required.")

        if self.is_token_expired(integration):
            return await self.refresh_access_token(integration, session)

        if not integration.access_token:
            return await self.refresh_access_token(integration, session)

        return integration.access_token


# Singleton token manager instance
zoho_token_manager = ZohoTokenManager()

