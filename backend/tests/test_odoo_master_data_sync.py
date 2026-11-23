from unittest.mock import AsyncMock, patch
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.odoo.client import OdooClient
from app.integrations.odoo.integration import OdooIntegration, odoo_integration
from app.models.integration import Integration
from app.models.integration_record import IntegrationRecord
from app.models.user import User
from app.services.odoo_contacts_service import OdooContactsService
from app.services.sync_service import SyncService


def partner_payload(partner_id: int, *, customer_rank: int = 0, supplier_rank: int = 0, parent=None, active=True):
    return {
        "id": partner_id,
        "name": f"Partner {partner_id}",
        "display_name": f"Partner {partner_id}",
        "active": active,
        "is_company": parent is None,
        "parent_id": parent,
        "customer_rank": customer_rank,
        "supplier_rank": supplier_rank,
        "email": None,
    }


def test_normalize_partner_classifies_dual_role_and_relationship():
    normalized = OdooIntegration.normalize_partner({
        **partner_payload(10, customer_rank=2, supplier_rank=3, parent=[20, "Parent Co"]),
        "country_id": [91, "India"],
    })
    assert normalized["id"] == "10"
    assert normalized["classifications"] == ["customer", "vendor"]
    assert normalized["parent"] == {"id": 20, "name": "Parent Co"}
    assert normalized["country"] == {"id": 91, "name": "India"}
    assert normalized["email"] is None


@pytest.mark.asyncio
async def test_odoo_search_read_pagination_and_fields():
    client = OdooClient.__new__(OdooClient)
    client.search_read_partners = AsyncMock(return_value=[partner_payload(1)])
    integration = Integration(
        user_id=uuid.uuid4(), provider="odoo", product="erp", connection_name="Odoo",
        api_domain="https://odoo.example.com", access_token="encrypted-value", status="active",
    )
    with patch("app.integrations.odoo.integration.OdooClient", return_value=client):
        result = await odoo_integration.fetch_records(
            integration=integration, resource_type="contacts", page=3, per_page=50, session=None,
        )
    client.search_read_partners.assert_awaited_once()
    args, kwargs = client.search_read_partners.await_args
    assert args[1:3] == (100, 50)
    assert "customer_rank" in args[3]
    assert result["data"][0]["partner_id"] == "1"


@pytest.mark.asyncio
async def test_odoo_sync_is_idempotent_and_uses_shared_history(db_session: AsyncSession):
    user = User(name="Sync Owner", email=f"sync_{uuid.uuid4().hex}@example.com", hashed_password="hashed")
    db_session.add(user)
    await db_session.commit()
    integration = Integration(
        user_id=user.id, provider="odoo", product="erp", connection_name="Odoo",
        api_domain="https://odoo.example.com", access_token="api-key", status="active",
    )
    db_session.add(integration)
    await db_session.commit()
    pages = [
        {"data": [OdooIntegration.normalize_partner(partner_payload(1, customer_rank=1, supplier_rank=1)), OdooIntegration.normalize_partner(partner_payload(2, supplier_rank=1))], "info": {"more_records": True}},
        {"data": [OdooIntegration.normalize_partner(partner_payload(1, customer_rank=2, supplier_rank=1))], "info": {"more_records": False}},
    ]
    with patch.object(odoo_integration, "fetch_records", new_callable=AsyncMock, side_effect=pages):
        result = await SyncService(db_session).sync_resource(integration, "contacts", incremental=False, per_page=2)
    assert result.status == "completed"
    assert result.records_processed == 3
    assert result.records_inserted == 2
    assert result.records_updated == 1
    count = await db_session.scalar(select(func.count()).select_from(IntegrationRecord).where(IntegrationRecord.integration_id == integration.id))
    assert count == 2
    stored = await db_session.scalar(select(IntegrationRecord.raw_data).where(IntegrationRecord.external_record_id == "1"))
    assert stored["classifications"] == ["customer", "vendor"]


@pytest.mark.asyncio
async def test_odoo_local_reads_are_tenant_scoped(db_session: AsyncSession):
    owner = User(name="Owner", email=f"owner_{uuid.uuid4().hex}@example.com", hashed_password="hashed")
    other = User(name="Other", email=f"other_{uuid.uuid4().hex}@example.com", hashed_password="hashed")
    db_session.add_all([owner, other])
    await db_session.commit()
    owner_int = Integration(user_id=owner.id, provider="odoo", product="erp", connection_name="Owner", api_domain="https://odoo.example.com", status="active")
    other_int = Integration(user_id=other.id, provider="odoo", product="erp", connection_name="Other", api_domain="https://odoo.example.com", status="active")
    db_session.add_all([owner_int, other_int])
    await db_session.commit()
    for current_user, current_int, partner_id in ((owner, owner_int, 1), (other, other_int, 2)):
        db_session.add(IntegrationRecord(
            user_id=current_user.id, integration_id=current_int.id, provider="odoo", product="erp",
            external_organization_id="https://odoo.example.com", resource_type="contacts",
            external_record_id=str(partner_id), raw_data=OdooIntegration.normalize_partner(partner_payload(partner_id, customer_rank=1)),
        ))
    await db_session.commit()
    result = await OdooContactsService(db_session, owner_int).list_local()
    assert [item["partner_id"] for item in result["data"]] == ["1"]


@pytest.mark.asyncio
async def test_odoo_api_errors_are_not_silently_normalized():
    client = OdooClient.__new__(OdooClient)
    client.search_read_partners = AsyncMock(side_effect=RuntimeError("provider failure"))
    integration = Integration(user_id=uuid.uuid4(), provider="odoo", product="erp", connection_name="Odoo", api_domain="https://odoo.example.com", access_token="key", status="active")
    with patch("app.integrations.odoo.integration.OdooClient", return_value=client):
        with pytest.raises(RuntimeError, match="provider failure"):
            await odoo_integration.fetch_records(integration=integration, resource_type="contacts", page=1, per_page=25, session=None)
