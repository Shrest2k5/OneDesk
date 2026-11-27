from datetime import datetime, timedelta, timezone
import threading
from typing import Any, Dict, Optional
import urllib.parse
import uuid

import httpx
import jwt

from app.core.config import settings
from app.core.logging import logger
from app.core.security import sanitize_data
from app.integrations.business_central.exceptions import BusinessCentralOAuthError


_consumed_state_nonces: Dict[str, datetime] = {}
_state_lock = threading.Lock()


def _consume_nonce(nonce: str, expires_at: datetime) -> bool:
    now = datetime.now(timezone.utc)
    with _state_lock:
        for key, expiry in list(_consumed_state_nonces.items()):
            if expiry < now:
                del _consumed_state_nonces[key]
        if nonce in _consumed_state_nonces:
            return True
        _consumed_state_nonces[nonce] = expires_at
        return False


class BusinessCentralOAuthClient:
    """Microsoft Entra authorization-code client for Business Central."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        tenant_id: Optional[str] = None,
        authority_url: Optional[str] = None,
        scopes: Optional[str] = None,
    ) -> None:
        self.client_id = client_id or settings.BUSINESS_CENTRAL_CLIENT_ID
        self.client_secret = client_secret or settings.BUSINESS_CENTRAL_CLIENT_SECRET
        self.redirect_uri = redirect_uri or settings.BUSINESS_CENTRAL_REDIRECT_URI
        self.tenant_id = tenant_id or settings.BUSINESS_CENTRAL_TENANT_ID
        self.authority_url = (authority_url or settings.BUSINESS_CENTRAL_AUTHORITY_URL).rstrip("/")
        self.scopes = scopes or settings.BUSINESS_CENTRAL_SCOPES

    @property
    def authorize_endpoint(self) -> str:
        return f"{self.authority_url}/{self.tenant_id}/oauth2/v2.0/authorize"

    @property
    def token_endpoint(self) -> str:
        return f"{self.authority_url}/{self.tenant_id}/oauth2/v2.0/token"

    def _require_configuration(self) -> None:
        if not self.client_id or not self.client_secret or not self.redirect_uri:
            raise BusinessCentralOAuthError(
                "Business Central OAuth credentials are not configured.", status_code=503
            )

    def generate_state(
        self,
        user_id: uuid.UUID,
        connection_name: str,
        integration_id: Optional[uuid.UUID] = None,
    ) -> str:
        payload: Dict[str, Any] = {
            "sub": str(user_id),
            "connection_name": connection_name,
            "type": "business_central_oauth_state",
            "product": "erp",
            "nonce": uuid.uuid4().hex,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        }
        if integration_id is not None:
            payload["integration_id"] = str(integration_id)
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    def validate_state(self, state: str) -> Dict[str, Any]:
        try:
            payload = jwt.decode(state, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            if payload.get("type") != "business_central_oauth_state" or payload.get("product") != "erp":
                raise BusinessCentralOAuthError("Invalid Business Central OAuth state token type.")
            nonce = payload.get("nonce")
            if not nonce:
                raise BusinessCentralOAuthError("Business Central OAuth state is missing its nonce.")
            exp = payload.get("exp")
            expires_at = datetime.fromtimestamp(exp, tz=timezone.utc) if exp else datetime.now(timezone.utc)
            if _consume_nonce(nonce, expires_at):
                raise BusinessCentralOAuthError("Business Central OAuth state has already been used.")
            return payload
        except BusinessCentralOAuthError:
            raise
        except jwt.ExpiredSignatureError as exc:
            raise BusinessCentralOAuthError("Business Central OAuth state has expired.") from exc
        except jwt.PyJWTError as exc:
            raise BusinessCentralOAuthError("Invalid or tampered Business Central OAuth state.") from exc

    def generate_authorization_url(
        self,
        user_id: uuid.UUID,
        connection_name: str,
        integration_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, str]:
        self._require_configuration()
        state = self.generate_state(user_id, connection_name, integration_id)
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "response_mode": "query",
            "scope": self.scopes,
            "state": state,
        }
        return {"authorization_url": f"{self.authorize_endpoint}?{urllib.parse.urlencode(params)}", "state": state}

    async def exchange_code(self, code: str) -> Dict[str, Any]:
        self._require_configuration()
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "scope": self.scopes,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(self.token_endpoint, data=data)
            except httpx.TimeoutException as exc:
                raise BusinessCentralOAuthError("Communication timeout with Microsoft Entra ID.") from exc
            except httpx.RequestError as exc:
                logger.warning("Business Central OAuth token exchange network failure: %s", type(exc).__name__)
                raise BusinessCentralOAuthError("Network communication failure with Microsoft Entra ID.") from exc
        try:
            result = response.json()
        except Exception:
            result = {}
        if response.status_code != 200 or not result.get("access_token"):
            error_code = result.get("error", f"HTTP {response.status_code}")
            raise BusinessCentralOAuthError(
                f"Business Central authorization failed: {error_code}",
                status_code=response.status_code,
                details=sanitize_data(result),
            )
        return result

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        self._require_configuration()
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": self.scopes,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(self.token_endpoint, data=data)
            except httpx.TimeoutException as exc:
                raise BusinessCentralOAuthError("Communication timeout refreshing Microsoft access token.") from exc
            except httpx.RequestError as exc:
                logger.warning("Business Central token refresh network failure: %s", type(exc).__name__)
                raise BusinessCentralOAuthError("Network communication failure refreshing Microsoft access token.") from exc
        try:
            result = response.json()
        except Exception:
            result = {}
        if response.status_code != 200 or not result.get("access_token"):
            error_code = result.get("error", f"HTTP {response.status_code}")
            if error_code in {"invalid_grant", "invalid_client", "interaction_required", "consent_required"}:
                raise BusinessCentralOAuthError(
                    "Business Central refresh token is invalid or revoked.",
                    status_code=response.status_code,
                    details=sanitize_data(result),
                )
            raise BusinessCentralOAuthError(
                f"Business Central token refresh failed: {error_code}",
                status_code=response.status_code,
                details=sanitize_data(result),
            )
        return result
