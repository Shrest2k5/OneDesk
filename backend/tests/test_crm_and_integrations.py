from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import uuid
import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import Integration
from app.models.user import User
from app.services.integration_service import IntegrationService


@pytest.fixture
async def authenticated_user_and_integration(client: AsyncClient, db_session: AsyncSession):
    """Fixture registering a user, logging in, and creating an active Zoho integration."""
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    # Register
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={"name": "CRM Tester", "email": email, "password": "Password123!"},
    )
    user_id = uuid.UUID(reg_resp.json()["id"])

    # Login
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create active integration directly in db
    integration = Integration(
        user_id=user_id,
        provider="zoho",
        connection_name="My Primary Zoho",
        external_account_id=f"org_{uuid.uuid4().hex[:6]}",
        access_token="1000.valid_test_token",
        refresh_token="1000.valid_refresh_token",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        api_domain="https://www.zohoapis.com",
        status="active",
    )
    db_session.add(integration)
    await db_session.commit()
    await db_session.refresh(integration)

    return {
        "user_id": user_id,
        "token": token,
        "headers": headers,
        "integration": integration,
    }


@pytest.mark.asyncio
async def test_integration_management_lifecycle(
    client: AsyncClient,
    authenticated_user_and_integration: dict,
    db_session: AsyncSession,
):
    """Test listing, inspecting, checking status, and deleting an integration."""
    headers = authenticated_user_and_integration["headers"]
    integration = authenticated_user_and_integration["integration"]

    # 1. List integrations
    list_resp = await client.get("/api/v1/integrations", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) >= 1
    assert items[0]["id"] == str(integration.id)
    assert "access_token" not in items[0]

    # 2. Get specific integration
    get_resp = await client.get(f"/api/v1/integrations/{integration.id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["connection_name"] == "My Primary Zoho"

    # 3. Check status (mock remote call)
    with patch.object(
        IntegrationService,
        "get_integration_status",
        new_callable=AsyncMock,
        return_value={
            "status": "connected",
            "provider": "zoho",
            "connection_name": "My Primary Zoho",
            "organization_name": "Acme Corp",
            "token_status": "valid",
        },
    ):
        status_resp = await client.get(f"/api/v1/integrations/{integration.id}/status", headers=headers)
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "connected"
        assert status_resp.json()["organization_name"] == "Acme Corp"

    # 4. Cross-tenant isolation check: create another user and verify they cannot access this integration
    reg2 = await client.post(
        "/api/v1/auth/register",
        json={"name": "Attacker", "email": f"attacker_{uuid.uuid4().hex[:4]}@example.com", "password": "Password123!"},
    )
    login2 = await client.post(
        "/api/v1/auth/login",
        json={"email": reg2.json()["email"], "password": "Password123!"},
    )
    attacker_headers = {"Authorization": f"Bearer {login2.json()['access_token']}"}

    unauth_resp = await client.get(f"/api/v1/integrations/{integration.id}", headers=attacker_headers)
    assert unauth_resp.status_code == 404

    # 5. Delete integration
    del_resp = await client.delete(f"/api/v1/integrations/{integration.id}", headers=headers)
    assert del_resp.status_code == 200
    assert "disconnected successfully" in del_resp.json()["message"]

    # Verify deleted
    get_after_del = await client.get(f"/api/v1/integrations/{integration.id}", headers=headers)
    assert get_after_del.status_code == 404


@pytest.mark.asyncio
async def test_crm_contacts_endpoints(
    client: AsyncClient,
    authenticated_user_and_integration: dict,
):
    """Test GET /api/v1/zoho/contacts and GET /api/v1/zoho/contacts/{id}."""
    headers = authenticated_user_and_integration["headers"]

    mock_contacts_data = {
        "data": [
            {
                "id": "c1001",
                "First_Name": "Jane",
                "Last_Name": "Doe",
                "Email": "jane@acme.com",
                "Phone": "+1234567890",
                "Account_Name": {"name": "Acme Inc", "id": "acc99"},
            }
        ],
        "info": {"page": 1, "per_page": 200, "count": 1, "more_records": False},
    }

    from app.integrations.zoho.client import ZohoClient

    with patch.object(
        ZohoClient,
        "_execute_request",
        new_callable=AsyncMock,
    ) as mock_exec:
        mock_exec.return_value = mock_contacts_data

        # List contacts
        list_resp = await client.get("/api/v1/zoho/contacts", headers=headers)
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert len(data["data"]) == 1
        contact = data["data"][0]
        assert contact["id"] == "c1001"
        assert contact["first_name"] == "Jane"
        assert contact["last_name"] == "Doe"
        assert contact["email"] == "jane@acme.com"
        assert contact["account_name"] == "Acme Inc"
        assert data["pagination"]["count"] == 1

        # Single contact
        mock_exec.return_value = {"data": [mock_contacts_data["data"][0]]}
        single_resp = await client.get("/api/v1/zoho/contacts/c1001", headers=headers)
        assert single_resp.status_code == 200
        assert single_resp.json()["id"] == "c1001"


@pytest.mark.asyncio
async def test_crm_leads_deals_accounts_endpoints(
    client: AsyncClient,
    authenticated_user_and_integration: dict,
):
    """Test leads, deals, and accounts retrieval endpoints."""
    headers = authenticated_user_and_integration["headers"]
    from app.integrations.zoho.client import ZohoClient

    with patch.object(
        ZohoClient,
        "_execute_request",
        new_callable=AsyncMock,
    ) as mock_exec:
        # Leads
        mock_exec.return_value = {
            "data": [{"id": "l201", "Last_Name": "Prospect", "Company": "Tech Co", "Email": "lead@tech.co"}],
            "info": {"count": 1},
        }
        leads_resp = await client.get("/api/v1/zoho/leads", headers=headers)
        assert leads_resp.status_code == 200
        assert leads_resp.json()["data"][0]["company"] == "Tech Co"

        # Deals
        mock_exec.return_value = {
            "data": [{"id": "d301", "Deal_Name": "Enterprise License", "Amount": "50000.0", "Stage": "Negotiation"}],
            "info": {"count": 1},
        }
        deals_resp = await client.get("/api/v1/zoho/deals", headers=headers)
        assert deals_resp.status_code == 200
        assert deals_resp.json()["data"][0]["amount"] == 50000.0

        # Accounts
        mock_exec.return_value = {
            "data": [{"id": "a401", "Account_Name": "Global Megacorp", "Industry": "Software"}],
            "info": {"count": 1},
        }
        accounts_resp = await client.get("/api/v1/zoho/accounts", headers=headers)
        assert accounts_resp.status_code == 200
        assert accounts_resp.json()["data"][0]["account_name"] == "Global Megacorp"
