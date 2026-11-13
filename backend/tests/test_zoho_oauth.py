from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid
import pytest
from httpx import AsyncClient

from app.integrations.zoho.exceptions import ZohoOAuthError
from app.integrations.zoho.oauth import ZohoOAuthClient


@pytest.mark.asyncio
async def test_zoho_connect_unauthorized(client: AsyncClient):
    """Test /api/v1/integrations/zoho/connect requires valid user authentication."""
    response = await client.post(
        "/api/v1/integrations/zoho/connect",
        json={"connection_name": "Test Zoho", "data_center": "us"},
    )
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_zoho_connect_success(client: AsyncClient):
    """Test generating Zoho OAuth authorization URL for different data centers."""
    # 1. Register and login
    await client.post(
        "/api/v1/auth/register",
        json={"name": "Integration User", "email": "zoho_user@example.com", "password": "Password123!"},
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "zoho_user@example.com", "password": "Password123!"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Connect US datacenter
    us_resp = await client.post(
        "/api/v1/integrations/zoho/connect",
        json={"connection_name": "US Production", "data_center": "us"},
        headers=headers,
    )
    assert us_resp.status_code == 200
    us_data = us_resp.json()
    assert "https://accounts.zoho.com/oauth/v2/auth" in us_data["authorization_url"]
    assert "prompt=consent" in us_data["authorization_url"]
    assert "access_type=offline" in us_data["authorization_url"]
    assert us_data["data_center"] == "us"
    assert us_data["state"] is not None

    # 3. Connect EU datacenter
    eu_resp = await client.post(
        "/api/v1/integrations/zoho/connect",
        json={"connection_name": "EU Production", "data_center": "eu"},
        headers=headers,
    )
    assert eu_resp.status_code == 200
    eu_data = eu_resp.json()
    assert "https://accounts.zoho.eu/oauth/v2/auth" in eu_data["authorization_url"]
    assert eu_data["data_center"] == "eu"

    # 4. Connect India (IN) datacenter
    in_resp = await client.post(
        "/api/v1/integrations/zoho/connect",
        json={"connection_name": "India Production", "data_center": "in"},
        headers=headers,
    )
    assert in_resp.status_code == 200
    in_data = in_resp.json()
    assert "https://accounts.zoho.in/oauth/v2/auth" in in_data["authorization_url"]
    assert in_data["data_center"] == "in"


def test_oauth_state_validation():
    """Test Zoho state token generation, validation, and tampering protection."""
    client = ZohoOAuthClient()
    user_id = uuid.uuid4()
    state = client.generate_state(user_id=user_id, connection_name="Test Org", data_center="eu")

    # Valid state
    payload = client.validate_state(state)
    assert payload["sub"] == str(user_id)
    assert payload["connection_name"] == "Test Org"
    assert payload["dc"] == "eu"

    # Tampered state
    with pytest.raises(ZohoOAuthError):
        client.validate_state(state + "tampered")


@pytest.mark.asyncio
async def test_zoho_callback_success(client: AsyncClient):
    """Test successful OAuth callback exchange and integration persistence."""
    # 1. Register and login
    await client.post(
        "/api/v1/auth/register",
        json={"name": "Zoho Admin", "email": "admin@zoho-corp.com", "password": "AdminPassword123!"},
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@zoho-corp.com", "password": "AdminPassword123!"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Initiate connection to obtain valid state
    connect_resp = await client.post(
        "/api/v1/integrations/zoho/connect",
        json={"connection_name": "Corporate Zoho CRM", "data_center": "us"},
        headers=headers,
    )
    state = connect_resp.json()["state"]

    # 3. Mock external Zoho API token exchange and org fetch
    mock_token_result = {
        "access_token": "1000.mock_access_token_abc123",
        "refresh_token": "1000.mock_refresh_token_xyz789",
        "api_domain": "https://www.zohoapis.com",
        "expires_in": 3600,
    }

    with patch.object(
        ZohoOAuthClient,
        "exchange_code",
        new_callable=AsyncMock,
        return_value=mock_token_result,
    ), patch.object(
        ZohoOAuthClient,
        "fetch_organization_id",
        new_callable=AsyncMock,
        return_value="org_8839210",
    ):
        callback_resp = await client.get(
            f"/api/v1/integrations/zoho/callback?code=mock_auth_code_123&state={state}"
        )
        assert callback_resp.status_code == 200
        data = callback_resp.json()
        assert data["provider"] == "zoho"
        assert data["connection_name"] == "Corporate Zoho CRM"
        assert data["status"] == "active"
        assert data["api_domain"] == "https://www.zohoapis.com"
        assert "integration_id" in data
        # Ensure tokens are never exposed
        assert "access_token" not in data
        assert "refresh_token" not in data


@pytest.mark.asyncio
async def test_zoho_callback_errors(client: AsyncClient):
    """Test callback rejection with error query parameter or missing parameters."""
    # User denied authorization
    denied_resp = await client.get("/api/v1/integrations/zoho/callback?error=access_denied")
    assert denied_resp.status_code == 400
    assert "denied or failed" in denied_resp.json()["detail"]

    # Missing state or code
    missing_resp = await client.get("/api/v1/integrations/zoho/callback?code=only_code")
    assert missing_resp.status_code == 400

    # Tampered state
    tampered_resp = await client.get(
        "/api/v1/integrations/zoho/callback?code=auth_code&state=invalid_tampered_state"
    )
    assert tampered_resp.status_code == 400
    assert "Invalid or tampered" in tampered_resp.json()["detail"]

