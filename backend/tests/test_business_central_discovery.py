from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import uuid

import httpx
import pytest
from httpx import AsyncClient

from app.integrations.business_central.client import BusinessCentralAPIError, BusinessCentralClient
from app.integrations.business_central.integration import business_central_integration
from app.models.integration import Integration
from app.models.user import User


class FakeTokenManager:
    def __init__(self, token="token"):
        self.token = token
        self.refreshes = 0

    async def get_valid_access_token(self, integration, session):
        return self.token

    async def refresh_access_token(self, integration, session, force=False):
        self.refreshes += 1
        self.token = "refreshed-token"
        integration.access_token = self.token
        return self.token


def integration_for_client():
    return Integration(
        id=uuid.uuid4(), user_id=uuid.uuid4(), provider="business_central", product="erp",
        connection_name="BC", access_token="token", refresh_token="refresh",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1), status="pending",
    )


def response(status, payload, url):
    return httpx.Response(status, json=payload, request=httpx.Request("GET", url))


@pytest.mark.asyncio
async def test_environment_discovery_success():
    integration = integration_for_client()
    manager = FakeTokenManager()
    client = BusinessCentralClient(integration, None, manager)
    url = client._admin_url("applications/BusinessCentral/environments")
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=response(200, {"value": [{"name": "sandbox", "type": "Sandbox", "status": "Active"}]}, url)):
        result = await client.list_environments()
    assert result["source"] == "admin_center"
    assert result["data"][0]["name"] == "sandbox"


@pytest.mark.asyncio
async def test_admin_center_denied_uses_only_verified_production_fallback():
    integration = integration_for_client()
    manager = FakeTokenManager()
    client = BusinessCentralClient(integration, None, manager)
    admin_url = client._admin_url("applications/BusinessCentral/environments")
    production_url = client._api_url("production")
    calls = [
        response(403, {"error": {"message": "forbidden"}}, admin_url),
        response(200, {"value": [{"id": "company"}]}, production_url),
    ]
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, side_effect=calls):
        result = await client.list_environments()
    assert result["source"] == "verified_production_fallback"
    assert result["data"] == [{"name": "production", "type": "production", "status": "verified"}]


@pytest.mark.asyncio
async def test_admin_center_denied_and_production_denied_returns_error():
    integration = integration_for_client()
    client = BusinessCentralClient(integration, None, FakeTokenManager())
    calls = [
        response(403, {}, client._admin_url("applications/BusinessCentral/environments")),
        response(403, {}, client._api_url("production")),
    ]
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, side_effect=calls):
        with pytest.raises(BusinessCentralAPIError) as exc:
            await client.list_environments()
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_company_discovery_normalizes_and_follows_odata_next_link():
    integration = integration_for_client()
    client = BusinessCentralClient(integration, None, FakeTokenManager())
    first_url = client._api_url("sandbox")
    next_url = first_url + "?$skiptoken=abc"
    calls = [
        response(200, {"value": [{"id": " c1 ", "displayName": "Company One"}], "@odata.nextLink": next_url}, first_url),
        response(200, {"value": [{"id": "c2", "name": "Company Two"}]}, next_url),
    ]
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, side_effect=calls) as request:
        companies = await client.list_companies("sandbox")
    assert [item["id"] for item in companies] == ["c1", "c2"]
    assert [item["display_name"] for item in companies] == ["Company One", "Company Two"]
    assert request.await_count == 2


@pytest.mark.asyncio
async def test_empty_company_response_is_valid_empty_list():
    integration = integration_for_client()
    client = BusinessCentralClient(integration, None, FakeTokenManager())
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=response(200, {"value": []}, client._api_url("production"))):
        assert await client.list_companies("production") == []


@pytest.mark.asyncio
async def test_company_request_refreshes_once_after_401():
    integration = integration_for_client()
    manager = FakeTokenManager()
    client = BusinessCentralClient(integration, None, manager)
    url = client._api_url("production")
    calls = [response(401, {}, url), response(200, {"value": []}, url)]
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, side_effect=calls):
        assert await client.list_companies("production") == []
    assert manager.refreshes == 1


@pytest.mark.asyncio
async def test_unsafe_odata_next_link_is_rejected():
    integration = integration_for_client()
    client = BusinessCentralClient(integration, None, FakeTokenManager())
    url = client._api_url("production")
    payload = {"value": [], "@odata.nextLink": "https://attacker.example/next"}
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=response(200, payload, url)):
        with pytest.raises(BusinessCentralAPIError, match="unsafe"):
            await client.list_companies("production")


@pytest.mark.asyncio
async def test_company_selection_rejects_unauthorized_integration(client: AsyncClient):
    response = await client.get(f"/api/v1/integrations/business-central/{uuid.uuid4()}/companies?environment_name=production")
    assert response.status_code in {401, 403}


@pytest.mark.asyncio
async def test_pending_sync_is_rejected(db_session):
    from app.services.sync_service import SyncService

    integration = integration_for_client()
    user = User(id=integration.user_id, name="BC", email=f"{integration.user_id}@example.com", hashed_password="hashed")
    db_session.add(user)
    await db_session.commit()
    with pytest.raises(ValueError, match="select a company"):
        await SyncService(db_session).sync_resource(integration, "companies", incremental=False)


@pytest.mark.asyncio
async def test_successful_company_selection_and_multiple_companies(client: AsyncClient, db_session):
    email = f"bc_{uuid.uuid4().hex}@example.com"
    await client.post("/api/v1/auth/register", json={"name": "BC", "email": email, "password": "Password123!"})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    user = (await db_session.execute(__import__("sqlalchemy").select(User).where(User.email == email))).scalar_one()
    first = Integration(
        user_id=user.id, provider="business_central", product="erp", connection_name="First",
        access_token="token", refresh_token="refresh", status="pending", business_central_tenant_id="tenant",
    )
    second = Integration(
        user_id=user.id, provider="business_central", product="erp", connection_name="Second",
        access_token="token", refresh_token="refresh", status="pending", business_central_tenant_id="tenant",
    )
    db_session.add_all([first, second])
    await db_session.commit()
    companies = [{"id": "company-1", "display_name": "Company One", "name": "Company One", "raw": {}}, {"id": "company-2", "display_name": "Company Two", "name": "Company Two", "raw": {}}]
    with patch.object(business_central_integration, "discover_companies", new_callable=AsyncMock, return_value=companies):
        selected = await client.put(f"/api/v1/integrations/business-central/{first.id}/companies/company-1/select?environment_name=sandbox", headers=headers)
        selected_two = await client.put(f"/api/v1/integrations/business-central/{second.id}/companies/company-2/select?environment_name=sandbox", headers=headers)
    assert selected.status_code == 200
    assert selected_two.status_code == 200
    await db_session.refresh(first)
    await db_session.refresh(second)
    assert first.status == second.status == "active"
    assert first.business_central_company_id == "company-1"
    assert second.business_central_company_id == "company-2"
