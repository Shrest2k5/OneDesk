import asyncio
from typing import Any, Dict, List, Optional
import uuid
from celery import shared_task
from celery.utils.log import get_task_logger

from app.core.database import async_session_factory
from app.core.database import engine
from app.models.integration import Integration
from app.repositories.integration_repository import IntegrationRepository
from app.services.sync_service import SyncService
from app.services.books_transactions_service import BooksTransactionsService
from app.services.books_purchases_service import BooksPurchasesService

celery_logger = get_task_logger(__name__)

RESOURCE_TYPES_BY_PRODUCT = {
    "crm": ("contacts", "leads", "deals", "accounts"),
    # Books financial transactions use the dedicated Books transactions service;
    # the shared task supports the paginated resources implemented by the ERP adapter.
    "books": ("contacts", "invoices"),
    "erp": ("contacts", "customers", "vendors"),
}


async def _create_sync_record(integration_id_str: str, resource_type: str) -> str:
    """Create one execution row for task retries to reuse."""
    integration_id = uuid.UUID(integration_id_str)
    await engine.dispose()
    try:
        async with async_session_factory() as session:
            integration = await IntegrationRepository(session).get_by_id(integration_id)
            if not integration:
                raise ValueError(f"Integration with id {integration_id} not found.")
            if integration.status != "active":
                raise ValueError(f"Integration {integration_id} is in status '{integration.status}', cannot sync.")
            execution = await SyncService(session).start_sync_record(integration_id, resource_type)
            return str(execution.id)
    finally:
        await engine.dispose()


async def _run_async_sync(
    integration_id_str: str,
    resource_type: str,
    incremental: bool = True,
    sync_id_str: Optional[str] = None,
    fail_on_error: bool = True,
    per_page: int = 200,
) -> Dict[str, Any]:
    """Helper running asynchronous database session and sync logic inside Celery process."""
    integration_id = uuid.UUID(integration_id_str)

    # Dispose any connections left by a previous asyncio.run() before creating
    # this task's session. NullPool prevents reuse, and this is an extra guard
    # for deployments that replace the configured engine in tests.
    await engine.dispose()
    try:
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
                sync_id=uuid.UUID(sync_id_str) if sync_id_str else None,
                fail_on_error=fail_on_error,
                per_page=per_page,
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
    finally:
        await engine.dispose()


@shared_task(bind=True, max_retries=3, default_retry_delay=60, name="app.workers.sync_worker.sync_resource_task")
def sync_resource_task(
    self,
    integration_id: str,
    resource_type: str,
    incremental: bool = True,
    sync_id: Optional[str] = None,
    per_page: int = 200,
) -> Dict[str, Any]:
    """
    Celery task to synchronize a single resource type with retry on transient network errors.
    """
    celery_logger.info(f"Starting Celery sync for integration {integration_id} [{resource_type}]...")
    try:
        if sync_id is None:
            sync_id = asyncio.run(_create_sync_record(integration_id, resource_type))
        return asyncio.run(
            _run_async_sync(
                integration_id,
                resource_type,
                incremental,
                sync_id,
                fail_on_error=self.request.retries >= self.max_retries,
                per_page=per_page,
            )
        )
    except Exception as exc:
        celery_logger.error(f"Error in sync_resource_task: {exc}")
        # Retry only for transient failures, don't retry if record not found
        retryable = "not found" not in str(exc).lower() and "revoked" not in str(exc).lower()
        if retryable and self.request.retries < self.max_retries:
            if sync_id:
                async def reset():
                    async with async_session_factory() as session:
                        await SyncService(session).retry_sync_record(uuid.UUID(sync_id))
                asyncio.run(reset())
            raise self.retry(
                exc=exc,
                countdown=60 * (self.request.retries + 1),
                kwargs={
                    "integration_id": integration_id,
                    "resource_type": resource_type,
                    "incremental": incremental,
                    "sync_id": sync_id,
                    "per_page": per_page,
                },
            )
        if sync_id:
            async def fail_final():
                async with async_session_factory() as session:
                    await SyncService(session).fail_sync_record(uuid.UUID(sync_id), str(exc))
            asyncio.run(fail_final())
        raise exc


