import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import uuid
import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.zoho.client import ZohoClient
from app.integrations.zoho.exceptions import (
    ZohoAPIError,
    ZohoRateLimitError,
    ZohoTokenExpiredError,
)
from app.integrations.zoho.token_manager import ZohoTokenManager, zoho_token_manager
from app.models.integration import Integration
from app.models.user import User


@pytest.fixture
async def sample_integration(db_session: AsyncSession) -> Integration:
    """Fixture providing a persisted Integration with valid tokens."""
    user = User(
        name="CRM Engineer",
        email=f"crm_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password="hashed_pw",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    integration = Integration(
        user_id=user.id,
        provider="zoho",
        connection_name="Test Enterprise Zoho",
        external_account_id="org_998811",
        access_token="1000.initial_access_token",
        refresh_token="1000.valid_refresh_token",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        api_domain="https://www.zohoapis.com",
        status="active",
    )
    db_session.add(integration)
    await db_session.commit()
    await db_session.refresh(integration)
    return integration


def test_token_expiration_logic(sample_integration: Integration):
    """Test token expiration logic with safety buffer."""
    manager = ZohoTokenManager()

    # Valid for 1 hour: not expired
    assert manager.is_token_expired(sample_integration) is False

    # Expiring in 2 minutes: within 5-minute safety buffer, treated as expired
    sample_integration.token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=2)
    assert manager.is_token_expired(sample_integration) is True

    # In the past: expired
    sample_integration.token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    assert manager.is_token_expired(sample_integration) is True


@pytest.mark.asyncio
async def test_token_refresh_success(sample_integration: Integration, db_session: AsyncSession):
    """Test successful token refresh updating the database record."""
    manager = ZohoTokenManager()
    # Mark token as expired
    sample_integration.token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=10)

    mock_refresh_response = {
        "access_token": "1000.fresh_new_access_token_999",
        "api_domain": "https://www.zohoapis.com",
        "expires_in": 3600,
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = httpx.Response(
            status_code=200,
            json=mock_refresh_response,
            request=httpx.Request("POST", "https://accounts.zoho.com/oauth/v2/token"),
        )
        mock_post.return_value = mock_response

        new_token = await manager.refresh_access_token(sample_integration, db_session)

        assert new_token == "1000.fresh_new_access_token_999"
        assert sample_integration.access_token == "1000.fresh_new_access_token_999"
        assert sample_integration.status == "active"


@pytest.mark.asyncio
async def test_token_refresh_revoked(sample_integration: Integration, db_session: AsyncSession):
    """Test handling of revoked refresh token marking status as revoked."""
    manager = ZohoTokenManager()
    # Mark token as expired
    sample_integration.token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=10)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = httpx.Response(
            status_code=400,
            json={"error": "invalid_code"},
            request=httpx.Request("POST", "https://accounts.zoho.com/oauth/v2/token"),
        )
        mock_post.return_value = mock_response

        with pytest.raises(ZohoTokenExpiredError) as exc_info:
            await manager.refresh_access_token(sample_integration, db_session)

        assert "revoked or invalid" in str(exc_info.value)
        assert sample_integration.status == "revoked"


@pytest.mark.asyncio
async def test_zoho_client_fetch_records_success(sample_integration: Integration, db_session: AsyncSession):
    """Test ZohoClient fetching contacts records successfully."""
    client = ZohoClient(sample_integration, db_session)

    mock_crm_data = {
        "data": [
            {"id": "111", "First_Name": "Alice", "Last_Name": "Smith", "Email": "alice@corp.com"},
            {"id": "222", "First_Name": "Bob", "Last_Name": "Jones", "Email": "bob@corp.com"},
        ],
        "info": {"per_page": 200, "count": 2, "page": 1, "more_records": False},
    }

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = httpx.Response(
            status_code=200,
            json=mock_crm_data,
            request=httpx.Request("GET", "https://www.zohoapis.com/crm/v8/Contacts"),
        )

        result = await client.fetch_records(
            module="Contacts",
            page=1,
            per_page=200,
            fields=["id", "First_Name", "Last_Name", "Email"],
            modified_since="2026-01-01T00:00:00Z",
        )

        assert len(result["data"]) == 2
        assert result["data"][0]["Email"] == "alice@corp.com"
        assert result["info"]["count"] == 2


