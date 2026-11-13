from datetime import datetime, timedelta, timezone
import threading
from typing import Any, Dict, Optional, Set
import urllib.parse
import uuid
import httpx
import jwt

from app.core.config import settings
from app.core.logging import logger
from app.core.security import sanitize_data
from app.integrations.zoho.exceptions import ZohoOAuthError

# Supported Zoho Data Centres and corresponding authentication & API base domains
ZOHO_DATA_CENTERS: Dict[str, Dict[str, str]] = {
    "us": {"accounts": "https://accounts.zoho.com", "api": "https://www.zohoapis.com"},
    "eu": {"accounts": "https://accounts.zoho.eu", "api": "https://www.zohoapis.eu"},
    "in": {"accounts": "https://accounts.zoho.in", "api": "https://www.zohoapis.in"},
    "cn": {"accounts": "https://accounts.zoho.com.cn", "api": "https://www.zohoapis.com.cn"},
    "au": {"accounts": "https://accounts.zoho.com.au", "api": "https://www.zohoapis.com.au"},
    "ca": {"accounts": "https://accounts.zoho.ca", "api": "https://www.zohoapis.ca"},
    "jp": {"accounts": "https://accounts.zoho.jp", "api": "https://www.zohoapis.jp"},
}


# Thread-safe in-memory store for consumed state tokens (single-use replay protection)
_consumed_state_nonces: Dict[str, datetime] = {}
_state_lock = threading.Lock()


def _is_nonce_consumed_and_record(nonce: str, exp_dt: datetime) -> bool:
    """
    Check if a state nonce has already been consumed, and if not, mark it as consumed.
    Cleans up expired entries periodically.
    """
    now = datetime.now(timezone.utc)
    with _state_lock:
        # Periodic cleanup of expired nonces
        expired_keys = [k for k, v in _consumed_state_nonces.items() if v < now]
        for k in expired_keys:
            del _consumed_state_nonces[k]

        if nonce in _consumed_state_nonces:
            return True

        _consumed_state_nonces[nonce] = exp_dt
        return False


