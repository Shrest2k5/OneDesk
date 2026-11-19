from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.zoho.books_client import ZohoBooksClient
from app.integrations.zoho.books_integration import ZohoBooksIntegration
from app.models.integration import Integration
from app.models.integration_record import IntegrationRecord
from app.models.user import User
from app.repositories.integration_record_repository import IntegrationRecordRepository
from app.services.books_transactions_service import BooksTransactionsService
from app.workers.sync_worker import sync_books_transactions_task


async def setup_books(db_session: AsyncSession):
    user = User(name="Transactions User", email=f"transactions_{uuid.uuid4().hex[:8]}@example.com", hashed_password="unused")
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


PAYLOADS = {
    "customer_payments": {"payment_id": "cp-1", "date": "2026-10-01", "amount": "10.10", "currency_code": "USD", "customer_name": "Customer"},
    "vendor_payments": {"payment_id": "vp-1", "date": "2026-10-02", "amount": "20.20", "currency_code": "EUR", "vendor_name": "Vendor"},
    "sales_receipts": {"sales_receipt_id": "sr-1", "date": "2026-10-03", "total": "30.30", "currency_code": "USD"},
    "credit_note_refunds": {"creditnote_refund_id": "cnr-1", "date": "2026-10-04", "amount_fcy": "4.00", "currency_code": "USD"},
    "customer_payment_refunds": {"payment_refund_id": "cpr-1", "date": "2026-10-05", "amount": "5.00", "currency_code": "USD"},
    "vendor_payment_refunds": {"vendorpayment_refund_id": "vpr-1", "date": "2026-10-06", "amount_fcy": "6.00", "currency_code": "EUR"},
    "bank_transactions": {"transaction_id": "bt-1", "date": "2026-10-07", "amount": "7.00", "currency_code": "USD", "transaction_type": "deposit"},
}


def test_normalization_supports_all_transaction_categories_and_decimal_inputs():
    for kind, payload in PAYLOADS.items():
        result = BooksTransactionsService.normalize(payload, kind)
        assert result["id"]
        assert result["transaction_type"] == kind
        assert result["raw_data"] == payload
    assert BooksTransactionsService._decimal("10.10") == Decimal("10.10")


def test_normalization_preserves_refund_source_and_financial_metadata():
    result = BooksTransactionsService.normalize(
        {
            "payment_refund_id": "refund-1", "payment_id": "payment-1", "date": "2026-10-05",
            "amount_fcy": "5.25", "currency_id": "cur-1", "currency_code": "USD",
            "exchange_rate": "1.2", "from_account_id": "acct-1", "description": "Refund",
        },
        "customer_payment_refunds",
    )
    assert result["amount"] == "5.25"
    assert result["currency_id"] == "cur-1"
    assert result["refund_source_id"] == "payment-1"
    assert result["refund_source_type"] == "customer_payment"


def test_date_range_is_inclusive_and_invalid_ranges_are_rejected():
    assert BooksTransactionsService._in_range("2026-10-01", "2026-10-01", "2026-10-01")
    assert not BooksTransactionsService._in_range("2026-10-02", "2026-10-01", "2026-10-01")
    with pytest.raises(Exception):
        BooksTransactionsService._validate_range("2026-11-02", "2026-11-01")


def test_books_financial_celery_task_is_registered():
    assert sync_books_transactions_task.name == "app.workers.sync_worker.sync_books_transactions_task"


@pytest.mark.asyncio
async def test_shared_books_adapter_maps_contacts_and_pagination(db_session):
    _, integration = await setup_books(db_session)
    response = {"contacts": [{"contact_id": "c-1"}], "page_context": {"has_more_page": True}}
    with patch("app.integrations.zoho.books_client.ZohoBooksClient") as client_type:
        client_type.return_value.list_contacts_page = AsyncMock(return_value=response)
        result = await ZohoBooksIntegration().fetch_records(
            integration=integration, resource_type="contacts", page=2, per_page=200, session=db_session
        )
    assert result == {"data": response["contacts"], "info": {"more_records": True}}
    client_type.return_value.list_contacts_page.assert_awaited_once_with("org-1", 2, 200)


@pytest.mark.asyncio
async def test_financial_client_passes_org_dates_and_pagination_context(db_session):
    _, integration = await setup_books(db_session)
    client = ZohoBooksClient(integration, db_session, token_manager=type("Tokens", (), {"get_valid_access_token": AsyncMock(return_value="token")})())
    response = httpx.Response(200, json={"code": 0, "customer_payments": [{"payment_id": "cp-1"}], "page_context": {"page": 2, "has_more_page": True}}, request=httpx.Request("GET", "https://www.zohoapis.eu/books/v3/customerpayments"))
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=response) as request:
        result = await client.list_financial_page("org-1", "customerpayments", "customer_payments", 2, 200, "2026-10-01", "2026-10-31")
    assert result["items"][0]["payment_id"] == "cp-1"
    assert result["page_context"]["has_more_page"] is True
    assert request.call_args.kwargs["params"] == {"organization_id": "org-1", "page": 2, "per_page": 200, "date_start": "2026-10-01", "date_end": "2026-10-31"}


@pytest.mark.asyncio
async def test_stats_are_scoped_and_currency_separated(db_session):
    user, integration = await setup_books(db_session)
    repo = IntegrationRecordRepository(db_session)
    await repo.upsert(user.id, integration.id, "zoho", "books", "org-1", "customer_payments", {"payment_id": "1", "date": "2026-10-01", "amount": "10.10", "currency_code": "USD"})
    await repo.upsert(user.id, integration.id, "zoho", "books", "org-1", "customer_payments", {"payment_id": "2", "date": "2026-10-01", "amount": "20.20", "currency_code": "EUR"})
    service = BooksTransactionsService(db_session, integration)
    stats = await service.stats("2026-10-01", "2026-10-01")
    assert stats["counts"]["customer_payments"] == 2
    assert stats["amounts"]["customer_payments:USD"] == "10.10"
    assert stats["amounts"]["customer_payments:EUR"] == "20.20"


@pytest.mark.asyncio
async def test_upsert_is_duplicate_safe_and_organization_scoped(db_session):
    user, integration = await setup_books(db_session)
    repo = IntegrationRecordRepository(db_session)
    payload = PAYLOADS["bank_transactions"]
    await repo.upsert(user.id, integration.id, "zoho", "books", "org-1", "bank_transactions", payload)
    await repo.upsert(user.id, integration.id, "zoho", "books", "org-1", "bank_transactions", {**payload, "amount": "8.00"})
    rows = (await db_session.execute(select(IntegrationRecord))).scalars().all()
    assert len(rows) == 1
    assert rows[0].raw_data["amount"] == "8.00"
    with pytest.raises(ValueError, match="selected Books organization"):
        await repo.upsert(user.id, integration.id, "zoho", "books", "org-2", "bank_transactions", payload)