@pytest.mark.asyncio
async def test_zoho_client_supplies_module_fields_and_incremental_header(
    sample_integration: Integration, db_session: AsyncSession
):
    """Get Records requests always include a valid, bounded field projection."""
    client = ZohoClient(sample_integration, db_session)

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = httpx.Response(
            status_code=200,
            json={"data": [], "info": {"more_records": False}},
            request=httpx.Request("GET", "https://www.zohoapis.com/crm/v8/Contacts"),
        )

        for module in ("contacts", "leads", "deals", "accounts"):
            await client.fetch_records(module=module, modified_since="2026-01-01T00:00:00Z")
            request_kwargs = mock_req.call_args.kwargs
            fields = request_kwargs["params"]["fields"].split(",")
            assert fields[0] == "id"
            assert "Created_Time" in fields
            assert "Modified_Time" in fields
            assert len(fields) <= 50
            assert request_kwargs["headers"]["If-Modified-Since"] == "2026-01-01T00:00:00Z"


@pytest.mark.asyncio
async def test_zoho_client_caps_explicit_fields(sample_integration: Integration, db_session: AsyncSession):
    client = ZohoClient(sample_integration, db_session)
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = httpx.Response(
            status_code=200,
            json={"data": [], "info": {"more_records": False}},
            request=httpx.Request("GET", "https://www.zohoapis.com/crm/v8/Deals"),
        )
        await client.fetch_records(module="deals", fields=[f"Custom_{i}" for i in range(100)])
        fields = mock_req.call_args.kwargs["params"]["fields"].split(",")
        assert len(fields) == 50
        assert fields[:3] == ["id", "Created_Time", "Modified_Time"]


@pytest.mark.asyncio
async def test_zoho_client_fetch_records_empty_204(sample_integration: Integration, db_session: AsyncSession):
    """Test ZohoClient handling HTTP 204 No Content gracefully."""
    client = ZohoClient(sample_integration, db_session)

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = httpx.Response(
            status_code=204,
            request=httpx.Request("GET", "https://www.zohoapis.com/crm/v8/Leads"),
        )

        result = await client.fetch_records(module="Leads")
        assert result["data"] == []
        assert result["info"]["count"] == 0


@pytest.mark.asyncio
async def test_zoho_client_reactive_401_refresh(sample_integration: Integration, db_session: AsyncSession):
    """Test automatic token refresh and request retry on HTTP 401."""
    client = ZohoClient(sample_integration, db_session)

    resp_401 = httpx.Response(
        status_code=401,
        json={"code": "INVALID_OAUTHTOKEN", "message": "Access token has expired", "status": "error"},
        request=httpx.Request("GET", "https://www.zohoapis.com/crm/v8/Contacts"),
    )
    resp_200 = httpx.Response(
        status_code=200,
        json={"data": [{"id": "999", "Last_Name": "Retried Record"}]},
        request=httpx.Request("GET", "https://www.zohoapis.com/crm/v8/Contacts"),
    )

    with patch.object(
        client.token_manager,
        "refresh_access_token",
        new_callable=AsyncMock,
        return_value="1000.new_token_after_401",
    ) as mock_refresh, patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_req:
        mock_req.side_effect = [resp_401, resp_200]

        result = await client.fetch_records(module="Contacts")

        assert mock_refresh.called
        assert len(result["data"]) == 1
        assert result["data"][0]["id"] == "999"


@pytest.mark.asyncio
async def test_zoho_client_api_error_handling(sample_integration: Integration, db_session: AsyncSession):
    """Test ZohoClient parsing API errors and raising ZohoAPIError."""
    client = ZohoClient(sample_integration, db_session)

    error_resp = httpx.Response(
        status_code=400,
        json={"code": "INVALID_MODULE", "message": "the module name specified is invalid", "status": "error", "details": {"param_name": "fields"}},
        request=httpx.Request("GET", "https://www.zohoapis.com/crm/v8/UnknownModule"),
    )

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = error_resp

        with pytest.raises(ZohoAPIError) as exc_info:
            await client.fetch_records(module="UnknownModule")

        assert "INVALID_MODULE" in str(exc_info.value)
        assert "missing parameter: fields" in str(exc_info.value)
        assert exc_info.value.status_code == 400
        assert exc_info.value.details["details"]["param_name"] == "fields"
