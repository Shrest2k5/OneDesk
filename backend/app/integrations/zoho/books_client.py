import asyncio
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit, urlunsplit

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.core.security import sanitize_data
from app.integrations.zoho.exceptions import ZohoAPIError, ZohoRateLimitError, ZohoTokenExpiredError
from app.integrations.zoho.oauth import ZOHO_DATA_CENTERS
from app.integrations.zoho.token_manager import ZohoTokenManager, zoho_token_manager
from app.models.integration import Integration


class ZohoBooksClient:
    """Dedicated read-only HTTP client for Zoho Books endpoints."""

    def __init__(
        self,
        integration: Integration,
        session: AsyncSession,
        token_manager: Optional[ZohoTokenManager] = None,
        timeout: float = 30.0,
    ) -> None:
        self.integration = integration
        self.session = session
        self.token_manager = token_manager or zoho_token_manager
        self.timeout = timeout
        api_domain = integration.api_domain or "https://www.zohoapis.com"
        parsed = urlsplit(api_domain.strip())
        origin = urlunsplit((parsed.scheme or "https", parsed.netloc, "", "", "")).rstrip("/")
        allowed_origins = {value["api"].rstrip("/") for value in ZOHO_DATA_CENTERS.values()}
        if not parsed.netloc or origin not in allowed_origins:
            raise ValueError("Invalid or unauthorized Zoho Books API domain.")
        self.base_url = f"{origin}/books/v3"

    async def _execute_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        attempt: int = 1,
    ) -> Dict[str, Any]:
        token = await self.token_manager.get_valid_access_token(self.integration, self.session)
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Zoho-oauthtoken {token}",
            "Accept": "application/json",
        }
        logger.debug("Zoho Books request: method=%s endpoint=%s params=%s", method, url, sanitize_data(params or {}))

        async with httpx.AsyncClient(timeout=self.timeout) as http_client:
            try:
                response = await http_client.request(method=method, url=url, params=params, headers=headers)
            except httpx.RequestError as exc:
                logger.error("Network error communicating with Zoho Books: %s", type(exc).__name__)
                raise ZohoAPIError("Network communication failure with Zoho Books.")

        if response.status_code == 401 and attempt == 1:
            try:
                await self.token_manager.refresh_access_token(self.integration, self.session)
            except ZohoTokenExpiredError:
                raise
            except Exception as exc:
                raise ZohoAPIError("Authentication failed with Zoho Books.", status_code=401) from exc
            return await self._execute_request(method, path, params, attempt + 1)

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            wait_time = float(retry_after) if retry_after and retry_after.isdigit() else 2.0 ** attempt
            if attempt <= 2:
                await asyncio.sleep(wait_time)
                return await self._execute_request(method, path, params, attempt + 1)
            raise ZohoRateLimitError("Zoho Books API rate limit exceeded.", status_code=429)

        try:
            payload = response.json()
        except Exception as exc:
            raise ZohoAPIError("Zoho Books returned an invalid JSON response.", status_code=response.status_code) from exc

        if response.status_code >= 400:
            details = sanitize_data(payload if isinstance(payload, dict) else {"raw": payload})
            message = details.get("message", f"HTTP {response.status_code}") if isinstance(details, dict) else "API error"
            raise ZohoAPIError(
                f"Zoho Books API error: {message}",
                status_code=response.status_code,
                details=details,
            )
        if not isinstance(payload, dict):
            raise ZohoAPIError("Zoho Books returned an unexpected response structure.")
        if payload.get("code") not in (None, 0):
            raise ZohoAPIError(
                f"Zoho Books API error: {payload.get('message', 'Unknown API error')}",
                details=sanitize_data(payload),
            )
        return payload

    async def list_organizations(self) -> List[Dict[str, Any]]:
        payload = await self._execute_request("GET", "organizations")
        organizations = payload.get("organizations", [])
        if organizations is None:
            return []
        if not isinstance(organizations, list):
            raise ZohoAPIError("Zoho Books organizations response has an invalid structure.")
        return [item for item in organizations if isinstance(item, dict)]

    async def list_contacts_page(
        self, organization_id: str, page: int = 1, per_page: int = 200,
    ) -> Dict[str, Any]:
        """Fetch one page of contacts for the explicitly selected organization."""
        if not organization_id:
            raise ValueError("A selected Books organization is required")
        payload = await self._execute_request(
            "GET",
            "contacts",
            params={"organization_id": organization_id, "page": page, "per_page": per_page},
        )
        contacts = payload.get("contacts", [])
        if contacts is None:
            contacts = []
        if not isinstance(contacts, list) or not all(isinstance(item, dict) for item in contacts):
            raise ZohoAPIError("Zoho Books contacts response has an invalid structure.")
        page_context = payload.get("page_context", {})
        if not isinstance(page_context, dict):
            raise ZohoAPIError("Zoho Books contacts pagination has an invalid structure.")
        return {"contacts": contacts, "page_context": page_context}

    async def list_contacts(self, organization_id: str, page: int = 1, per_page: int = 200) -> Dict[str, Any]:
        return await self.list_contacts_page(organization_id, page, per_page)

    async def list_invoices_page(
        self, organization_id: str, page: int = 1, per_page: int = 200,
    ) -> Dict[str, Any]:
        """Fetch one page of sales invoices for the explicitly selected organization."""
        if not organization_id:
            raise ValueError("A selected Books organization is required")
        payload = await self._execute_request(
            "GET",
            "invoices",
            params={"organization_id": organization_id, "page": page, "per_page": per_page},
        )
        invoices = payload.get("invoices", [])
        if invoices is None:
            invoices = []
        if not isinstance(invoices, list) or not all(isinstance(item, dict) for item in invoices):
            raise ZohoAPIError("Zoho Books invoices response has an invalid structure.")
        page_context = payload.get("page_context", {})
        if isinstance(page_context, list):
            page_context = page_context[0] if page_context and isinstance(page_context[0], dict) else {}
        if not isinstance(page_context, dict):
            raise ZohoAPIError("Zoho Books invoice pagination has an invalid structure.")
        return {"invoices": invoices, "page_context": page_context}

    async def list_financial_page(
        self, organization_id: str, endpoint: str, response_key: str,
        page: int = 1, per_page: int = 200, start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not organization_id:
            raise ValueError("A selected Books organization is required")
        params: Dict[str, Any] = {"organization_id": organization_id, "page": page, "per_page": per_page}
        if start_date:
            params["date_start"] = start_date
        if end_date:
            params["date_end"] = end_date
        payload = await self._execute_request("GET", endpoint, params=params)
        items = payload.get(response_key, [])
        if items is None:
            items = []
        if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
            raise ZohoAPIError(f"Zoho Books {endpoint} response has an invalid structure.")
        context = payload.get("page_context", {})
        if context is None:
            context = {}
        if isinstance(context, list):
            context = context[0] if context and isinstance(context[0], dict) else {}
        if not isinstance(context, dict):
            raise ZohoAPIError(f"Zoho Books {endpoint} pagination has an invalid structure.")
        return {"items": items, "page_context": context}
