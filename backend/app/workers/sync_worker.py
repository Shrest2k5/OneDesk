import asyncio
from typing import Any, Dict, List, Optional
import uuid
from celery import shared_task
from celery.utils.log import get_task_logger

from app.core.database import async_session_factory
from app.models.integration import Integration
from app.repositories.integration_repository import IntegrationRepository
from app.services.sync_service import SyncService

celery_logger = get_task_logger(__name__)


async def _run_async_sync(
    integration_id_str: str,
    resource_type: str,
    incremental: bool = True,
) -> Dict[str, Any]:
    """Helper running asynchronous database session and sync logic inside Celery process."""
    integration_id = uuid.UUID(integration_id_str)

    async with async_session_factory() as session:
        repo = IntegrationRepository(session)
        integration = await repo.get_by_id(integration_id)
        if not integration:
            raise ValueError(f"Integration with id {integration_id} not found.")

        if integration.status != "active":
            raise ValueError(f"Integration {integration_id} is in status '{integration.status}', cannot sync.")

        sync_service = SyncService(session)
        sync_result = await sync_service.sync_resource(
            integration=integration,
            resource_type=resource_type,
            incremental=incremental,
        )

        return {
            "sync_id": str(sync_result.id),
            "integration_id": str(integration_id),
            "resource_type": resource_type,
            "status": sync_result.status,
            "records_processed": sync_result.records_processed,
            "started_at": sync_result.started_at.isoformat() if sync_result.started_at else None,
            "completed_at": sync_result.completed_at.isoformat() if sync_result.completed_at else None,
        }


@shared_task(bind=True, max_retries=3, default_retry_delay=60, name="app.workers.sync_worker.sync_resource_task")
def sync_resource_task(
    self,
    integration_id: str,
    resource_type: str,
    incremental: bool = True,
) -> Dict[str, Any]:
    """
    Celery task to synchronize a single resource type with retry on transient network errors.
    """
    celery_logger.info(f"Starting Celery sync for integration {integration_id} [{resource_type}]...")
    try:
        return asyncio.run(_run_async_sync(integration_id, resource_type, incremental))
    except Exception as exc:
        celery_logger.error(f"Error in sync_resource_task: {exc}")
        # Retry only for transient failures, don't retry if record not found
        if "not found" not in str(exc).lower() and "revoked" not in str(exc).lower():
            raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
        raise exc


@shared_task(bind=True, max_retries=1, name="app.workers.sync_worker.sync_all_resources_task")
def sync_all_resources_task(
    self,
    integration_id: str,
    incremental: bool = True,
) -> List[Dict[str, Any]]:
    """
    Celery task to synchronize all standard CRM resources for an integration.
    """
    resources = ["contacts", "leads", "deals", "accounts"]
    results = []
    for res in resources:
        res_summary = sync_resource_task.apply(args=[integration_id, res, incremental]).get()
        results.append(res_summary)
    return results