async def _run_books_transactions_sync(
    integration_id_str: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    integration_id = uuid.UUID(integration_id_str)
    await engine.dispose()
    try:
        async with async_session_factory() as session:
            integration = await IntegrationRepository(session).get_by_id(integration_id)
            if not integration:
                raise ValueError(f"Integration with id {integration_id} not found.")
            if integration.provider != "zoho" or integration.product != "books":
                raise ValueError(f"Integration {integration_id} is not a Zoho Books integration.")
            if integration.status != "active":
                raise ValueError(f"Integration {integration_id} is in status '{integration.status}', cannot sync.")
            job = await BooksTransactionsService(session, integration).synchronize(start_date, end_date)
            result = {
                "sync_id": str(job.id), "integration_id": str(integration.id),
                "resource_type": "financial_transactions", "status": job.status,
                "records_processed": job.records_processed, "records_inserted": job.records_inserted,
                "records_updated": job.records_updated, "records_failed": job.records_failed,
                "error": job.error_message,
            }
            if job.status == "failed":
                raise RuntimeError(job.error_message or "Books financial synchronization failed")
            return result
    finally:
        await engine.dispose()


@shared_task(bind=True, max_retries=3, default_retry_delay=60, name="app.workers.sync_worker.sync_books_transactions_task")
def sync_books_transactions_task(
    self,
    integration_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Synchronize all Books financial modules for a selected date range."""
    try:
        return asyncio.run(_run_books_transactions_sync(integration_id, start_date, end_date))
    except Exception as exc:
        celery_logger.error("Books financial sync failed for %s: %s", integration_id, type(exc).__name__)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
        raise


async def _run_books_purchases_sync(integration_id_str: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
    integration_id = uuid.UUID(integration_id_str)
    await engine.dispose()
    try:
        async with async_session_factory() as session:
            integration = await IntegrationRepository(session).get_by_id(integration_id)
            if not integration or integration.provider != "zoho" or integration.product != "books":
                raise ValueError(f"Integration {integration_id} is not a Zoho Books integration.")
            if integration.status != "active":
                raise ValueError(f"Integration {integration_id} is not active.")
            resolved_integration_id = integration.id
            job = await BooksPurchasesService(session, integration).synchronize(start_date, end_date)
            result = {"sync_id": str(job.id), "integration_id": str(resolved_integration_id), "resource_type": "purchases", "status": job.status, "records_processed": job.records_processed, "records_inserted": job.records_inserted, "records_updated": job.records_updated, "records_failed": job.records_failed, "error": job.error_message}
            if job.status == "failed":
                # Permission failures are permanent until reauthorization or
                # a Books role change; do not retry the same provider request.
                if job.error_message and ("authorization failed (HTTP 401)" in job.error_message or "authorization failed (HTTP 403)" in job.error_message):
                    return result
                raise RuntimeError(job.error_message or "Books purchases synchronization failed")
            return result
    finally:
        await engine.dispose()


@shared_task(bind=True, max_retries=3, default_retry_delay=60, name="app.workers.sync_worker.sync_books_purchases_task")
def sync_books_purchases_task(self, integration_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
    try:
        return asyncio.run(_run_books_purchases_sync(integration_id, start_date, end_date))
    except Exception as exc:
        celery_logger.error("Books purchases sync failed for %s: %s", integration_id, type(exc).__name__)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
        raise


@shared_task(bind=True, max_retries=1, name="app.workers.sync_worker.sync_all_resources_task")
def sync_all_resources_task(
    self,
    integration_id: str,
    incremental: bool = True,
) -> List[Dict[str, Any]]:
    """
    Celery task to synchronize all standard CRM resources for an integration.
    """
    async def get_product() -> str:
        async with async_session_factory() as session:
            integration = await IntegrationRepository(session).get_by_id(uuid.UUID(integration_id))
            if not integration:
                raise ValueError(f"Integration with id {integration_id} not found.")
            return integration.product

    product = asyncio.run(get_product())
    resources = RESOURCE_TYPES_BY_PRODUCT.get(product, ())
    if not resources:
        raise ValueError(f"No synchronization resource mapping exists for product '{product}'.")
    results = []
    for res in resources:
        res_summary = sync_resource_task.apply(args=[integration_id, res, incremental]).get()
        results.append(res_summary)
    return results

