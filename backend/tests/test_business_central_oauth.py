from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse
from unittest.mock import AsyncMock, patch
import uuid

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import cast, select, String

from app.core.config import settings
from app.integrations.business_central.exceptions import BusinessCentralOAuthError, BusinessCentralTokenExpiredError
from app.integrations.business_central.integration import BusinessCentralIntegration
from app.integrations.business_central.oauth import BusinessCentralOAuthClient
from app.integrations.business_central.token_manager import BusinessCentralTokenManager
from app.models.integration import Integration
from app.models.sync_history import SyncHistory
from app.models.user import User
from app.integrations.business_central.integration import business_central_integration


def configured_client() -> BusinessCentralOAuthClient:
    return BusinessCentralOAuthClient(
        client_id="bc-client",
        client_secret="bc-secret",
        redirect_uri="https://onedesk.example.com/api/v1/integrations/business-central/callback",
        tenant_id="organizations",
    )


def test_authorization_url_construction():
    oauth = configured_client()
    result = oauth.generate_authorization_url(uuid.uuid4(), "BC Production")
    parsed = urlparse(result["authorization_url"])
    params = parse_qs(parsed.query)
    assert parsed.netloc == "login.microsoftonline.com"
    assert parsed.path == "/organizations/oauth2/v2.0/authorize"
    assert params["client_id"] == ["bc-client"]
    assert params["response_type"] == ["code"]
    assert "offline_access" in params["scope"][0]
    assert "Financials.ReadWrite.All" in params["scope"][0]


def test_state_validation_and_replay_protection():
    oauth = configured_client()
    state = oauth.generate_state(uuid.uuid4(), "BC")
    assert oauth.validate_state(state)["product"] == "erp"
    with pytest.raises(BusinessCentralOAuthError, match="already been used"):
        oauth.validate_state(state)


def test_expired_and_tampered_state_rejected():
    oauth = configured_client()
    with pytest.raises(BusinessCentralOAuthError, match="expired"):
        expired = oauth.generate_state(uuid.uuid4(), "BC")
        payload = __import__("jwt").decode(expired, options={"verify_signature": False})
        payload["exp"] = datetime.now(timezone.utc) - timedelta(minutes=1)
        expired = __import__("jwt").encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        oauth.validate_state(expired)
    with pytest.raises(BusinessCentralOAuthError):
        oauth.validate_state("not-a-valid-state")


@pytest.mark.asyncio
async def test_successful_authorization_code_exchange():
    oauth = configured_client()
    response = httpx.Response(
        200,
        json={"access_token": "access", "refresh_token": "refresh", "expires_in": 3600},
        request=httpx.Request("POST", oauth.token_endpoint),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=response) as post:
        result = await oauth.exchange_code("one-time-code")
    assert result["access_token"] == "access"
    post.assert_awaited_once()
    assert post.call_args.kwargs["data"]["client_secret"] == "bc-secret"


@pytest.mark.asyncio
async def test_refresh_rotation_and_expiry(db_session):
    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, name="BC Owner", email=f"{user_id}@example.com", hashed_password="hashed"))
    await db_session.commit()
    integration = Integration(
        user_id=user_id, provider="business_central", product="erp", connection_name="BC",
        access_token="old-access", refresh_token="old-refresh",
        token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1), status="active",
    )
    db_session.add(integration)
    await db_session.commit()
    manager = BusinessCentralTokenManager(configured_client())
    with patch.object(manager.oauth_client, "refresh_token", new_callable=AsyncMock, return_value={
        "access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 3600,
    }):
        assert await manager.refresh_access_token(integration, db_session) == "new-access"
    assert integration.refresh_token == "new-refresh"
    assert integration.status == "active"


@pytest.mark.asyncio
async def test_refresh_failure_marks_invalid_grant_revoked(db_session):
    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, name="BC Owner", email=f"{user_id}@example.com", hashed_password="hashed"))
    await db_session.commit()
    integration = Integration(
        user_id=user_id, provider="business_central", product="erp", connection_name="BC",
        access_token="old-access", refresh_token="old-refresh",
        token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1), status="active",
    )
    db_session.add(integration)
    await db_session.commit()
    manager = BusinessCentralTokenManager(configured_client())
    with patch.object(manager.oauth_client, "refresh_token", new_callable=AsyncMock, side_effect=BusinessCentralOAuthError("invalid or revoked", status_code=400)):
        with pytest.raises(BusinessCentralTokenExpiredError):
            await manager.refresh_access_token(integration, db_session)
    assert integration.status == "revoked"


@pytest.mark.asyncio
async def test_reauthorization_preserves_integration_and_history(db_session):
    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, name="BC Owner", email=f"{user_id}@example.com", hashed_password="hashed"))
    await db_session.commit()
    integration = Integration(
        user_id=user_id, provider="business_central", product="erp", connection_name="Old BC",
        access_token="old-access", refresh_token="old-refresh", status="active",
    )
    db_session.add(integration)
    await db_session.commit()
    history = SyncHistory(integration_id=integration.id, resource_type="companies", status="completed")
    db_session.add(history)
    await db_session.commit()
    oauth = configured_client()
    provider = BusinessCentralIntegration(oauth)
    state = oauth.generate_state(user_id, "Reauthorized BC", integration.id)
    with patch.object(oauth, "exchange_code", new_callable=AsyncMock, return_value={
        "access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 3600,
    }):
        updated = await provider.handle_oauth_callback("code", state, db_session)
    assert updated.id == integration.id
    assert updated.refresh_token == "new-refresh"
    assert await db_session.get(SyncHistory, history.id) is not None


@pytest.mark.asyncio
async def test_callback_never_returns_secrets(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={"name": "BC", "email": "bc@example.com", "password": "Password123!"})
    login = await client.post("/api/v1/auth/login", json={"email": "bc@example.com", "password": "Password123!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    with patch.object(business_central_integration.oauth_client, "client_id", "bc-client"), patch.object(business_central_integration.oauth_client, "client_secret", "bc-secret"), patch.object(business_central_integration.oauth_client, "redirect_uri", "https://onedesk.example.com/api/v1/integrations/business-central/callback"):
        connect = await client.post("/api/v1/integrations/business-central/connect", json={"connection_name": "BC"}, headers=headers)
    assert connect.status_code == 200
    state = connect.json()["state"]
    with patch.object(BusinessCentralOAuthClient, "exchange_code", new_callable=AsyncMock, return_value={"access_token": "secret-access", "refresh_token": "secret-refresh", "expires_in": 3600}):
        callback = await client.get(f"/api/v1/integrations/business-central/callback?code=secret-code&state={state}")
    assert callback.status_code == 303
    location = callback.headers["location"]
    assert "secret" not in location
    integrations = await client.get("/api/v1/integrations", headers=headers)
    assert "secret-access" not in integrations.text
    assert "secret-refresh" not in integrations.text
