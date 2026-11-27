from unittest.mock import AsyncMock, patch
import uuid

import pytest

from app.integrations.registry import IntegrationRegistry, integration_registry
from app.models.integration import Integration
from app.models.user import User
from app.services.sync_service import SyncService
from app.workers.sync_worker import sync_resource_task


def test_worker_registry_resolves_odoo_without_api_router_import():
    registry = IntegrationRegistry()
    provider = registry.get("odoo", "erp")

    assert provider is not None
    assert provider.provider_name == "odoo"
    assert provider.product_name == "erp"


@pytest.mark.parametrize(("provider_name", "product"), [("zoho", "crm"), ("zoho", "books")])
def test_worker_registry_preserves_zoho_provider_resolution(provider_name, product):
    provider = IntegrationRegistry().get(provider_name, product)

    assert provider is not None
    assert provider.provider_name == provider_name
    assert provider.product_name == product


def test_worker_registry_resolves_business_central():
    provider = IntegrationRegistry().get("business_central", "erp")
    assert provider is not None
    assert provider.provider_name == "business_central"
    assert provider.product_name == "erp"


def test_unknown_provider_remains_unsupported():
    assert IntegrationRegistry().get("not-a-provider", "erp") is None


@pytest.mark.parametrize("resource_type", [
    "contacts", "invoices", "bills", "credit_notes", "payments", "transactions",
])
@pytest.mark.asyncio
async def test_shared_sync_service_resolves_every_odoo_resource(db_session, resource_type):
    user = User(name="Worker Owner", email=f"worker_{uuid.uuid4().hex}@example.com", hashed_password="hashed")
    db_session.add(user)
    await db_session.commit()
    integration = Integration(
        user_id=user.id, provider="odoo", product="erp",
        connection_name="Worker Odoo", api_domain="https://odoo.example.com",
        access_token="api-key", status="active",
    )
    with patch.object(integration_registry, "get", wraps=integration_registry.get) as resolve, \
         patch("app.integrations.odoo.integration.OdooIntegration.fetch_records", new_callable=AsyncMock,
               return_value={"data": [], "info": {"more_records": False}}):
        db_session.add(integration)
        await db_session.commit()
        result = await SyncService(db_session).sync_resource(integration, resource_type, incremental=False)

    assert result.status == "completed"
    resolve.assert_called_with("odoo", "erp")


def test_celery_task_is_registered_for_worker_dispatch():
    assert sync_resource_task.name == "app.workers.sync_worker.sync_resource_task"


def test_celery_sync_task_dispatches_odoo_resource():
    expected = {"status": "completed", "resource_type": "invoices"}
    with patch("app.workers.sync_worker._create_sync_record", new_callable=AsyncMock, return_value="sync-id"), \
         patch("app.workers.sync_worker._run_async_sync", new_callable=AsyncMock, return_value=expected) as run_sync:
        result = sync_resource_task.apply(
            args=[str(uuid.uuid4()), "invoices", False], throw=True,
        ).get()

    assert result == expected
    run_sync.assert_awaited_once()
