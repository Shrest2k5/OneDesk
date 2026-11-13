from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import uuid
from cryptography.fernet import Fernet
import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import cast, select, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    decrypt_token,
    encrypt_token,
    get_fernet,
    mask_secret,
    sanitize_data,
    validate_encryption_key,
)
from app.integrations.zoho.client import ZohoClient
from app.integrations.zoho.exceptions import ZohoAPIError, ZohoOAuthError, ZohoTokenExpiredError
from app.integrations.zoho.oauth import ZohoOAuthClient
from app.integrations.zoho.token_manager import ZohoTokenManager
from app.models.integration import Integration
from app.models.user import User


# ==============================================================================
# 1. ENCRYPTION SECURITY TESTS
# ==============================================================================

def test_fernet_encryption_and_decryption_lifecycle():
    """Verify symmetric encryption, decryption, and ciphertext properties."""
    plain_token = "1000.sample_zoho_oauth_access_token_abc12345"
    ciphertext = encrypt_token(plain_token)

    assert ciphertext != plain_token
    assert ciphertext is not None
    assert ciphertext.startswith("gAAAAA")

    decrypted = decrypt_token(ciphertext)
    assert decrypted == plain_token


def test_encryption_handles_empty_and_none():
    """Verify empty or None inputs fail safely and return None."""
    assert encrypt_token(None) is None
    assert encrypt_token("") is None
    assert decrypt_token(None) is None
    assert decrypt_token("") is None


def test_invalid_ciphertext_rejected():
    """Verify corrupt ciphertext raises ValueError and never returns plaintext."""
    with pytest.raises(ValueError) as exc:
        decrypt_token("gAAAAABcorruptciphertextnotvalidbase64")
    assert "Decryption failed" in str(exc.value)


def test_wrong_key_fails_safely():
    """Verify decrypting with a mismatched Fernet key raises clear error."""
    plain_token = "secret_zoho_token"
    # Encrypt with valid current key
    ciphertext = encrypt_token(plain_token)

    # Attempt decrypt with different valid key
    other_key = Fernet.generate_key()
    other_fernet = Fernet(other_key)
    with pytest.raises(Exception):
        other_fernet.decrypt(ciphertext.encode("utf-8"))


def test_placeholder_key_rejected():
    """Verify validate_encryption_key rejects placeholder keys."""
    with patch.object(settings, "ENCRYPTION_KEY", "replace-with-valid-fernet-key-32-urlsafe-base64-bytes"):
        with pytest.raises(ValueError) as exc:
            validate_encryption_key()
        assert "placeholder" in str(exc.value).lower()

    with patch.object(settings, "ENCRYPTION_KEY", ""):
        with pytest.raises(ValueError):
            validate_encryption_key()


def test_sanitize_data_scrubs_all_credentials():
    """Verify sanitize_data redacts tokens, secrets, codes, and passwords."""
    sensitive_dict = {
        "access_token": "secret_access",
        "refresh_token": "secret_refresh",
        "client_secret": "super_secret",
        "code": "auth_code_xyz",
        "Authorization": "Bearer secret_jwt",
        "nested": {
            "password": "my_password",
            "safe_key": "safe_value",
        },
        "safe_field": 12345,
    }

    clean = sanitize_data(sensitive_dict)
    assert clean["access_token"] == "[REDACTED]"
    assert clean["refresh_token"] == "[REDACTED]"
    assert clean["client_secret"] == "[REDACTED]"
    assert clean["code"] == "[REDACTED]"
    assert clean["Authorization"] == "[REDACTED]"
    assert clean["nested"]["password"] == "[REDACTED]"
    assert clean["nested"]["safe_key"] == "safe_value"
    assert clean["safe_field"] == 12345


def test_mask_secret_utility():
    """Verify mask_secret shows only prefix/suffix for debug purposes."""
    assert mask_secret("1000.abc123456789xyz", visible_chars=4) == "1000...9xyz"
    assert mask_secret(None) == "[empty]"
    assert mask_secret("short") == "***"


