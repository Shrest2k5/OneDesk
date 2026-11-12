import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    decode_access_token,
    decrypt_token,
    encrypt_token,
    hash_password,
    verify_password,
)
from app.models import Integration, SyncHistory, User


@pytest.mark.asyncio
async def test_health_endpoints(client: AsyncClient):
    """Test root and API v1 health check endpoints."""
    # Root health
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "OneDesk" in data["service"]

    # API v1 health
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "0.1.0"


def test_password_hashing():
    """Test bcrypt password hashing and verification."""
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_jwt_token_flow():
    """Test JWT access token creation and decoding."""
    user_id = str(uuid.uuid4())
    token = create_access_token(subject=user_id, extra_claims={"email": "test@example.com"})

    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == user_id
    assert decoded["email"] == "test@example.com"
    assert "exp" in decoded

    # Test invalid token
    invalid_decoded = decode_access_token("invalid.token.payload")
    assert invalid_decoded is None


def test_token_encryption_at_rest():
    """Test Fernet symmetric token encryption and decryption."""
    raw_token = "1000.a1b2c3d4e5f6g7h8i9j0k.sensitive_oauth_token"
    encrypted = encrypt_token(raw_token)

    assert encrypted != raw_token
    assert encrypted is not None

    decrypted = decrypt_token(encrypted)
    assert decrypted == raw_token

    # None handling
    assert encrypt_token(None) is None
    assert decrypt_token(None) is None


@pytest.mark.asyncio
async def test_database_models_and_encryption(db_session: AsyncSession):
    """
    Test SQLAlchemy models: User, Integration, SyncHistory,
    including transparent token encryption and cascade behaviors.
    """
    # 1. Create User
    user = User(
        name="Alice Architect",
        email="alice@enterprise.com",
        hashed_password=hash_password("SecurePassword456!"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.id is not None
    assert user.created_at is not None
    assert user.updated_at is not None

    # 2. Create Integration with sensitive tokens
    raw_access = "zoho_access_token_12345"
    raw_refresh = "zoho_refresh_token_67890"

    integration = Integration(
        user_id=user.id,
        provider="zoho",
        external_account_id="zoho_org_1001",
        connection_name="Alice Production Zoho",
        access_token=raw_access,
        refresh_token=raw_refresh,
        token_expires_at=datetime.now(timezone.utc),
        api_domain="https://www.zohoapis.com",
        status="active",
    )
    db_session.add(integration)
    await db_session.commit()
    await db_session.refresh(integration)

    assert integration.id is not None
    # Verify transparent decryption on read
    assert integration.access_token == raw_access
    assert integration.refresh_token == raw_refresh

    # 3. Create SyncHistory record
    sync = SyncHistory(
        integration_id=integration.id,
        resource_type="contacts",
        status="completed",
        records_processed=150,
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(sync)
    await db_session.commit()
    await db_session.refresh(sync)

    assert sync.id is not None
    assert sync.resource_type == "contacts"
    assert sync.records_processed == 150
    assert sync.status == "completed"

    # 4. Verify cascade deletion: deleting user removes integration and sync history
    await db_session.delete(user)
    await db_session.commit()

    integrations_result = await db_session.execute(
        select(Integration).where(Integration.user_id == user.id)
    )
    assert integrations_result.scalars().all() == []

    syncs_result = await db_session.execute(
        select(SyncHistory).where(SyncHistory.integration_id == integration.id)
    )
    assert syncs_result.scalars().all() == []

