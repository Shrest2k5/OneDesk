import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.core.logging import logger
from app.integrations.registry import integration_registry
from app.models.integration import Integration
from app.models.sync_history import SyncHistory
from app.repositories.integration_repository import IntegrationRepository
from app.repositories.integration_record_repository import IntegrationRecordRepository


class SyncService:
    """
    Core synchronization service managing on-demand and background sync jobs,
    incremental delta synchronization, error capture, and audit history.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.integration_repo = IntegrationRepository(session)
        self.record_repo = IntegrationRecordRepository(session)

    async def get_last_successful_sync(
        self,
        integration_id: uuid.UUID,
        resource_type: str,
    ) -> Optional[SyncHistory]:
        """Find the most recent successfully completed sync job for incremental timestamping."""
        query = (
            select(SyncHistory)
            .where(
                SyncHistory.integration_id == integration_id,
                SyncHistory.resource_type == resource_type,
                SyncHistory.status == "completed",
                SyncHistory.successful_at.is_not(None),
            )
            .order_by(desc(SyncHistory.completed_at))
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def start_sync_record(
        self,
        integration_id: uuid.UUID,
        resource_type: str,
    ) -> SyncHistory:
        """Create an in-progress SyncHistory record."""
        sync_job = SyncHistory(
            integration_id=integration_id,
            resource_type=resource_type,
            status="in_progress",
            records_processed=0,
            started_at=datetime.now(timezone.utc),
        )
        self.session.add(sync_job)
        await self.session.commit()
        await self.session.refresh(sync_job)
        return sync_job

    async def complete_sync_record(
        self,
        sync_id: uuid.UUID,
        records_count: int,
        records_inserted: int = 0,
        records_updated: int = 0,
        records_failed: int = 0,
    ) -> SyncHistory:
        """Mark a sync job as completed with total records count."""
        query = select(SyncHistory).where(SyncHistory.id == sync_id)
        result = await self.session.execute(query)
        sync_job = result.scalar_one()

        sync_job.status = "completed"
        sync_job.records_processed = records_count
        sync_job.records_inserted = records_inserted
        sync_job.records_updated = records_updated
        sync_job.records_failed = records_failed
        sync_job.completed_at = datetime.now(timezone.utc)
        sync_job.successful_at = sync_job.completed_at if records_failed == 0 else None

        await self.session.commit()
        await self.session.refresh(sync_job)
        return sync_job

    async def fail_sync_record(
        self,
        sync_id: uuid.UUID,
        error_message: str,
        records_processed: Optional[int] = None,
        records_inserted: Optional[int] = None,
        records_updated: Optional[int] = None,
        records_failed: Optional[int] = None,
    ) -> SyncHistory:
        """Mark a sync job as failed with captured error details."""
        query = select(SyncHistory).where(SyncHistory.id == sync_id)
        result = await self.session.execute(query)
        sync_job = result.scalar_one_or_none()
        if not sync_job:
            return None

        sync_job.status = "failed"
        sync_job.error_message = error_message
        sync_job.completed_at = datetime.now(timezone.utc)
        if records_processed is not None:
            sync_job.records_processed = records_processed
        if records_inserted is not None:
            sync_job.records_inserted = records_inserted
        if records_updated is not None:
            sync_job.records_updated = records_updated
        if records_failed is not None:
            sync_job.records_failed = records_failed

        await self.session.commit()
        await self.session.refresh(sync_job)
        return sync_job

    async def retry_sync_record(self, sync_id: uuid.UUID) -> Optional[SyncHistory]:
        """Return a retrying execution to in_progress without losing its audit row."""
        query = select(SyncHistory).where(SyncHistory.id == sync_id)
        result = await self.session.execute(query)
        sync_job = result.scalar_one_or_none()
        if not sync_job:
            return None
        sync_job.status = "in_progress"
        sync_job.error_message = None
        sync_job.completed_at = None
        await self.session.commit()
        return sync_job

    async def recover_abandoned_syncs(self, stale_after: timedelta = timedelta(hours=2)) -> int:
        """Fail only executions older than the worker's maximum task lifetime.

        This is intended for an operator/periodic cleanup job. The two-hour
        default is deliberately above Celery's one-hour hard limit, so active
        tasks are not interrupted by recovery.
        """
        cutoff = datetime.now(timezone.utc) - stale_after
        result = await self.session.execute(
            update(SyncHistory)
            .where(SyncHistory.status == "in_progress", SyncHistory.started_at < cutoff)
            .values(
                status="failed",
                completed_at=datetime.now(timezone.utc),
                error_message="Execution abandoned after exceeding the recovery grace period.",
            )
        )
        await self.session.commit()
        return result.rowcount or 0

    async def sync_resource(
        self,
        integration: Integration,
        resource_type: str,
        incremental: bool = True,
        sync_id: Optional[uuid.UUID] = None,
        fail_on_error: bool = True,
        per_page: int = 200,
    ) -> SyncHistory:
        """
        Execute full or incremental synchronization of an ERP resource type
        (contacts, leads, deals, accounts) across all available pages.
        """
        provider = integration_registry.get(integration.provider, integration.product)
        if not provider:
            raise ValueError(f"Unsupported ERP provider '{integration.provider}'")

        # Create the audit job before doing external work. A queued API request
        # passes its existing row so the worker updates the row the caller sees.
        sync_job = await (
            self._get_sync_record(sync_id)
            if sync_id
            else self.start_sync_record(integration.id, resource_type)
        )
        if sync_job is None:
            raise ValueError(f"Sync execution {sync_id} not found")
        sync_job.status = "in_progress"
        await self.session.commit()

        # Determine delta sync timestamp if incremental
        modified_since: Optional[str] = None
        if incremental:
            last_sync = await self.get_last_successful_sync(integration.id, resource_type)
            if last_sync and last_sync.completed_at:
                modified_since = last_sync.completed_at.strftime("%Y-%m-%dT%H:%M:%SZ")

        total_records = 0
        total_inserted = 0
        total_updated = 0
        total_failed = 0
        page = 1
        per_page = max(1, min(per_page, 500))
        sync_job_id = sync_job.id

        try:
            while True:
                response = await provider.fetch_records(
                    integration=integration,
                    resource_type=resource_type,
                    page=page,
                    per_page=per_page,
                    modified_since=modified_since,
                    session=self.session,
                )

                items = response.get("data", [])
                total_records += len(items)

                page_inserted = page_updated = page_failed = 0
                for item in items:
                    try:
                        external_organization_id = (
                            integration.selected_organization_id
                            if integration.product == "books"
                            else integration.external_account_id
                        )
                        if integration.provider == "odoo":
                            external_organization_id = integration.external_database or integration.api_domain or "odoo-default"
                        stored_resource_type = "contacts" if (integration.provider == "odoo" and resource_type in {"contacts", "customers", "vendors"}) else resource_type
                        outcome = await self.record_repo.upsert(
                            user_id=integration.user_id,
                            integration_id=integration.id,
                            provider=integration.provider,
                            product=integration.product,
                            external_organization_id=external_organization_id,
                            resource_type=stored_resource_type,
                            payload=item,
                        )
                        if outcome == "inserted":
                            page_inserted += 1
                        else:
                            page_updated += 1
                    except (ValueError, TypeError, KeyError) as exc:
                        page_failed += 1
                        logger.warning("Skipping invalid %s record during sync: %s", resource_type, type(exc).__name__)

                total_inserted += page_inserted
                total_updated += page_updated
                total_failed += page_failed
                # Commit each page so records from completed pages survive a later
                # provider failure, while the final successful_at remains unset.
                await self.session.commit()

                info = response.get("info", {})
                more_records = info.get("more_records", False)

                if not more_records or not items:
                    break

                page += 1

            return await self.complete_sync_record(
                sync_job.id, total_records, total_inserted, total_updated, total_failed
            )

        except Exception as exc:
            logger.error(f"Sync failed for integration {integration.id} [{resource_type}]: {exc}")
            # A failed page-level database operation must not poison the session
            # used to record the failed execution. Provider/API errors leave the
            # transaction usable; only roll back actual database exceptions.
            if isinstance(exc, SQLAlchemyError):
                await self.session.rollback()
            if fail_on_error:
                await self.fail_sync_record(
                    sync_job_id,
                    str(exc),
                    total_records,
                    total_inserted,
                    total_updated,
                    total_failed,
                )
            raise

    async def _get_sync_record(self, sync_id: uuid.UUID) -> Optional[SyncHistory]:
        result = await self.session.execute(select(SyncHistory).where(SyncHistory.id == sync_id))
        return result.scalar_one_or_none()

    async def get_history_by_integration(
        self,
        integration_id: uuid.UUID,
        limit: int = 50,
    ) -> List[SyncHistory]:
        """Fetch historical synchronization runs for an integration."""
        query = (
            select(SyncHistory)
            .where(SyncHistory.integration_id == integration_id)
            .order_by(desc(SyncHistory.started_at))
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