# ==============================================================================
# 2. OAUTH AUTHORIZATION & REPLAY PROTECTION TESTS
# ==============================================================================

def test_oauth_state_single_use_replay_protection():
    """Verify OAuth state can only be used once (replay protection)."""
    client = ZohoOAuthClient()
    user_id = uuid.uuid4()
    state = client.generate_state(user_id=user_id, connection_name="Test Org", data_center="in")

    # 1. First validation succeeds
    payload = client.validate_state(state)
    assert payload["sub"] == str(user_id)
    assert payload["dc"] == "in"

    # 2. Replay attempt with the EXACT SAME state must fail
    with pytest.raises(ZohoOAuthError) as exc:
        client.validate_state(state)
    assert "replay detected" in str(exc.value)


@pytest.mark.asyncio
async def test_oauth_token_exchange_ssrf_protection():
    """Verify exchange_code rejects unauthorized / rogue accounts URLs (SSRF protection)."""
    client = ZohoOAuthClient()
    with pytest.raises(ZohoOAuthError) as exc:
        await client.exchange_code(
            code="test_code",
            accounts_url="https://attacker-controlled-server.com",
        )
    assert "unauthorized Zoho accounts domain" in str(exc.value)


@pytest.mark.asyncio
async def test_oauth_token_exchange_timeout_handling():
    """Verify exchange_code handles network timeouts safely without exposing secrets."""
    client = ZohoOAuthClient()
    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Connection timed out")):
        with pytest.raises(ZohoOAuthError) as exc:
            await client.exchange_code(
                code="test_code",
                accounts_url="https://accounts.zoho.in",
            )
        assert "timeout" in str(exc.value).lower()


# ==============================================================================
# 3. DATABASE PERSISTENCE & RAW CIPHERTEXT VERIFICATION
# ==============================================================================

