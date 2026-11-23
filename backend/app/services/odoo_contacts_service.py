from typing import Any, Dict, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import Integration
from app.models.integration_record import IntegrationRecord
from app.models.sync_history import SyncHistory


class OdooContactsService:
    """Local read model for the canonical Odoo res.partner synchronization."""

    resource_type = "contacts"

    def __init__(self, session: AsyncSession, integration: Integration) -> None:
        self.session = session
        self.integration = integration
        self.scope = integration.external_database or integration.api_domain or "odoo-default"

    async def list_local(
        self,
        page: int = 1,
        per_page: int = 25,
        kind: Optional[str] = None,
        search: Optional[str] = None,
        include_archived: bool = True,
    ) -> Dict[str, Any]:
        query = select(IntegrationRecord).where(
            IntegrationRecord.user_id == self.integration.user_id,
            IntegrationRecord.integration_id == self.integration.id,
            IntegrationRecord.provider == "odoo",
            IntegrationRecord.product == "erp",
            IntegrationRecord.resource_type == self.resource_type,
            IntegrationRecord.external_organization_id == self.scope,
        ).order_by(desc(IntegrationRecord.last_synced_at))
        rows = list((await self.session.execute(query)).scalars().all())
        items = [row.raw_data for row in rows if isinstance(row.raw_data, dict)]
        if not include_archived:
            items = [item for item in items if item.get("active", True)]
        if kind in {"customer", "vendor"}:
            items = [item for item in items if kind in (item.get("classifications") or [])]
        if search:
            needle = search.casefold()
            items = [item for item in items if any(needle in str(item.get(key) or "").casefold() for key in ("name", "display_name", "email", "phone"))]
        total = len(items)
        start = max(0, page - 1) * per_page
        page_items = items[start:start + per_page]
        return {
            "data": page_items,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "count": len(page_items),
                "total": total,
                "more_records": start + per_page < total,
            },
        }

    async def stats(self) -> Dict[str, int]:
        result = await self.list_local(page=1, per_page=1_000_000)
        items = result["data"]
        return {
            "total": result["pagination"]["total"],
            "customers": sum("customer" in (item.get("classifications") or []) for item in items),
            "vendors": sum("vendor" in (item.get("classifications") or []) for item in items),
            "companies": sum(bool(item.get("is_company")) for item in items),
            "archived": sum(item.get("active") is False for item in items),
        }

    async def sync_status(self) -> Dict[str, Any]:
        latest_result = await self.session.execute(
            select(SyncHistory)
            .where(SyncHistory.integration_id == self.integration.id, SyncHistory.resource_type == self.resource_type)
            .order_by(desc(SyncHistory.started_at)).limit(1)
        )
        latest = latest_result.scalar_one_or_none()
        successful_result = await self.session.execute(
            select(SyncHistory)
            .where(
                SyncHistory.integration_id == self.integration.id,
                SyncHistory.resource_type == self.resource_type,
                SyncHistory.status == "completed",
                SyncHistory.successful_at.is_not(None),
            )
            .order_by(desc(SyncHistory.successful_at)).limit(1)
        )
        successful = successful_result.scalar_one_or_none()
        return {
            "status": latest.status if latest else "never_synced",
            "error": latest.error_message if latest and latest.status == "failed" else None,
            "last_successful_sync": successful.successful_at if successful else None,
        }
