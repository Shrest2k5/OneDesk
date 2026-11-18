from datetime import datetime, timedelta, timezone
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import Integration
from app.models.integration_record import IntegrationRecord
from app.models.user import User
from app.models.sync_history import SyncHistory
from app.repositories.integration_record_repository import IntegrationRecordRepository
from app.services.integration_service import IntegrationService
from app.services.sync_service import SyncService
from app.workers.sync_worker import RESOURCE_TYPES_BY_PRODUCT


async def _user(db_session: AsyncSession, prefix: str) -> User:
    user = User(
        name=prefix,
        email=f"{prefix.lower()}_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="not-used",
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _integration(db_session: AsyncSession, user: User, product: str = "crm") -> Integration:
    integration = Integration(
        user_id=user.id,
        provider="zoho",
        product=product,
        connection_name=f"Zoho {product}",
        external_account_id=f"org_{uuid.uuid4().hex[:8]}",
        access_token="access",
        refresh_token="refresh",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        status="active",
    )
    db_session.add(integration)
    await db_session.flush()
    return integration


@pytest.mark.asyncio
async def test_existing_integrations_default_to_crm_and_selection_is_product_aware(db_session: AsyncSession):
    user = await _user(db_session, "CRMUser")
    crm = await _integration(db_session, user)
    books = await _integration(db_session, user, "books")
    await db_session.commit()

    assert crm.product == "crm"
    service = IntegrationService(db_session)
    assert (await service.resolve_active_integration(user.id, crm.id, "zoho", "crm")).id == crm.id
    with pytest.raises(Exception):
        await service.resolve_active_integration(user.id, books.id, "zoho", "crm")


@pytest.mark.asyncio
async def test_record_upsert_updates_without_duplicates(db_session: AsyncSession):
    user = await _user(db_session, "RecordUser")
    integration = await _integration(db_session, user)
    repo = IntegrationRecordRepository(db_session)
    payload = {"id": "contact-1", "First_Name": "Jane", "Modified_Time": "2026-11-18T10:00:00Z"}

    assert await repo.upsert(user.id, integration.id, "zoho", "crm", integration.external_account_id, "contacts", payload) == "inserted"
    payload["First_Name"] = "Janet"
    assert await repo.upsert(user.id, integration.id, "zoho", "crm", integration.external_account_id, "contacts", payload) == "updated"
    await db_session.commit()

    rows = (await db_session.execute(select(IntegrationRecord))).scalars().all()
    assert len(rows) == 1
    assert rows[0].raw_data["First_Name"] == "Janet"


@pytest.mark.asyncio
async def test_record_queries_are_tenant_scoped(db_session: AsyncSession):
    owner = await _user(db_session, "Owner")
    other = await _user(db_session, "Other")
    integration = await _integration(db_session, owner)
    repo = IntegrationRecordRepository(db_session)
    await repo.upsert(owner.id, integration.id, "zoho", "crm", integration.external_account_id, "contacts", {"id": "c1"})
    await db_session.commit()

    assert len(await repo.list_for_user(owner.id, integration.id)) == 1
    assert len(await repo.list_for_user(other.id, integration.id)) == 0


@pytest.mark.asyncio
async def test_successful_timestamp_is_not_set_for_failed_sync(db_session: AsyncSession):
    user = await _user(db_session, "SyncUser")
    integration = await _integration(db_session, user)
    service = SyncService(db_session)
    job = await service.start_sync_record(integration.id, "contacts")
    await service.fail_sync_record(job.id, "provider unavailable", records_processed=2, records_failed=2)

    failed = (await db_session.execute(select(SyncHistory).where(SyncHistory.id == job.id))).scalar_one()
    assert failed.status == "failed"
    assert failed.successful_at is None
    assert failed.records_failed == 2

    completed_job = await service.start_sync_record(integration.id, "contacts")
    completed = await service.complete_sync_record(completed_job.id, 1, records_inserted=1)
    assert completed.successful_at is not None
    assert completed.records_inserted == 1


def test_celery_resource_mappings_are_product_specific():
    assert RESOURCE_TYPES_BY_PRODUCT["crm"] == ("contacts", "leads", "deals", "accounts")
    assert "invoices" in RESOURCE_TYPES_BY_PRODUCT["books"]
