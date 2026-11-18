from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse
from unittest.mock import AsyncMock, patch
import uuid

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import encrypt_token
from app.core.config import settings
from app.integrations.zoho.books_integration import ZohoBooksIntegration
from app.integrations.zoho.exceptions import ZohoOAuthError
from app.integrations.zoho.oauth import ZohoOAuthClient
from app.models.integration import Integration
from app.models.user import User


def test_books_authorization_url_is_product_aware_and_read_only():
    client = ZohoOAuthClient(
        client_id="books-client",
        client_secret="books-secret",
        redirect_uri="http://localhost/books/callback",
        scopes="ZohoBooks.settings.READ,ZohoBooks.contacts.READ",
        product="books",
    )
    result = client.generate_authorization_url(uuid.uuid4(), "Books", "in")
    query = parse_qs(urlparse(result["authorization_url"]).query)
    assert urlparse(result["authorization_url"]).netloc == "accounts.zoho.in"
    assert query["redirect_uri"] == ["http://localhost/books/callback"]
    assert query["scope"] == ["ZohoBooks.settings.READ,ZohoBooks.contacts.READ"]
    assert query["state"]
    assert client.validate_state(result["state"])["product"] == "books"


def test_crm_state_is_rejected_by_books_client():
    user_id = uuid.uuid4()
    crm = ZohoOAuthClient(client_id="crm", client_secret="secret", product="crm")
    books = ZohoOAuthClient(client_id="books", client_secret="secret", product="books")
    state = crm.generate_state(user_id, "CRM", "us")
    with pytest.raises(ZohoOAuthError, match="does not match"):
        books.validate_state(state)


@pytest.mark.asyncio
async def test_books_callback_exchanges_and_encrypts_tokens(db_session: AsyncSession):
    user = User(
        name="Books User",
        email=f"books_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="unused",
    )
    db_session.add(user)
    await db_session.flush()
    integration = ZohoBooksIntegration()
    state = integration.oauth_client.generate_state(user.id, "Books Connection", "in", "books")
    token_data = {
        "access_token": "books-access-token",
        "refresh_token": "books-refresh-token",
        "api_domain": "https://www.zohoapis.in",
        "expires_in": 3600,
    }
    with patch.object(integration.oauth_client, "exchange_code", new_callable=AsyncMock, return_value=token_data):
        created = await integration.handle_oauth_callback("one-time-code", state, db_session)

    assert created.provider == "zoho"
    assert created.product == "books"
    assert created.external_account_id is None
    assert created.access_token == "books-access-token"
    assert created.refresh_token == "books-refresh-token"

    raw = await db_session.execute(select(Integration).where(Integration.id == created.id))
    stored = raw.scalar_one()
    # SQLAlchemy returns decrypted values while the database column contains ciphertext.
    assert stored.access_token == "books-access-token"
    assert stored.refresh_token == "books-refresh-token"
    assert encrypt_token("books-access-token") != "books-access-token"


@pytest.mark.asyncio
async def test_books_token_exchange_failure_is_safely_reported():
    client = ZohoOAuthClient(
        client_id="books-client",
        client_secret="books-secret",
        redirect_uri="http://localhost/books/callback",
        product="books",
    )
    response = httpx.Response(
        400,
        json={"error": "invalid_code"},
        request=httpx.Request("POST", "https://accounts.zoho.in/oauth/v2/token"),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=response):
        with pytest.raises(ZohoOAuthError, match="authorization failed"):
            await client.exchange_code("expired-code", "https://accounts.zoho.in")


@pytest.mark.asyncio
async def test_books_callback_rejects_missing_refresh_token(db_session: AsyncSession):
    user = User(
        name="Books User 2",
        email=f"books_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="unused",
    )
    db_session.add(user)
    await db_session.flush()
    integration = ZohoBooksIntegration()
    state = integration.oauth_client.generate_state(user.id, "Books Connection", "us", "books")
    with patch.object(
        integration.oauth_client,
        "exchange_code",
        new_callable=AsyncMock,
        return_value={"access_token": "only-access", "expires_in": 3600},
    ):
        with pytest.raises(ZohoOAuthError, match="missing required credentials"):
            await integration.handle_oauth_callback("code", state, db_session)


@pytest.mark.asyncio
async def test_books_refresh_uses_books_credentials(db_session: AsyncSession):
    user = User(
        name="Books Refresh User",
        email=f"books_refresh_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="unused",
    )
    db_session.add(user)
    await db_session.flush()
    integration = Integration(
        user_id=user.id,
        provider="zoho",
        product="books",
        connection_name="Books",
        external_account_id=None,
        access_token="expired",
        refresh_token="books-refresh",
        token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        api_domain="https://www.zohoapis.in",
        status="active",
    )
    db_session.add(integration)
    await db_session.flush()
    from app.integrations.zoho.token_manager import ZohoTokenManager

    manager = ZohoTokenManager()
    response = httpx.Response(
        200,
        json={"access_token": "fresh-books", "expires_in": 3600},
        request=httpx.Request("POST", "https://accounts.zoho.in/oauth/v2/token"),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=response) as post:
        await manager.refresh_access_token(integration, db_session)
    assert post.call_args.kwargs["data"]["client_id"] == settings.ZOHO_BOOKS_CLIENT_ID
    assert post.call_args.kwargs["data"]["refresh_token"] == "books-refresh"