@pytest.mark.asyncio
async def test_raw_database_contains_ciphertext_not_plaintext(db_session: AsyncSession):
    """
    CRITICAL SECURITY CHECK:
    Inspect raw SQL rows directly from SQLite / PostgreSQL to guarantee
    tokens are physically stored as AES/Fernet ciphertext ('gAAAAA...'),
    and plaintext NEVER exists in table columns.
    """
    user = User(
        name="DB Security Auditor",
        email=f"auditor_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password="hashed_pw_xyz",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    plain_access = "1000.plain_access_secret_token_never_store_me_raw"
    plain_refresh = "1000.plain_refresh_secret_token_never_store_me_raw"

    integration = Integration(
        user_id=user.id,
        provider="zoho",
        connection_name="Encrypted Enterprise Zoho",
        external_account_id=f"org_{uuid.uuid4().hex[:6]}",
        access_token=plain_access,
        refresh_token=plain_refresh,
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        api_domain="https://www.zohoapis.in",
        status="active",
    )
    db_session.add(integration)
    await db_session.commit()

    # 1. Inspect raw stored strings bypassing EncryptedString TypeDecorator decryption
    raw_query = select(
        cast(Integration.access_token, String),
        cast(Integration.refresh_token, String),
    ).where(Integration.id == integration.id)
    result = await db_session.execute(raw_query)
    row = result.fetchone()

    assert row is not None
    raw_stored_access, raw_stored_refresh = row[0], row[1]

    # Verify raw database columns DO NOT contain plaintext
    assert raw_stored_access != plain_access
    assert raw_stored_refresh != plain_refresh

    # Verify raw database columns contain Fernet ciphertext
    assert raw_stored_access.startswith("gAAAAA")
    assert raw_stored_refresh.startswith("gAAAAA")

    # 2. Verify ORM read transparently decrypts
    await db_session.refresh(integration)
    assert integration.access_token == plain_access
    assert integration.refresh_token == plain_refresh


# ==============================================================================
# 4. TOKEN REFRESH: ROTATION AND PRESERVATION TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_refresh_preserves_existing_refresh_token_when_none_returned(db_session: AsyncSession):
    """
    Verify that if Zoho refresh endpoint returns an access_token but NO new refresh_token,
    the existing encrypted refresh_token is safely preserved and not cleared.
    """
    user = User(name="Tester", email=f"t_{uuid.uuid4().hex[:6]}@example.com", hashed_password="pw")
    db_session.add(user)
    await db_session.commit()

    orig_refresh = "1000.original_preserved_refresh_token_xyz"
    integration = Integration(
        user_id=user.id,
        provider="zoho",
        connection_name="Zoho Token Preserver",
        external_account_id=f"org_{uuid.uuid4().hex[:6]}",
        access_token="1000.old_access_token",
        refresh_token=orig_refresh,
        token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        api_domain="https://www.zohoapis.in",
        status="active",
    )
    db_session.add(integration)
    await db_session.commit()
    await db_session.refresh(integration)

    manager = ZohoTokenManager()

    # Response with NO refresh_token returned
    mock_resp_data = {
        "access_token": "1000.brand_new_access_token_456",
        "expires_in": 3600,
        "api_domain": "https://www.zohoapis.in",
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = httpx.Response(
            status_code=200,
            json=mock_resp_data,
            request=httpx.Request("POST", "https://accounts.zoho.in/oauth/v2/token"),
        )

        new_access = await manager.refresh_access_token(integration, db_session)

        assert new_access == "1000.brand_new_access_token_456"
        assert integration.access_token == "1000.brand_new_access_token_456"
        # Crucial check: refresh_token is preserved!
        assert integration.refresh_token == orig_refresh

        # Check raw DB
        raw_res = await db_session.execute(
            select(cast(Integration.refresh_token, String)).where(Integration.id == integration.id)
        )
        raw_refresh_in_db = raw_res.scalar_one()
        assert raw_refresh_in_db.startswith("gAAAAA")
        assert decrypt_token(raw_refresh_in_db) == orig_refresh


@pytest.mark.asyncio
async def test_refresh_updates_rotated_refresh_token(db_session: AsyncSession):
    """
    Verify that if Zoho returns a replacement refresh token (token rotation),
    it is encrypted and persisted in PostgreSQL.
    """
    user = User(name="Tester 2", email=f"t2_{uuid.uuid4().hex[:6]}@example.com", hashed_password="pw")
    db_session.add(user)
    await db_session.commit()

    old_refresh = "1000.old_refresh_token_to_replace"
    new_rotated_refresh = "1000.new_rotated_refresh_token_received"

    integration = Integration(
        user_id=user.id,
        provider="zoho",
        connection_name="Zoho Token Rotator",
        external_account_id=f"org_{uuid.uuid4().hex[:6]}",
        access_token="1000.old_access_token",
        refresh_token=old_refresh,
        token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        api_domain="https://www.zohoapis.in",
        status="active",
    )
    db_session.add(integration)
    await db_session.commit()
    await db_session.refresh(integration)

    manager = ZohoTokenManager()

    # Response with rotated refresh_token
    mock_resp_data = {
        "access_token": "1000.brand_new_access_token_789",
        "refresh_token": new_rotated_refresh,
        "expires_in": 3600,
        "api_domain": "https://www.zohoapis.in",
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = httpx.Response(
            status_code=200,
            json=mock_resp_data,
            request=httpx.Request("POST", "https://accounts.zoho.in/oauth/v2/token"),
        )

        new_access = await manager.refresh_access_token(integration, db_session)

        assert new_access == "1000.brand_new_access_token_789"
        assert integration.access_token == "1000.brand_new_access_token_789"
        assert integration.refresh_token == new_rotated_refresh

        # Check raw DB
        raw_res = await db_session.execute(
            select(cast(Integration.refresh_token, String)).where(Integration.id == integration.id)
        )
        raw_refresh_in_db = raw_res.scalar_one()
        assert raw_refresh_in_db.startswith("gAAAAA")
        assert decrypt_token(raw_refresh_in_db) == new_rotated_refresh


@pytest.mark.asyncio
async def test_failed_refresh_preserves_stored_credentials(db_session: AsyncSession):
    """Verify that a temporary network or upstream error does NOT wipe stored refresh tokens."""
    user = User(name="Tester 3", email=f"t3_{uuid.uuid4().hex[:6]}@example.com", hashed_password="pw")
    db_session.add(user)
    await db_session.commit()

    saved_refresh = "1000.saved_refresh_token_keep_me"
    saved_access = "1000.saved_access_token_keep_me"

    integration = Integration(
        user_id=user.id,
        provider="zoho",
        connection_name="Zoho Temp Error",
        external_account_id=f"org_{uuid.uuid4().hex[:6]}",
        access_token=saved_access,
        refresh_token=saved_refresh,
        token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        api_domain="https://www.zohoapis.in",
        status="active",
    )
    db_session.add(integration)
    await db_session.commit()
    await db_session.refresh(integration)

    manager = ZohoTokenManager()

    # Upstream temporary 500 error
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = httpx.Response(
            status_code=500,
            json={"error": "internal_zoho_service_error"},
            request=httpx.Request("POST", "https://accounts.zoho.in/oauth/v2/token"),
        )

        with pytest.raises(ZohoOAuthError):
            await manager.refresh_access_token(integration, db_session)

        # Credentials must not be erased
        assert integration.refresh_token == saved_refresh
        assert integration.access_token == saved_access
        assert integration.status == "active"


# ==============================================================================
# 5. DATA LEAKAGE & ENDPOINT SECURITY
# ==============================================================================

@pytest.mark.asyncio
async def test_api_endpoints_never_expose_tokens(client: AsyncClient, db_session: AsyncSession):
    """
    Verify that GET /api/v1/integrations and GET /api/v1/integrations/{id}
    NEVER include access_token or refresh_token in response payloads.
    """
    email = f"leak_test_{uuid.uuid4().hex[:6]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"name": "Auditor", "email": email, "password": "Password123!"},
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Connect
    conn_resp = await client.post(
        "/api/v1/integrations/zoho/connect",
        json={"connection_name": "Test Token Leakage", "data_center": "in"},
        headers=headers,
    )
    state = conn_resp.json()["state"]

    mock_token_result = {
        "access_token": "1000.secret_access_value_must_not_leak",
        "refresh_token": "1000.secret_refresh_value_must_not_leak",
        "api_domain": "https://www.zohoapis.in",
        "expires_in": 3600,
    }

    with patch.object(ZohoOAuthClient, "exchange_code", new_callable=AsyncMock, return_value=mock_token_result), \
         patch.object(ZohoOAuthClient, "fetch_organization_id", new_callable=AsyncMock, return_value="org_leak_999"):
        cb_resp = await client.get(f"/api/v1/integrations/zoho/callback?code=mock_code&state={state}")
        assert cb_resp.status_code == 200
        cb_json = cb_resp.json()
        int_id = cb_json["integration_id"]

        # 1. Callback response check
        assert "access_token" not in cb_json
        assert "refresh_token" not in cb_json
        assert "secret_access_value_must_not_leak" not in cb_resp.text
        assert "secret_refresh_value_must_not_leak" not in cb_resp.text

        # 2. List endpoint check
        list_resp = await client.get("/api/v1/integrations", headers=headers)
        assert list_resp.status_code == 200
        assert "secret_access_value_must_not_leak" not in list_resp.text
        assert "secret_refresh_value_must_not_leak" not in list_resp.text
        for item in list_resp.json():
            assert "access_token" not in item
            assert "refresh_token" not in item

        # 3. Detail endpoint check
        detail_resp = await client.get(f"/api/v1/integrations/{int_id}", headers=headers)
        assert detail_resp.status_code == 200
        assert "secret_access_value_must_not_leak" not in detail_resp.text
        assert "secret_refresh_value_must_not_leak" not in detail_resp.text
        assert "access_token" not in detail_resp.json()
        assert "refresh_token" not in detail_resp.json()
