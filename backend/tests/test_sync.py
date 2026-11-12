from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.zoho.client import ZohoClient
from app.integrations.zoho.exceptions import ZohoAPIError
from app.models.integration import Integration
from app.models.user import User


@pytest.fixture
async def sync_setup(client: AsyncClient, db_session: AsyncSession):
    """Fixture providing user and active integration for sync testing."""
    email = f"sync_user_{uuid.uuid4().hex[:6]}@example.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"name": "Sync Master", "email": email, "password": "Password123!"},
    )
    user_id = uuid.UUID(reg.json()["id"])

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    integration = Integration(
        user_id=user_id,
        provider="zoho",
        connection_name="Sync Zoho Account",
        external_account_id=f"org_{uuid.uuid4().hex[:6]}",
        access_token="1000.sync_access_token",
        refresh_token="1000.sync_refresh_token",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        api_domain="https://www.zohoapis.com",
        status="active",
    )
    db_session.add(integration)
    await db_session.commit()
    await db_session.refresh(integration)

    return {
        "user_id": user_id,
        "headers": headers,
        "integration": integration,
    }


@pytest.mark.asyncio
async def test_on_demand_sync_success(client: AsyncClient, sync_setup: dict):
    """Test on-demand synchronization execution and history recording."""
    headers = sync_setup["headers"]
    integration = sync_setup["integration"]

    mock_page1 = {
        "data": [{"id": "1", "Last_Name": "Lead 1"}, {"id": "2", "Last_Name": "Lead 2"}],
        "info": {"more_records": False, "count": 2},
    }

    with patch.object(ZohoClient, "_execute_request", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = mock_page1

        sync_resp = await client.post(
            f"/api/v1/integrations/{integration.id}/sync",
            json={"resource_type": "leads", "incremental": False},
            headers=headers,
        )
        assert sync_resp.status_code == 200
        data = sync_resp.json()
        assert data["status"] == "completed"
        assert data["resource_type"] == "leads"
        assert data["records_processed"] == 2
        assert data["completed_at"] is not None

        # Fetch sync history
        history_resp = await client.get(
            f"/api/v1/integrations/{integration.id}/sync-history",
            headers=headers,
        )
        assert history_resp.status_code == 200
        history_items = history_resp.json()
        assert len(history_items) >= 1
        assert history_items[0]["status"] == "completed"
        assert history_items[0]["records_processed"] == 2


@pytest.mark.asyncio
async def test_sync_failure_audit_recording(client: AsyncClient, sync_setup: dict):
    """Test that a sync failure records 'failed' status and error details."""
    headers = sync_setup["headers"]
    integration = sync_setup["integration"]

    with patch.object(
        ZohoClient,
        "_execute_request",
        new_callable=AsyncMock,
        side_effect=ZohoAPIError("Zoho CRM quota exhausted", status_code=429),
    ):
        sync_resp = await client.post(
            f"/api/v1/integrations/{integration.id}/sync",
            json={"resource_type": "contacts"},
            headers=headers,
        )
        assert sync_resp.status_code >= 400

        # Verify failure history recorded in database
        history_resp = await client.get(
            f"/api/v1/integrations/{integration.id}/sync-history",
            headers=headers,
        )
        assert history_resp.status_code == 200
        history_items = history_resp.json()
        assert len(history_items) >= 1
        failed_job = history_items[0]
        assert failed_job["status"] == "failed"
        assert "quota exhausted" in failed_job["error_message"]


@pytest.mark.asyncio
async def test_sync_cross_tenant_isolation(client: AsyncClient, sync_setup: dict):
    """Test that another tenant cannot trigger sync or access sync history."""
    integration = sync_setup["integration"]

    # Register unauthorized user
    reg2 = await client.post(
        "/api/v1/auth/register",
        json={"name": "Attacker 2", "email": f"att_{uuid.uuid4().hex[:4]}@corp.com", "password": "Password123!"},
    )
    login2 = await client.post(
        "/api/v1/auth/login",
        json={"email": reg2.json()["email"], "password": "Password123!"},
    )
    unauthorized_headers = {"Authorization": f"Bearer {login2.json()['access_token']}"}

    # Cannot trigger sync
    resp1 = await client.post(
        f"/api/v1/integrations/{integration.id}/sync",
        json={"resource_type": "contacts"},
        headers=unauthorized_headers,
    )
    assert resp1.status_code == 404

    # Cannot view sync history
    resp2 = await client.get(
        f"/api/v1/integrations/{integration.id}/sync-history",
        headers=unauthorized_headers,
    )
    assert resp2.status_code == 404
