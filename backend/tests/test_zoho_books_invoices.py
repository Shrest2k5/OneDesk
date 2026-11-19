from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.zoho.books_client import ZohoBooksClient
from app.models.integration import Integration
from app.models.integration_record import IntegrationRecord
from app.models.sync_history import SyncHistory
from app.models.user import User
from app.repositories.integration_record_repository import IntegrationRecordRepository
from app.services.books_invoices_service import BooksInvoicesService


async def setup_books(db_session: AsyncSession):
    user = User(name="Invoice User", email=f"invoice_{uuid.uuid4().hex[:8]}@example.com", hashed_password="unused")
    db_session.add(user)
    await db_session.flush()
    integration = Integration(
        user_id=user.id, provider="zoho", product="books", connection_name="Books",
        selected_organization_id="org-1", api_domain="https://www.zohoapis.eu",
        access_token="access", refresh_token="refresh",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1), status="active",
    )
    db_session.add(integration)
    await db_session.flush()
    return user, integration


def invoice(invoice_id: str, **overrides):
    value = {
        "invoice_id": invoice_id, "invoice_number": f"INV-{invoice_id}",
        "customer_id": "customer-1", "customer_name": "Acme", "status": "paid",
        "date": "2026-11-01", "due_date": "2026-11-30", "currency_code": "USD",
        "total": "100.10", "balance": "0.10", "line_items": [{"item_id": "item-1", "rate": "100.10"}],
    }
    value.update(overrides)
    return value


def test_invoice_normalization_preserves_fields_and_avoids_float_math():
    normalized = BooksInvoicesService.normalize(invoice("1", status="partially_paid"))
    assert normalized["id"] == "1"
    assert normalized["line_items"][0]["item_id"] == "item-1"
    assert Decimal(str(normalized["amount_paid"])) == Decimal("100.00")


@pytest.mark.asyncio
async def test_invoice_client_sends_organization_and_handles_list_page_context(db_session):
    _, integration = await setup_books(db_session)
    tokens = type("Tokens", (), {"get_valid_access_token": AsyncMock(return_value="token")})()
    client = ZohoBooksClient(integration, db_session, token_manager=tokens)
    response = httpx.Response(200, json={"code": 0, "invoices": [invoice("1")], "page_context": [{"page": 1, "has_more_page": True}]}, request=httpx.Request("GET", "https://www.zohoapis.eu/books/v3/invoices"))
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=response) as request:
        result = await client.list_invoices_page("org-1")
    assert result["invoices"][0]["invoice_id"] == "1"
    assert request.call_args.kwargs["params"]["organization_id"] == "org-1"


@pytest.mark.asyncio
async def test_invoice_stats_and_upsert_are_decimal_and_org_scoped(db_session):
    user, integration = await setup_books(db_session)
    repo = IntegrationRecordRepository(db_session)
    await repo.upsert(user.id, integration.id, "zoho", "books", "org-1", "invoices", invoice("1"))
    await repo.upsert(user.id, integration.id, "zoho", "books", "org-1", "invoices", invoice("2", status="overdue", total="0.20", balance="0.20"))
    service = BooksInvoicesService(db_session, integration)
    stats = await service.stats()
    assert stats["total"] == 2
    assert stats["overdue"] == 1
    assert stats["total_amount"] == "100.30"
    assert stats["total_outstanding"] == "0.30"
    with pytest.raises(ValueError, match="selected Books organization"):
        await repo.upsert(user.id, integration.id, "zoho", "books", "org-2", "invoices", invoice("3"))


@pytest.mark.asyncio
async def test_invoice_partial_page_failure_preserves_previous_page_and_fails_sync(db_session):
    _, integration = await setup_books(db_session)
    pages = AsyncMock(side_effect=[{"invoices": [invoice("1")], "page_context": {"has_more_page": True}}, RuntimeError("page unavailable")])
    with patch.object(ZohoBooksClient, "list_invoices_page", pages):
        job = await BooksInvoicesService(db_session, integration).synchronize()
    assert job.status == "failed"
    assert job.successful_at is None
    records = (await db_session.execute(select(IntegrationRecord))).scalars().all()
    assert len(records) == 1
    assert records[0].external_record_id == "1"
    history = (await db_session.execute(select(SyncHistory).where(SyncHistory.id == job.id))).scalar_one()
    assert history.status == "failed"
