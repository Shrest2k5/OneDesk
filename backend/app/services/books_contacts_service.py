from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.zoho.books_client import ZohoBooksClient
from app.models.integration import Integration
from app.models.integration_record import IntegrationRecord
from app.models.sync_history import SyncHistory
from app.repositories.integration_record_repository import IntegrationRecordRepository


class BooksContactsService:
    resource_type = "contacts"

    def __init__(self, session: AsyncSession, integration: Integration) -> None:
        self.session = session
        self.integration = integration
        self.records = IntegrationRecordRepository(session)

    @staticmethod
    def _types(payload: Dict[str, Any]) -> List[str]:
        value = payload.get("contact_type") or payload.get("contact_type_formatted")
        values = value if isinstance(value, list) else [value]
        result = {part.strip().lower() for item in values if item for part in str(item).split(",") if part.strip()}
        if payload.get("is_customer") is True:
            result.add("customer")
        if payload.get("is_vendor") is True:
            result.add("vendor")
        return sorted(item for item in result if item in {"customer", "vendor"})

    @classmethod
    def normalize(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        contact_id = payload.get("contact_id", payload.get("id"))
        if contact_id is None:
            raise ValueError("Zoho Books contact is missing contact_id")
        types = cls._types(payload)
        billing = payload.get("billing_address") if isinstance(payload.get("billing_address"), dict) else {}
        return {
            "id": str(contact_id),
            "contact_id": str(contact_id),
            "contact_name": payload.get("contact_name") or payload.get("name"),
            "company_name": payload.get("company_name"),
            "contact_type": types[0] if len(types) == 1 else (types or None),
            "contact_types": types,
            "email": payload.get("email"),
            "phone": payload.get("phone") or billing.get("phone"),
            "currency_code": payload.get("currency_code"),
            "currency_symbol": payload.get("currency_symbol"),
            "created_time": payload.get("created_time"),
            "last_modified_time": payload.get("last_modified_time"),
            "raw_data": payload,
        }

    async def list_local(
        self, page: int, per_page: int, contact_type: Optional[str] = None, search: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._require_selected_org()
        query = select(IntegrationRecord).where(
            IntegrationRecord.user_id == self.integration.user_id,
            IntegrationRecord.integration_id == self.integration.id,
            IntegrationRecord.provider == "zoho", IntegrationRecord.product == "books",
            IntegrationRecord.resource_type == self.resource_type,
            IntegrationRecord.external_organization_id == self.integration.selected_organization_id,
        )
        rows = (await self.session.execute(query.order_by(desc(IntegrationRecord.last_synced_at)))).scalars().all()
        normalized = [self.normalize(row.raw_data) for row in rows]
        if contact_type:
            normalized = [item for item in normalized if contact_type.lower() in item["contact_types"]]
        if search:
            needle = search.casefold()
            normalized = [item for item in normalized if any(needle in str(item.get(key) or "").casefold() for key in ("contact_name", "company_name", "email"))]
        start = (page - 1) * per_page
        page_items = normalized[start:start + per_page]
        return {"data": page_items, "pagination": {"page": page, "per_page": per_page, "count": len(page_items), "total": len(normalized), "more_records": start + per_page < len(normalized)}}

    async def stats(self) -> Dict[str, Any]:
        result = await self.list_local(1, 1_000_000)
        items = result["data"] if result["pagination"]["total"] <= 1_000_000 else []
        return {"total": result["pagination"]["total"], "customers": sum("customer" in x["contact_types"] for x in items), "vendors": sum("vendor" in x["contact_types"] for x in items)}

    async def synchronize(self) -> SyncHistory:
        self._require_selected_org()
        job = SyncHistory(integration_id=self.integration.id, resource_type=self.resource_type, status="in_progress", started_at=datetime.now(timezone.utc))
        self.session.add(job)
        await self.session.commit()
        client = ZohoBooksClient(self.integration, self.session)
        page, processed, inserted, updated, failed = 1, 0, 0, 0, 0
        try:
            while True:
                response = await client.list_contacts_page(self.integration.selected_organization_id, page, 200)
                items = response["contacts"]
                for item in items:
                    processed += 1
                    try:
                        outcome = await self.records.upsert(
                            self.integration.user_id, self.integration.id, "zoho", "books",
                            self.integration.selected_organization_id, self.resource_type, item,
                        )
                        inserted += outcome == "inserted"
                        updated += outcome == "updated"
                    except (ValueError, TypeError, KeyError):
                        failed += 1
                await self.session.commit()
                context = response.get("page_context", {})
                if not context.get("has_more_page", False) or not items:
                    break
                page += 1
            job.status = "completed" if failed == 0 else "failed"
            job.records_processed, job.records_inserted, job.records_updated, job.records_failed = processed, inserted, updated, failed
            job.completed_at = datetime.now(timezone.utc)
            job.successful_at = job.completed_at if failed == 0 else None
            if failed:
                job.error_message = "One or more contacts could not be persisted."
        except Exception as exc:
            await self.session.rollback()
            job = (await self.session.execute(select(SyncHistory).where(SyncHistory.id == job.id))).scalar_one()
            job.status, job.error_message, job.completed_at = "failed", str(exc), datetime.now(timezone.utc)
            job.records_processed, job.records_inserted, job.records_updated, job.records_failed = processed, inserted, updated, failed
        await self.session.commit()
        await self.session.refresh(job)
        return job

    def _require_selected_org(self) -> None:
        if not self.integration.selected_organization_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Select a Zoho Books organization before accessing contacts.")

    async def status(self) -> Dict[str, Any]:
        result = await self.session.execute(select(SyncHistory).where(SyncHistory.integration_id == self.integration.id, SyncHistory.resource_type == self.resource_type).order_by(desc(SyncHistory.started_at)).limit(1))
        latest = result.scalar_one_or_none()
        successful = await self.session.execute(select(SyncHistory).where(SyncHistory.integration_id == self.integration.id, SyncHistory.resource_type == self.resource_type, SyncHistory.status == "completed", SyncHistory.successful_at.is_not(None)).order_by(desc(SyncHistory.successful_at)).limit(1))
        last_success = successful.scalar_one_or_none()
        return {"status": latest.status if latest else "never_synced", "error": latest.error_message if latest and latest.status == "failed" else None, "last_successful_sync": last_success.successful_at if last_success else None}
