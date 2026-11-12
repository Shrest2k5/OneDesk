import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.integrations.registry import integration_registry
from app.models.integration import Integration
from app.models.sync_history import SyncHistory
from app.repositories.integration_repository import IntegrationRepository


class SyncService:
    """
    Core synchronization service managing on-demand and background sync jobs,
    incremental delta synchronization, error capture, and audit history.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.integration_repo = IntegrationRepository(session)

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
    ) -> SyncHistory:
        """Mark a sync job as completed with total records count."""
        query = select(SyncHistory).where(SyncHistory.id == sync_id)
        result = await self.session.execute(query)
        sync_job = result.scalar_one()

        sync_job.status = "completed"
        sync_job.records_processed = records_count
        sync_job.completed_at = datetime.now(timezone.utc)

        await self.session.commit()
        await self.session.refresh(sync_job)
        return sync_job

    async def fail_sync_record(
        self,
        sync_id: uuid.UUID,
        error_message: str,
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

        await self.session.commit()
        await self.session.refresh(sync_job)
        return sync_job

    async def sync_resource(
        self,
        integration: Integration,
        resource_type: str,
        incremental: bool = True,
    ) -> SyncHistory:
        """
        Execute full or incremental synchronization of an ERP resource type
        (contacts, leads, deals, accounts) across all available pages.
        """
        provider = integration_registry.get(integration.provider)
        if not provider:
            raise ValueError(f"Unsupported ERP provider '{integration.provider}'")

        # Determine delta sync timestamp if incremental
        modified_since: Optional[str] = None
        if incremental:
            last_sync = await self.get_last_successful_sync(integration.id, resource_type)
            if last_sync and last_sync.completed_at:
                modified_since = last_sync.completed_at.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Create audit job
        sync_job = await self.start_sync_record(integration.id, resource_type)
        total_records = 0
        page = 1
        per_page = 200

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

                info = response.get("info", {})
                more_records = info.get("more_records", False)

                if not more_records or not items:
                    break

                page += 1

            return await self.complete_sync_record(sync_job.id, total_records)

        except Exception as exc:
            logger.error(f"Sync failed for integration {integration.id} [{resource_type}]: {exc}")
            await self.fail_sync_record(sync_job.id, str(exc))
            raise

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
