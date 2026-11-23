from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.integrations.odoo.integration import odoo_integration
from app.models.user import User
from app.services.integration_service import IntegrationService
from app.services.odoo_contacts_service import OdooContactsService
from app.services.sync_service import SyncService


router = APIRouter(prefix="/integrations/odoo", tags=["Odoo Integration"])


class OdooConnectRequest(BaseModel):
    connection_name: str = Field(default="My Odoo ERP", min_length=1, max_length=100)
    instance_url: HttpUrl = Field(description="Externally hosted Odoo base URL")
    api_key: str = Field(min_length=1, max_length=2048, repr=False)
    database: Optional[str] = Field(default=None, min_length=1, max_length=100)
    integration_id: Optional[uuid.UUID] = None


class OdooConnectResponse(BaseModel):
    id: uuid.UUID
    provider: str
    product: str
    connection_name: str
    api_domain: Optional[str]
    external_database: Optional[str]
    status: str


class OdooContactsResponse(BaseModel):
    data: List[Dict[str, Any]]
    pagination: Dict[str, Any]
    sync: Dict[str, Any]


@router.post(
    "/connect",
    response_model=OdooConnectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Validate and connect an external Odoo JSON-2 instance",
)
async def connect_odoo(
    request: OdooConnectRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> OdooConnectResponse:
    integration = await odoo_integration.connect(
        user_id=current_user.id,
        connection_name=request.connection_name,
        instance_url=str(request.instance_url),
        api_key=request.api_key,
        database=request.database,
        integration_id=request.integration_id,
        session=session,
    )
    return OdooConnectResponse(
        id=integration.id,
        provider=integration.provider,
        product=integration.product,
        connection_name=integration.connection_name,
        api_domain=integration.api_domain,
        external_database=integration.external_database,
        status=integration.status,
    )


async def _owned_odoo_integration(user: User, integration_id: uuid.UUID, session: AsyncSession):
    integration = await IntegrationService(session).get_user_integration(user.id, integration_id)
    if integration.provider != "odoo" or integration.product != "erp":
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="The selected integration is not an Odoo ERP connection.")
    return integration


@router.get("/{integration_id}/contacts", response_model=OdooContactsResponse)
async def list_odoo_contacts(
    integration_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=500),
    kind: Optional[str] = Query(None, pattern="^(customer|vendor)$"),
    search: Optional[str] = Query(None, max_length=200),
    include_archived: bool = True,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    integration = await _owned_odoo_integration(current_user, integration_id, session)
    service = OdooContactsService(session, integration)
    result = await service.list_local(page, per_page, kind, search, include_archived)
    result["sync"] = await service.sync_status()
    return result


@router.get("/{integration_id}/contacts/stats")
async def odoo_contact_stats(
    integration_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    integration = await _owned_odoo_integration(current_user, integration_id, session)
    return await OdooContactsService(session, integration).stats()


@router.post("/{integration_id}/contacts/refresh")
async def refresh_odoo_contacts(
    integration_id: uuid.UUID,
    async_mode: bool = True,
    per_page: int = Query(200, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    integration = await _owned_odoo_integration(current_user, integration_id, session)
    sync = SyncService(session)
    if async_mode:
        from app.workers.sync_worker import sync_resource_task
        job = await sync.start_sync_record(integration.id, "contacts")
        task = sync_resource_task.delay(
            integration_id=str(integration.id), resource_type="contacts", incremental=False,
            sync_id=str(job.id), per_page=per_page,
        )
        return {"status": "queued", "task_id": task.id, "sync_id": str(job.id)}
    job = await sync.sync_resource(integration, "contacts", incremental=False, per_page=per_page)
    return {"status": job.status, "sync_id": str(job.id), "records_processed": job.records_processed}
