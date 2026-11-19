from datetime import datetime, timedelta, timezone
import uuid

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch

from app.integrations.zoho.books_client import ZohoBooksClient
from app.models.integration import Integration
from app.models.integration_record import IntegrationRecord
from app.models.user import User
from app.repositories.integration_record_repository import IntegrationRecordRepository
from app.services.books_contacts_service import BooksContactsService


async def books_setup(db_session: AsyncSession):
    user = User(name="Books User", email=f"books_{uuid.uuid4().hex[:8]}@example.com", hashed_password="unused")
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


def test_books_contact_classification_preserves_customer_and_vendor_types():
    normalized = BooksContactsService.normalize({
        "contact_id": 42, "contact_name": "Both Co", "contact_type": "customer,vendor",
        "email": "both@example.com",
    })
    assert normalized["id"] == "42"
    assert normalized["contact_types"] == ["customer", "vendor"]
    assert normalized["raw_data"]["contact_id"] == 42


@pytest.mark.asyncio
async def test_books_client_sends_selected_organization_and_parses_page_context(db_session):
    _, integration = await books_setup(db_session)
    client = ZohoBooksClient(integration, db_session, token_manager=type("Tokens", (), {
        "get_valid_access_token": AsyncMock(return_value="token")
    })())
    response = httpx.Response(200, json={"code": 0, "contacts": [{"contact_id": "c1", "contact_type": "vendor"}], "page_context": {"page": 1, "has_more_page": True}}, request=httpx.Request("GET", "https://www.zohoapis.eu/books/v3/contacts"))
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=response) as request:
        page = await client.list_contacts_page("org-1", 1, 200)
    assert page["contacts"][0]["contact_id"] == "c1"
    assert request.call_args.kwargs["params"]["organization_id"] == "org-1"


@pytest.mark.asyncio
async def test_books_record_upsert_rejects_wrong_selected_organization(db_session):
    user, integration = await books_setup(db_session)
    repo = IntegrationRecordRepository(db_session)
    with pytest.raises(ValueError, match="selected Books organization"):
        await repo.upsert(user.id, integration.id, "zoho", "books", "org-2", "contacts", {"contact_id": "c1"})

    await repo.upsert(user.id, integration.id, "zoho", "books", "org-1", "contacts", {"contact_id": "c1", "contact_name": "Old"})
    await repo.upsert(user.id, integration.id, "zoho", "books", "org-1", "contacts", {"contact_id": "c1", "contact_name": "New"})
    rows = (await db_session.execute(select(IntegrationRecord))).scalars().all()
    assert len(rows) == 1
    assert rows[0].raw_data["contact_name"] == "New"
