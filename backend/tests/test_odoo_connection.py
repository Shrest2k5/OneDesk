from unittest.mock import AsyncMock, patch
import uuid

import httpx
import pytest
from sqlalchemy import Uuid, bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.integrations.odoo.client import OdooClient
from app.integrations.odoo.exceptions import (
    OdooAuthenticationError,
    OdooConfigurationError,
    OdooConnectionError,
    OdooPermissionError,
    OdooUnsupportedError,
)
from app.integrations.odoo.integration import odoo_integration
from app.models.integration import Integration
from app.models.user import User


class FakeAsyncClient:
    def __init__(self, response: httpx.Response):
        self.response = response
        self.request_args = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, **kwargs):
        self.request_args = (url, kwargs)
        return self.response


def response(status_code: int, payload: object) -> httpx.Response:
    return httpx.Response(status_code, json=payload, request=httpx.Request("POST", "https://odoo.example.com/json/2/res.users/context_get"))


@pytest.mark.asyncio
async def test_odoo_client_uses_json2_bearer_auth_and_optional_database():
    fake = FakeAsyncClient(response(200, {"uid": 7, "lang": "en_US"}))
    with patch("app.integrations.odoo.client.httpx.AsyncClient", return_value=fake):
        result = await OdooClient("https://odoo.example.com", "secret-api-key", "production").get_user_context()

    assert result["uid"] == 7
    url, kwargs = fake.request_args
    assert url == "https://odoo.example.com/json/2/res.users/context_get"
    assert kwargs["headers"]["Authorization"] == "bearer secret-api-key"
    assert kwargs["headers"]["X-Odoo-Database"] == "production"
    assert kwargs["json"] == {}


@pytest.mark.parametrize("url", [
    "http://odoo.example.com",
    "https://localhost:8069",
    "https://127.0.0.1",
    "https://user:pass@odoo.example.com",
    "https://odoo.example.com?database=prod",
])
def test_odoo_client_rejects_unsafe_instance_urls(url: str):
    with pytest.raises(OdooConfigurationError):
        OdooClient(url, "api-key")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "exception"),
    [(401, OdooAuthenticationError), (403, OdooPermissionError), (404, OdooUnsupportedError)],
)
async def test_odoo_client_maps_auth_permission_and_endpoint_errors(status_code, exception):
    fake = FakeAsyncClient(response(status_code, {"message": "provider detail", "api_key": "do-not-log"}))
    with patch("app.integrations.odoo.client.httpx.AsyncClient", return_value=fake):
        with pytest.raises(exception) as exc_info:
            await OdooClient("https://odoo.example.com", "secret-api-key").get_user_context()
    assert exc_info.value.details.get("api_key") == "[REDACTED]"


@pytest.mark.asyncio
async def test_odoo_client_maps_unreachable_instance():
    fake = FakeAsyncClient(response(200, {}))
    fake.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
    with patch("app.integrations.odoo.client.httpx.AsyncClient", return_value=fake):
        with pytest.raises(OdooConnectionError, match="could not be reached"):
            await OdooClient("https://odoo.example.com", "secret-api-key").get_user_context()


@pytest.mark.asyncio
async def test_odoo_connect_validates_before_persisting_and_encrypts_key(db_session: AsyncSession):
    user = User(name="Odoo Owner", email=f"odoo_{uuid.uuid4().hex}@example.com", hashed_password="hashed")
    db_session.add(user)
    await db_session.commit()
    with patch.object(OdooClient, "get_user_context", new_callable=AsyncMock, return_value={"uid": 9, "lang": "en_US"}):
        integration = await odoo_integration.connect(
            user_id=user.id,
            connection_name="External Odoo",
            instance_url="https://odoo.example.com/",
            api_key="secret-api-key",
            database="production",
            session=db_session,
        )

    assert integration.status == "active"
    assert integration.access_token == "secret-api-key"
    assert integration.external_database == "production"
    raw_query = text("SELECT access_token FROM integrations WHERE id = :id").bindparams(
        bindparam("id", type_=Uuid),
    )
    raw = await db_session.execute(raw_query, {"id": integration.id})
    assert raw.scalar_one() != "secret-api-key"


@pytest.mark.asyncio
async def test_odoo_failed_validation_does_not_persist(db_session: AsyncSession):
    user = User(name="Odoo Owner", email=f"odoo_fail_{uuid.uuid4().hex}@example.com", hashed_password="hashed")
    db_session.add(user)
    await db_session.commit()
    with patch.object(OdooClient, "get_user_context", side_effect=OdooAuthenticationError("invalid key", status_code=401)):
        with pytest.raises(OdooAuthenticationError):
            await odoo_integration.connect(user.id, "Odoo", "https://odoo.example.com", "bad-key", None, db_session)
    count_query = text("SELECT COUNT(*) FROM integrations WHERE user_id = :id").bindparams(
        bindparam("id", type_=Uuid),
    )
    result = await db_session.execute(count_query, {"id": user.id})
    assert result.scalar_one() == 0


@pytest.mark.asyncio
async def test_odoo_reconnect_rejects_cross_tenant_integration(db_session: AsyncSession):
    owner = User(name="Owner", email=f"owner_{uuid.uuid4().hex}@example.com", hashed_password="hashed")
    attacker = User(name="Attacker", email=f"attacker_{uuid.uuid4().hex}@example.com", hashed_password="hashed")
    db_session.add_all([owner, attacker])
    await db_session.commit()
    integration = Integration(user_id=owner.id, provider="odoo", product="erp", connection_name="Owned", status="active")
    db_session.add(integration)
    await db_session.commit()
    with patch.object(OdooClient, "get_user_context", new_callable=AsyncMock, return_value={"uid": 9}):
        with pytest.raises(OdooConfigurationError):
            await odoo_integration.connect(attacker.id, "Hijack", "https://odoo.example.com", "new-key", None, db_session, integration.id)


@pytest.mark.asyncio
async def test_odoo_disconnect_is_tenant_scoped(client, db_session: AsyncSession):
    user = User(name="Disconnect User", email=f"disconnect_{uuid.uuid4().hex}@example.com", hashed_password="hashed")
    db_session.add(user)
    await db_session.commit()
    integration = Integration(user_id=user.id, provider="odoo", product="erp", connection_name="Odoo", status="active")
    db_session.add(integration)
    await db_session.commit()
    token = create_access_token(subject=user.id)
    result = await client.delete(f"/api/v1/integrations/{integration.id}", headers={"Authorization": f"Bearer {token}"})
    assert result.status_code == 200
    assert await db_session.get(Integration, integration.id) is None