class ZohoOAuthClient:
    """Handles Zoho OAuth 2.0 URL construction, CSRF state validation, and token exchanges."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        scopes: Optional[str] = None,
    ) -> None:
        self.client_id = client_id or settings.ZOHO_CLIENT_ID
        self.client_secret = client_secret or settings.ZOHO_CLIENT_SECRET
        self.redirect_uri = redirect_uri or settings.ZOHO_REDIRECT_URI
        self.scopes = scopes or settings.ZOHO_SCOPES

    @staticmethod
    def get_data_center_info(dc: Optional[str] = None) -> Dict[str, str]:
        """Resolve Zoho data center accounts and API base URLs."""
        if not dc and hasattr(settings, "ZOHO_DEFAULT_ACCOUNTS_URL") and settings.ZOHO_DEFAULT_ACCOUNTS_URL:
            for dc_name, dc_info in ZOHO_DATA_CENTERS.items():
                if dc_info["accounts"].rstrip("/") == settings.ZOHO_DEFAULT_ACCOUNTS_URL.rstrip("/"):
                    dc = dc_name
                    break
        dc_key = (dc or "in").lower().strip()
        if dc_key not in ZOHO_DATA_CENTERS:
            logger.warning(f"Unknown data center '{dc}', defaulting to 'in'.")
            dc_key = "in"
        return ZOHO_DATA_CENTERS[dc_key]

    def generate_state(
        self,
        user_id: uuid.UUID,
        connection_name: str,
        data_center: str = "us",
    ) -> str:
        """
        Generate a cryptographically signed OAuth state JWT token.
        Prevents CSRF and securely carries connection metadata through the external redirect.
        """
        payload = {
            "sub": str(user_id),
            "connection_name": connection_name,
            "dc": data_center.lower().strip(),
            "type": "zoho_oauth_state",
            "nonce": uuid.uuid4().hex,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            "iat": datetime.now(timezone.utc),
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    def validate_state(self, state: str) -> Dict[str, Any]:
        """
        Validate and decode the OAuth state token received from callback.
        Enforces cryptographic signature, expiration, and single-use replay protection.
        """
        try:
            payload = jwt.decode(
                state,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
            if payload.get("type") != "zoho_oauth_state":
                raise ZohoOAuthError("Invalid OAuth state token type.")

            nonce = payload.get("nonce")
            if not nonce:
                raise ZohoOAuthError("OAuth state missing security nonce.")

            exp_timestamp = payload.get("exp")
            exp_dt = (
                datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
                if exp_timestamp
                else datetime.now(timezone.utc) + timedelta(minutes=15)
            )

            # Replay protection: verify nonce has not been consumed yet
            if _is_nonce_consumed_and_record(nonce, exp_dt):
                logger.warning("Zoho OAuth state replay attempt detected.")
                raise ZohoOAuthError("OAuth state has already been used (replay detected). Please re-initiate connection.")

            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Zoho OAuth state token expired.")
            raise ZohoOAuthError("OAuth authorization session expired. Please re-initiate connection.")
        except jwt.PyJWTError as e:
            logger.warning(f"Zoho OAuth state validation failed: {e}")
            raise ZohoOAuthError("Invalid or tampered OAuth state parameter.")

    def generate_authorization_url(
        self,
        user_id: uuid.UUID,
        connection_name: str,
        data_center: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Build the official Zoho OAuth 2.0 authorization URL.
        Includes prompt=consent and access_type=offline to guarantee refresh_token issuance.
        """
        dc_info = self.get_data_center_info(data_center)
        accounts_url = dc_info["accounts"]
        resolved_dc = "in"
        for k, v in ZOHO_DATA_CENTERS.items():
            if v["accounts"] == accounts_url:
                resolved_dc = k
                break

        state = self.generate_state(user_id, connection_name, resolved_dc)

        params = {
            "scope": self.scopes,
            "client_id": self.client_id,
            "response_type": "code",
            "access_type": "offline",
            "redirect_uri": self.redirect_uri,
            "prompt": "consent",
            "state": state,
        }
        query_string = urllib.parse.urlencode(params)
        auth_url = f"{accounts_url}/oauth/v2/auth?{query_string}"

        return {
            "authorization_url": auth_url,
            "state": state,
            "accounts_url": accounts_url,
            "data_center": resolved_dc,
        }

    async def exchange_code(
        self,
        code: str,
        accounts_url: str,
    ) -> Dict[str, Any]:
        """
        Exchange an OAuth authorization code for Zoho access and refresh tokens.
        Validates accounts endpoint URL against allowed Zoho domains.
        """
        # Validate target accounts domain to prevent SSRF
        valid_accounts_urls = {dc["accounts"].rstrip("/") for dc in ZOHO_DATA_CENTERS.values()}
        cleaned_accounts_url = accounts_url.rstrip("/")
        if cleaned_accounts_url not in valid_accounts_urls:
            logger.error("Rejected token exchange request to unapproved domain.")
            raise ZohoOAuthError("Invalid or unauthorized Zoho accounts domain.")

        token_endpoint = f"{cleaned_accounts_url}/oauth/v2/token"
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "code": code,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(token_endpoint, data=data)
            except httpx.TimeoutException:
                logger.error("Timeout during Zoho OAuth token exchange.")
                raise ZohoOAuthError("Communication timeout with Zoho Accounts service.")
            except httpx.RequestError as exc:
                logger.error(f"Network error during Zoho token exchange: {type(exc).__name__}")
                raise ZohoOAuthError("Network communication failure with Zoho Accounts.")

        try:
            result = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        except Exception:
            result = {}

        if response.status_code != 200 or "error" in result:
            err_msg = result.get("error", f"HTTP {response.status_code}")
            logger.error(f"Zoho token exchange error: {err_msg}")
            raise ZohoOAuthError(
                f"Zoho authorization failed: {err_msg}",
                status_code=response.status_code,
                details=sanitize_data(result),
            )

        access_token = result.get("access_token")
        refresh_token = result.get("refresh_token")
        api_domain = result.get("api_domain")
        expires_in = result.get("expires_in", 3600)

        if not access_token:
            raise ZohoOAuthError("Zoho token response missing access_token.")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "api_domain": api_domain,
            "expires_in": expires_in,
        }

    async def fetch_organization_id(
        self,
        access_token: str,
        api_domain: str,
    ) -> Optional[str]:
        """
        Retrieve the Zoho Organization ID to uniquely identify the connected ERP tenant.
        """
        url = f"{api_domain.rstrip('/')}/crm/v8/org"
        headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    orgs = data.get("org", [])
                    if orgs and isinstance(orgs, list):
                        return str(orgs[0].get("id"))
            except Exception as e:
                logger.warning(f"Could not fetch Zoho organization ID: {e}")
        return None

