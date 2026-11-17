import asyncio
from typing import Any, Dict, List, Optional
import httpx
from urllib.parse import urlsplit, urlunsplit
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.core.security import sanitize_data
from app.integrations.zoho.exceptions import (
    ZohoAPIError,
    ZohoRateLimitError,
    ZohoTokenExpiredError,
)
from app.integrations.zoho.token_manager import ZohoTokenManager, zoho_token_manager
from app.models.integration import Integration


class ZohoClient:
    """
    Asynchronous HTTP client for official Zoho CRM v8 REST APIs.
    Features:
    - Dynamic multi-datacenter API domain routing
    - Automatic token injection and reactive 401 retry with token refresh
    - Rate limit (HTTP 429) backoff handling
    - Normalized pagination and field projection
    - ISO-8601 If-Modified-Since incremental sync headers
    """

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

        # Resolve base API domain
        api_domain = integration.api_domain or "https://www.zohoapis.com"
        parsed = urlsplit(api_domain.strip())
        # OAuth responses may contain a CRM path. Store/use only the origin so
        # requests never become .../crm/v8/crm/v8/... .
        origin = urlunsplit((parsed.scheme or "https", parsed.netloc, "", "", "")).rstrip("/")
        if not parsed.netloc:
            raise ValueError(f"Invalid Zoho API domain: {api_domain!r}")
        self.base_url = f"{origin}/crm/v8"

    MODULES = {
        "contacts": "Contacts",
        "leads": "Leads",
        "deals": "Deals",
        "accounts": "Accounts",
    }

    # Verified CRM API field names.  Keeping this list in the shared client
    # means API routes and both sync paths use the same valid projection.
    # Zoho's Get Records API requires fields and accepts at most 50 per call.
    DEFAULT_FIELDS = {
        "Contacts": [
            "id", "First_Name", "Last_Name", "Full_Name", "Email", "Phone",
            "Mobile", "Account_Name", "Lead_Source", "Created_Time", "Modified_Time",
        ],
        "Leads": [
            "id", "First_Name", "Last_Name", "Full_Name", "Company", "Email",
            "Phone", "Mobile", "Lead_Status", "Lead_Source", "Created_Time",
            "Modified_Time",
        ],
        "Deals": [
            "id", "Deal_Name", "Account_Name", "Stage", "Amount", "Closing_Date",
            "Probability", "Type", "Lead_Source", "Created_Time", "Modified_Time",
        ],
        "Accounts": [
            "id", "Account_Name", "Website", "Phone", "Billing_City", "Billing_State",
            "Billing_Country", "Industry", "Annual_Revenue", "Created_Time",
            "Modified_Time",
        ],
    }

    @classmethod
    def _record_fields(cls, module: str, fields: Optional[List[str]]) -> List[str]:
        """Return a de-duplicated, module-valid projection within Zoho's limit."""
        selected = fields or cls.DEFAULT_FIELDS.get(module, [])
        required = ["id", "Created_Time", "Modified_Time"]
        result: List[str] = []
        for field in [*required, *selected]:
            field = field.strip()
            if field and field not in result:
                result.append(field)
        return result[:50]

    @classmethod
    def _module_name(cls, module: str) -> str:
        normalized = module.strip().strip("/").lower()
        try:
            return cls.MODULES[normalized]
        except KeyError:
            if module.strip() in cls.MODULES.values():
                return module.strip()
            # Preserve the provider client's existing behavior for modules not
            # covered by the sync mapping; Zoho returns the authoritative API
            # error for those requests.
            return module.strip().strip("/")

    async def _execute_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        attempt: int = 1,
    ) -> Dict[str, Any]:
        """
        Execute an authenticated request with rate-limit retries and automatic 401 token refresh.
        """
        token = await self.token_manager.get_valid_access_token(self.integration, self.session)

        req_headers = {
            "Authorization": f"Zoho-oauthtoken {token}",
            "Accept": "application/json",
        }
        if headers:
            req_headers.update(headers)

        url = f"{self.base_url}/{path.lstrip('/')}"
        safe_params = sanitize_data(params or {})
        logger.debug("Zoho CRM request: method=%s endpoint=%s params=%s", method, url, safe_params)

        async with httpx.AsyncClient(timeout=self.timeout) as http_client:
            try:
                response = await http_client.request(
                    method=method,
                    url=url,
                    params=params,
                    headers=req_headers,
                    json=json_data,
                )
            except httpx.RequestError as exc:
                logger.error(f"Network error communicating with Zoho CRM ({url}): {exc}")
                raise ZohoAPIError(f"Network communication failure: {exc}")

        # 1. Handle HTTP 204 No Content (empty dataset in Zoho)
        if response.status_code == 204:
            return {"data": [], "info": {"count": 0, "more_records": False}}

        # 2. Handle HTTP 401 Unauthorized (reactive token refresh)
        if response.status_code == 401 and attempt == 1:
            logger.warning(
                f"Zoho returned 401 Unauthorized for integration {self.integration.id}. "
                "Triggering token refresh and retrying..."
            )
            try:
                await self.token_manager.refresh_access_token(self.integration, self.session)
                return await self._execute_request(
                    method=method,
                    path=path,
                    params=params,
                    headers=headers,
                    json_data=json_data,
                    attempt=attempt + 1,
                )
            except ZohoTokenExpiredError:
                raise
            except Exception as e:
                logger.error(f"Failed to refresh token during 401 retry: {e}")
                raise ZohoAPIError(f"Authentication failed with Zoho: {e}", status_code=401)

        # 3. Handle Rate Limiting (HTTP 429)
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            wait_time = float(retry_after) if retry_after and retry_after.isdigit() else (2.0 ** attempt)

            if attempt <= 2:
                logger.warning(f"Zoho rate limit hit (HTTP 429). Backing off for {wait_time}s (attempt {attempt})...")
                await asyncio.sleep(wait_time)
                return await self._execute_request(
                    method=method,
                    path=path,
                    params=params,
                    headers=headers,
                    json_data=json_data,
                    attempt=attempt + 1,
                )
            else:
                logger.error("Zoho rate limit exceeded maximum retry attempts.")
                raise ZohoRateLimitError("Zoho API rate limit exceeded. Please try again later.", status_code=429)

        # Parse JSON payload
        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}

        # 4. Handle Error Responses
        if response.status_code >= 400:
            error_payload = data if isinstance(data, dict) else {"raw": data}
            error_code = error_payload.get("code") or "API_ERROR"
            error_message = error_payload.get("message") or f"HTTP {response.status_code}"
            details = sanitize_data(error_payload)
            provider_details = details.get("details") if isinstance(details, dict) else None
            missing_param = (
                provider_details.get("param_name")
                if isinstance(provider_details, dict)
                else None
            )
            if missing_param:
                error_message = f"{error_message} (missing parameter: {missing_param})"
            logger.error(
                f"Zoho API returned error {response.status_code} [{error_code}]: "
                f"{error_message}; endpoint={url}; params={safe_params}; details={details}"
            )
            raise ZohoAPIError(
                message=f"Zoho CRM API error ({error_code}): {error_message}",
                status_code=response.status_code,
                details=details,
            )

        return data

    async def fetch_records(
        self,
        module: str,
        page: int = 1,
        per_page: int = 200,
        fields: Optional[List[str]] = None,
        modified_since: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch a paginated list of records from any Zoho CRM module (Contacts, Leads, Deals, Accounts).
        """
        params: Dict[str, Any] = {
            "page": max(1, page),
            "per_page": min(200, max(1, per_page)),
        }
        module_name = self._module_name(module)
        params["fields"] = ",".join(self._record_fields(module_name, fields))

        headers: Dict[str, str] = {}
        if modified_since:
            headers["If-Modified-Since"] = modified_since

        return await self._execute_request(
            method="GET",
            path=module_name,
            params=params,
            headers=headers if headers else None,
        )

    async def get_record(
        self,
        module: str,
        record_id: str,
        fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve an individual record by module name and record ID.
        """
        params: Dict[str, Any] = {}
        if fields:
            params["fields"] = ",".join(fields)

        return await self._execute_request(
            method="GET",
            path=f"{self._module_name(module)}/{record_id}",
            params=params if params else None,
        )

    async def get_organization(self) -> Dict[str, Any]:
        """
        Retrieve Zoho CRM organization profile.
        """
        return await self._execute_request(method="GET", path="org")

