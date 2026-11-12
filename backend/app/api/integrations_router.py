from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.models.user import User
from app.services.integration_service import IntegrationService

router = APIRouter(prefix="/integrations", tags=["Integration Management"])


class IntegrationResponse(BaseModel):
    id: uuid.UUID
    provider: str
    connection_name: str
    external_account_id: Optional[str] = None
    status: str
    api_domain: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get(
    "",
    response_model=List[IntegrationResponse],
    status_code=status.HTTP_200_OK,
    summary="List all connected ERP integrations for current user",
)
async def list_integrations(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Retrieve all ERP connections belonging to the authenticated user.
    Tokens are strictly excluded from the response payload.
    """
    service = IntegrationService(session)
    return await service.list_user_integrations(current_user.id)


@router.get(
    "/{integration_id}",
    response_model=IntegrationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get integration connection details",
)
async def get_integration(
    integration_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get connection details for a specific integration with tenant ownership verification.
    """
    service = IntegrationService(session)
    return await service.get_user_integration(current_user.id, integration_id)


@router.get(
    "/{integration_id}/status",
    status_code=status.HTTP_200_OK,
    summary="Check live connection status against remote ERP provider",
)
async def check_integration_status(
    integration_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Query the external ERP API (e.g. Zoho CRM org API) to verify token validity and connectivity.
    """
    service = IntegrationService(session)
    return await service.get_integration_status(current_user.id, integration_id)


class SyncRequest(BaseModel):
    resource_type: str = "contacts"
    incremental: bool = True
    async_mode: bool = False


class SyncHistoryResponse(BaseModel):
    id: uuid.UUID
    integration_id: uuid.UUID
    resource_type: str
    status: str
    records_processed: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


@router.post(
    "/{integration_id}/sync",
    response_model=SyncHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger on-demand or background synchronization",
)
async def trigger_sync(
    integration_id: uuid.UUID,
    request: SyncRequest = SyncRequest(),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Trigger data synchronization for a specific ERP integration.
    Verifies tenant ownership. If async_mode is true, dispatches to Celery background worker.
    """
    int_service = IntegrationService(session)
    integration = await int_service.get_user_integration(current_user.id, integration_id)

    from app.services.sync_service import SyncService
    sync_service = SyncService(session)

    if request.async_mode:
        from app.workers.sync_worker import sync_resource_task
        task = sync_resource_task.delay(
            integration_id=str(integration.id),
            resource_type=request.resource_type,
            incremental=request.incremental,
        )
        sync_job = await sync_service.start_sync_record(integration.id, request.resource_type)
        return sync_job

    # Synchronous inline execution
    sync_job = await sync_service.sync_resource(
        integration=integration,
        resource_type=request.resource_type,
        incremental=request.incremental,
    )
    return sync_job


@router.get(
    "/{integration_id}/sync-history",
    response_model=List[SyncHistoryResponse],
    status_code=status.HTTP_200_OK,
    summary="Get synchronization history and job logs for an integration",
)
async def get_sync_history(
    integration_id: uuid.UUID,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Retrieve historical synchronization audit logs for an integration.
    """
    int_service = IntegrationService(session)
    await int_service.get_user_integration(current_user.id, integration_id)

    from app.services.sync_service import SyncService
    sync_service = SyncService(session)
    return await sync_service.get_history_by_integration(integration_id, limit=limit)


@router.delete(
    "/{integration_id}",
    status_code=status.HTTP_200_OK,
    summary="Disconnect and delete an ERP connection",
)
async def disconnect_integration(
    integration_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Disconnect and remove an ERP integration.
    Associated background sync histories are automatically cascade-deleted.
    """
    service = IntegrationService(session)
    await service.delete_user_integration(current_user.id, integration_id)
    return {
        "status": "success",
        "message": f"Integration '{integration_id}' disconnected successfully.",
    }

