import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_user_registration_success(client: AsyncClient):
    """Test successful user registration."""
    payload = {
        "name": "Bob Builder",
        "email": "bob@enterprise.com",
        "password": "SecurePassword123!",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Bob Builder"
    assert data["email"] == "bob@enterprise.com"
    assert "id" in data
    assert "hashed_password" not in data
    assert "password" not in data


@pytest.mark.asyncio
async def test_user_registration_duplicate_email(client: AsyncClient):
    """Test duplicate registration rejection."""
    payload = {
        "name": "Bob Builder",
        "email": "bob@enterprise.com",
        "password": "SecurePassword123!",
    }
    # First registration
    resp1 = await client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201

    # Second registration with same email
    resp2 = await client.post("/api/v1/auth/register", json=payload)
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_user_registration_validation(client: AsyncClient):
    """Test validation errors for short password or invalid email."""
    # Password too short (< 8 characters)
    short_pw_payload = {
        "name": "Bob",
        "email": "bob@test.com",
        "password": "short",
    }
    resp1 = await client.post("/api/v1/auth/register", json=short_pw_payload)
    assert resp1.status_code == 422

    # Invalid email
    invalid_email_payload = {
        "name": "Bob",
        "email": "not-an-email",
        "password": "ValidPassword123!",
    }
    resp2 = await client.post("/api/v1/auth/register", json=invalid_email_payload)
    assert resp2.status_code == 422


@pytest.mark.asyncio
async def test_user_login_success(client: AsyncClient):
    """Test successful login returning valid JWT."""
    # Register user
    reg_payload = {
        "name": "Charlie Chaplin",
        "email": "charlie@enterprise.com",
        "password": "MySecretPassword88!",
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    # Login
    login_payload = {
        "email": "charlie@enterprise.com",
        "password": "MySecretPassword88!",
    }
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_user_login_invalid_credentials(client: AsyncClient):
    """Test login failure with wrong password and unknown user."""
    # Register user
    await client.post(
        "/api/v1/auth/register",
        json={"name": "Dan", "email": "dan@enterprise.com", "password": "CorrectPassword123!"},
    )

    # Wrong password
    resp1 = await client.post(
        "/api/v1/auth/login",
        json={"email": "dan@enterprise.com", "password": "WrongPassword!"},
    )
    assert resp1.status_code == 401
    assert "Incorrect email or password" in resp1.json()["detail"]

    # Unknown email
    resp2 = await client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@enterprise.com", "password": "AnyPassword123!"},
    )
    assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_endpoint(client: AsyncClient):
    """Test /api/v1/auth/me profile endpoint with valid, invalid, and missing tokens."""
    # Register and login
    await client.post(
        "/api/v1/auth/register",
        json={"name": "Eve Adams", "email": "eve@enterprise.com", "password": "StrongPassword99!"},
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "eve@enterprise.com", "password": "StrongPassword99!"},
    )
    token = login_resp.json()["access_token"]

    # 1. Valid Token
    me_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["name"] == "Eve Adams"
    assert me_data["email"] == "eve@enterprise.com"
    assert "hashed_password" not in me_data

    # 2. Missing Token
    unauth_resp = await client.get("/api/v1/auth/me")
    assert unauth_resp.status_code in [401, 403]

    # 3. Invalid / Tampered Token
    tampered_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer forged.invalid.token"},
    )
    assert tampered_resp.status_code == 401

