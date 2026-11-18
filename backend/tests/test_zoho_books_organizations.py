from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import uuid

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.zoho.books_client import ZohoBooksClient
from app.integrations.zoho.exceptions import ZohoAPIError
from app.models.books_organization import BooksOrganization
from app.models.integration import Integration
from app.models.user import User
from app.repositories.books_organization_repository import BooksOrganizationRepository


class FakeTokenManager:
    async def get_valid_access_token(self, integration, session):
        return "books-test-token"


async def make_user(db_session: AsyncSession, label: str) -> User:
    user = User(
        name=label,
        email=f"{label.lower()}_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="unused",
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def make_books_integration(db_session: AsyncSession, user: User) -> Integration:
    integration = Integration(
        user_id=user.id,
        provider="zoho",
        product="books",
        connection_name="Books",
        access_token="access",
        refresh_token="refresh",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        api_domain="https://www.zohoapis.in",
        status="active",
    )
    db_session.add(integration)
    await db_session.flush()
    return integration


@pytest.mark.asyncio
async def test_books_client_parses_organizations_and_uses_dynamic_domain(db_session: AsyncSession):
    integration = Integration(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        provider="zoho",
        product="books",
        connection_name="Books",
        api_domain="https://www.zohoapis.eu",
        access_token="access",
        refresh_token="refresh",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        status="active",
    )
    client = ZohoBooksClient(integration, db_session, token_manager=FakeTokenManager())
    response = httpx.Response(
        200,
        json={"code": 0, "message": "success", "organizations": [{"organization_id": "org-1", "name": "EU Org"}]},
        request=httpx.Request("GET", "https://www.zohoapis.eu/books/v3/organizations"),
    )
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=response) as request:
        organizations = await client.list_organizations()

    assert organizations[0]["organization_id"] == "org-1"
    assert request.call_args.kwargs["url"] == "https://www.zohoapis.eu/books/v3/organizations"
    assert request.call_args.kwargs["headers"]["Authorization"] == "Zoho-oauthtoken books-test-token"


@pytest.mark.asyncio
async def test_books_client_handles_empty_and_api_errors(db_session: AsyncSession):
    integration = Integration(
        id=uuid.uuid4(), user_id=uuid.uuid4(), provider="zoho", product="books",
        connection_name="Books", api_domain="https://www.zohoapis.in", access_token="access",
        refresh_token="refresh", token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1), status="active",
    )
    client = ZohoBooksClient(integration, db_session, token_manager=FakeTokenManager())
    with patch.object(client, "_execute_request", new_callable=AsyncMock, return_value={"code": 0, "organizations": []}):
        assert await client.list_organizations() == []
    with patch.object(client, "_execute_request", new_callable=AsyncMock, return_value={"code": 0, "organizations": {}}):
        with pytest.raises(ZohoAPIError, match="invalid structure"):
            await client.list_organizations()


@pytest.mark.asyncio
async def test_organization_upsert_prevents_duplicates_and_updates_metadata(db_session: AsyncSession):
    user = await make_user(db_session, "OrgOwner")
    integration = await make_books_integration(db_session, user)
    repo = BooksOrganizationRepository(db_session)
    payload = {"organization_id": "org-1", "name": "Original", "currency_code": "INR"}
    await repo.upsert_many(user.id, integration.id, [payload])
    payload["name"] = "Updated"
    await repo.upsert_many(user.id, integration.id, [payload])
    await db_session.commit()

    rows = (await db_session.execute(select(BooksOrganization))).scalars().all()
    assert len(rows) == 1
    assert rows[0].name == "Updated"


@pytest.mark.asyncio
async def test_organization_endpoints_validate_tenant_and_integration_ownership(client, db_session: AsyncSession):
    owner = await make_user(db_session, "EndpointOwner")
    other = await make_user(db_session, "EndpointOther")
    owner_integration = await make_books_integration(db_session, owner)
    other_integration = await make_books_integration(db_session, owner)
    repo = BooksOrganizationRepository(db_session)
    await repo.upsert_many(owner.id, owner_integration.id, [{"organization_id": "org-owner", "name": "Owner Org"}])
    await repo.upsert_many(owner.id, other_integration.id, [{"organization_id": "org-other", "name": "Other Org"}])
    await db_session.commit()

    async def auth(user: User) -> dict:
        response = await client.post("/api/v1/auth/login", json={"email": user.email, "password": "unused"})
        # Login cannot use the fixture password; create via the normal API instead.
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    # Use direct JWT creation for the two pre-created users.
    from app.core.security import create_access_token
    owner_headers = {"Authorization": f"Bearer {create_access_token(owner.id)}"}
    other_headers = {"Authorization": f"Bearer {create_access_token(other.id)}"}

    listed = await client.get(f"/api/v1/integrations/zoho/books/{owner_integration.id}/organizations", headers=owner_headers)
    assert listed.status_code == 200
    assert listed.json()[0]["external_organization_id"] == "org-owner"

    selected = await client.put(
        f"/api/v1/integrations/zoho/books/{owner_integration.id}/organizations/org-owner/select",
        headers=owner_headers,
    )
    assert selected.status_code == 200
    assert selected.json()["selected"] is True

    current = await client.get(f"/api/v1/integrations/zoho/books/{owner_integration.id}/organizations/selected", headers=owner_headers)
    assert current.status_code == 200
    assert current.json()["external_organization_id"] == "org-owner"

    cross_integration = await client.put(
        f"/api/v1/integrations/zoho/books/{other_integration.id}/organizations/org-owner/select",
        headers=owner_headers,
    )
    assert cross_integration.status_code == 404

    cross_tenant = await client.get(
        f"/api/v1/integrations/zoho/books/{owner_integration.id}/organizations",
        headers=other_headers,
    )
    assert cross_tenant.status_code == 404
