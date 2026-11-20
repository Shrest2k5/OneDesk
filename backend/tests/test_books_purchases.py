from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy import select

from app.integrations.zoho.books_client import ZohoBooksClient
from app.models.integration import Integration
from app.models.integration_record import IntegrationRecord
from app.models.user import User
from app.services.books_purchases_service import BooksPurchasesService
from app.workers.sync_worker import sync_books_purchases_task


async def setup_books(db_session):
    user = User(name="Purchase User", email=f"purchase_{uuid.uuid4().hex[:8]}@example.com", hashed_password="unused")
    db_session.add(user); await db_session.flush()
    integration = Integration(user_id=user.id, provider="zoho", product="books", connection_name="Books",
        selected_organization_id="org-1", api_domain="https://www.zohoapis.eu", access_token="access",
        refresh_token="refresh", token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1), status="active")
    db_session.add(integration); await db_session.flush()
    return user, integration


def bill(bill_id="bill-1", date="2026-11-01"):
    return {"bill_id": bill_id, "bill_number": "B-1", "vendor_id": "v-1", "vendor_name": "Vendor",
            "date": date, "due_date": "2026-11-30", "status": "open", "currency_code": "USD",
            "sub_total": 10, "tax_total": 2, "total": 12, "balance": 12,
            "line_items": [{"item_id": "i-1", "rate": 10}], "payments": [{"payment_id": "p-1", "bill_id": bill_id}]}


def test_purchase_normalization_uses_decimal_values_and_relationships():
    row = BooksPurchasesService.normalize(bill(), "bills")
    assert row["id"] == "bill-1"
    assert Decimal(str(row["total"])) == Decimal("12")
    assert row["payments"][0]["bill_id"] == "bill-1"


@pytest.mark.asyncio
async def test_client_retrieves_bills_with_org_pagination_and_dates(db_session):
    _, integration = await setup_books(db_session)
    client = ZohoBooksClient(integration, db_session, token_manager=type("Tokens", (), {"get_valid_access_token": AsyncMock(return_value="token")})())
    response = httpx.Response(200, json={"code": 0, "bills": [bill()], "page_context": {"has_more_page": True}}, request=httpx.Request("GET", "https://www.zohoapis.eu/books/v3/bills"))
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=response) as request:
        result = await client.list_bills_page("org-1", 2, 200, "2026-11-01", "2026-11-30")
    assert result["items"][0]["bill_id"] == "bill-1"
    assert request.call_args.kwargs["params"] == {"organization_id": "org-1", "page": 2, "per_page": 200, "date_start": "2026-11-01", "date_end": "2026-11-30"}


@pytest.mark.asyncio
async def test_purchase_sync_upserts_pages_and_filters_dates(db_session):
    user, integration = await setup_books(db_session)
    pages = AsyncMock(side_effect=[{"items": [bill()], "page_context": {"has_more_page": True}}, {"items": [], "page_context": {"has_more_page": False}}, {"items": [{"vendor_credit_id": "vc-1", "vendor_credit_number": "VC-1", "date": "2026-10-01", "vendor_name": "Vendor", "bills_credited": [{"bill_id": "bill-1"}], "total": 3, "balance": 3}], "page_context": {"has_more_page": False}}])
    with patch.object(ZohoBooksClient, "list_bills_page", pages), patch.object(ZohoBooksClient, "list_vendor_credits_page", pages):
        job = await BooksPurchasesService(db_session, integration).synchronize("2026-11-01", "2026-11-30")
    rows = (await db_session.execute(select(IntegrationRecord).where(IntegrationRecord.integration_id == integration.id))).scalars().all()
    assert job.status == "completed" and len(rows) == 1 and rows[0].external_organization_id == "org-1"


def test_purchases_celery_task_is_registered():
    assert sync_books_purchases_task.name == "app.workers.sync_worker.sync_books_purchases_task"
