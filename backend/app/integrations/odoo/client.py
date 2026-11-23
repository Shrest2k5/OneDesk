import ipaddress
import socket
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.core.logging import logger
from app.core.security import sanitize_data
from app.integrations.odoo.exceptions import (
    OdooAuthenticationError,
    OdooConfigurationError,
    OdooConnectionError,
    OdooPermissionError,
    OdooUnsupportedError,
)


class OdooClient:
    """Small, read-only client for Odoo 20 External JSON-2."""

    def __init__(self, instance_url: str, api_key: str, database: Optional[str] = None, timeout: float = 15.0) -> None:
        self.base_url = self._validate_instance_url(instance_url)
        if not api_key or not api_key.strip():
            raise OdooConfigurationError("An Odoo JSON-2 API key is required.", status_code=422)
        if database is not None and (not database.strip() or len(database.strip()) > 100):
            raise OdooConfigurationError("The optional Odoo database name is invalid.", status_code=422)
        self.api_key = api_key.strip()
        self.database = database.strip() if database else None
        self.timeout = timeout

    @staticmethod
    def _validate_instance_url(instance_url: str) -> str:
        value = (instance_url or "").strip().rstrip("/")
        parsed = urlsplit(value)
        if len(value) > 2048 or parsed.scheme != "https" or not parsed.hostname:
            raise OdooConfigurationError("Odoo instance URL must be an HTTPS URL with a hostname.", status_code=422)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise OdooConfigurationError("Odoo instance URL must not contain credentials, query parameters, or fragments.", status_code=422)
        if parsed.hostname.lower() in {"localhost", "localhost.localdomain"}:
            raise OdooConfigurationError("Local Odoo instance URLs are not allowed for external connections.", status_code=422)
        OdooClient._assert_public_hostname(parsed.hostname, parsed.port or 443)
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))

    @staticmethod
    def _assert_public_hostname(hostname: str, port: int) -> None:
        try:
            address = ipaddress.ip_address(hostname)
            if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_multicast:
                raise OdooConfigurationError("Private or non-routable Odoo instance addresses are not allowed.", status_code=422)
        except ValueError:
            if hostname.lower().endswith((".local", ".internal")):
                raise OdooConfigurationError("Internal Odoo hostnames are not allowed for external connections.", status_code=422)
            try:
                resolved = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
                for item in resolved:
                    resolved_address = ipaddress.ip_address(item[4][0])
                    if resolved_address.is_private or resolved_address.is_loopback or resolved_address.is_link_local or resolved_address.is_reserved or resolved_address.is_multicast:
                        raise OdooConfigurationError("The Odoo hostname resolves to a private or non-routable address.", status_code=422)
            except socket.gaierror:
                # DNS reachability is validated by the request itself; an unresolved
                # public hostname is not treated as a local/private target here.
                pass

    async def get_user_context(self) -> Dict[str, Any]:
        """Authenticate without mutating Odoo and return the current user's context."""
        result = await self._post("res.users", "context_get", {})
        if not isinstance(result, dict):
            raise OdooConnectionError("Odoo JSON-2 returned an invalid user context.", status_code=502)
        return result

    async def search_read_partners(
        self,
        domain: Optional[list] = None,
        offset: int = 0,
        limit: int = 200,
        fields: Optional[List[str]] = None,
        order: str = "id",
    ) -> List[Dict[str, Any]]:
        """Read one paginated, read-only page of res.partner records."""
        result = await self._post(
            "res.partner",
            "search_read",
            {
                "domain": domain or [],
                "fields": fields or [],
                "offset": max(0, offset),
                "limit": max(1, min(limit, 500)),
                "order": order,
                "context": {"active_test": False},
            },
        )
        if not isinstance(result, list) or not all(isinstance(item, dict) for item in result):
            raise OdooConnectionError("Odoo res.partner/search_read returned an invalid response.", status_code=502)
        return result

    async def _post(self, model: str, method: str, payload: Dict[str, Any]) -> Any:
        url = f"{self.base_url}/json/2/{model}/{method}"
        parsed = urlsplit(self.base_url)
        self._assert_public_hostname(parsed.hostname or "", parsed.port or 443)
        headers = {
            "Authorization": f"bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "OneDesk-Odoo-Integration/1.0",
        }
        if self.database:
            headers["X-Odoo-Database"] = self.database
        logger.debug("Odoo JSON-2 request: method=POST endpoint=%s database=%s", url, self.database or "[default]")
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as http_client:
                response = await http_client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise OdooConnectionError("The Odoo instance timed out. Check the URL and retry.", status_code=504) from exc
        except httpx.RequestError as exc:
            logger.warning("Odoo connection failed: type=%s", type(exc).__name__)
            raise OdooConnectionError("The Odoo instance could not be reached. Check the URL and network access.", status_code=502) from exc

        try:
            data = response.json()
        except ValueError:
            data = {"message": response.text[:500]}
        safe_data = sanitize_data(data)
        if 300 <= response.status_code < 400:
            raise OdooConnectionError("The Odoo instance redirected the JSON-2 request; redirects are not followed.", status_code=502)
        if response.status_code in (401, 403):
            if response.status_code == 403:
                raise OdooPermissionError("The Odoo API key is valid but lacks permission for JSON-2 validation.", status_code=403, details=safe_data if isinstance(safe_data, dict) else {})
            raise OdooAuthenticationError("The Odoo JSON-2 API key was rejected.", status_code=401, details=safe_data if isinstance(safe_data, dict) else {})
        if response.status_code == 404:
            raise OdooUnsupportedError("The Odoo deployment did not expose the required External JSON-2 endpoint.", status_code=404, details=safe_data if isinstance(safe_data, dict) else {})
        if response.status_code >= 400:
            raise OdooConnectionError(f"Odoo JSON-2 returned HTTP {response.status_code}.", status_code=response.status_code, details=safe_data if isinstance(safe_data, dict) else {})
        return data
