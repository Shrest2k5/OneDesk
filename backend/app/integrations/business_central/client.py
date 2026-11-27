from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlparse

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.core.security import sanitize_data
from app.integrations.business_central.exceptions import BusinessCentralOAuthError, BusinessCentralTokenExpiredError
from app.integrations.business_central.token_manager import BusinessCentralTokenManager, business_central_token_manager
from app.models.integration import Integration


class BusinessCentralAPIError(Exception):
    def __init__(self, message: str, status_code: int, details: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details or {}


class BusinessCentralClient:
    """HTTP client for official Business Central cloud APIs."""

    def __init__(
        self,
        integration: Integration,
        session: AsyncSession,
        token_manager: Optional[BusinessCentralTokenManager] = None,
    ) -> None:
        self.integration = integration
        self.session = session
        self.token_manager = token_manager or business_central_token_manager
        self.base_url = settings.BUSINESS_CENTRAL_API_BASE_URL.rstrip("/")

    def _api_url(self, environment_name: str, path: str = "companies") -> str:
        environment = quote(environment_name.strip(), safe="")
        return f"{self.base_url}/v2.0/{environment}/api/v2.0/{path.lstrip('/')}"

    def _admin_url(self, path: str) -> str:
        version = getattr(settings, "BUSINESS_CENTRAL_ADMIN_API_VERSION", "v2.29")
        return f"{self.base_url}/admin/{version}/{path.lstrip('/')}"

    def _validate_next_link(self, next_link: str) -> str:
        parsed = urlparse(next_link)
        base = urlparse(self.base_url)
        if parsed.scheme != "https" or parsed.netloc.lower() != base.netloc.lower():
            raise BusinessCentralAPIError("Business Central returned an unsafe pagination link.", 502)
        return next_link

    async def _request(
        self,
        method: str,
        url: str,
        *,
        retry_on_401: bool = True,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            token = await self.token_manager.get_valid_access_token(self.integration, self.session)
        except BusinessCentralTokenExpiredError:
            raise
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.request(method, url, headers=headers, params=params)
            except httpx.TimeoutException as exc:
                raise BusinessCentralAPIError("Business Central request timed out.", 504) from exc
            except httpx.RequestError as exc:
                logger.warning("Business Central API network failure: %s", type(exc).__name__)
                raise BusinessCentralAPIError("Business Central could not be reached.", 502) from exc

        if response.status_code == 401 and retry_on_401:
            await self.token_manager.refresh_access_token(self.integration, self.session, force=True)
            return await self._request(method, url, retry_on_401=False, params=params)

        try:
            payload = response.json() if response.content else {}
        except Exception:
            payload = {}
        if response.status_code >= 400:
            error = payload.get("error", {}) if isinstance(payload, dict) else {}
            message = error.get("message") if isinstance(error, dict) else None
            raise BusinessCentralAPIError(
                message or "Business Central rejected the request.",
                response.status_code,
                sanitize_data(payload),
            )
        return payload if isinstance(payload, dict) else {}

    async def list_environments(self) -> Dict[str, Any]:
        """List environments through Admin Center, with verified production fallback."""
        try:
            payload = await self._request(
                "GET", self._admin_url("applications/BusinessCentral/environments")
            )
            environments = payload.get("value", [])
            return {"data": [self._normalize_environment(item) for item in environments], "source": "admin_center"}
        except BusinessCentralAPIError as exc:
            if exc.status_code not in {401, 403, 404}:
                raise
            logger.info("Business Central Admin Center environment discovery unavailable; verifying production fallback")
            try:
                await self.list_companies("production")
            except BusinessCentralAPIError as fallback_exc:
                if fallback_exc.status_code in {401, 403, 404}:
                    raise BusinessCentralAPIError(
                        "Business Central environments are unavailable and production could not be accessed.",
                        fallback_exc.status_code,
                        fallback_exc.details,
                    ) from fallback_exc
                raise
            return {
                "data": [{"name": "production", "type": "production", "status": "verified"}],
                "source": "verified_production_fallback",
                "warning": "Admin Center environment discovery requires additional tenant permissions.",
            }

    @staticmethod
    def _normalize_environment(item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "name": str(item.get("name") or item.get("environmentName") or "").strip(),
            "type": item.get("type") or item.get("environmentType"),
            "status": item.get("status"),
            "application_version": item.get("applicationVersion"),
            "raw": item,
        }

    async def list_companies(self, environment_name: str) -> List[Dict[str, Any]]:
        """Return all companies visible to the delegated Business Central user."""
        url = self._api_url(environment_name)
        companies: List[Dict[str, Any]] = []
        next_url: Optional[str] = url
        while next_url:
            payload = await self._request("GET", next_url)
            page = payload.get("value", [])
            if not isinstance(page, list):
                raise BusinessCentralAPIError("Business Central returned an invalid companies response.", 502)
            companies.extend(self._normalize_company(item) for item in page if isinstance(item, dict))
            raw_next = payload.get("@odata.nextLink") or payload.get("@odata.nextlink")
            next_url = self._validate_next_link(raw_next) if raw_next else None
        return companies

    @staticmethod
    def _normalize_company(item: Dict[str, Any]) -> Dict[str, Any]:
        company_id = item.get("id")
        display_name = item.get("displayName") or item.get("name")
        return {
            "id": str(company_id).strip() if company_id is not None else "",
            "display_name": str(display_name).strip() if display_name is not None else "",
            "name": item.get("name"),
            "raw": item,
        }
