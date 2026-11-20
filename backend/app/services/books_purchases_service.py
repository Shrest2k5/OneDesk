from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.zoho.books_client import ZohoBooksClient
from app.integrations.zoho.exceptions import ZohoAPIError
from app.models.integration import Integration
from app.models.integration_record import IntegrationRecord
from app.models.sync_history import SyncHistory
from app.repositories.integration_record_repository import IntegrationRecordRepository
from app.services.books_transactions_service import BooksTransactionsService


class BooksPurchasesService:
    PURCHASE_TYPES = ("bills", "vendor_credits")

    def __init__(self, session: AsyncSession, integration: Integration) -> None:
        self.session, self.integration = session, integration
        self.records = IntegrationRecordRepository(session)

    def _org(self) -> str:
        if not self.integration.selected_organization_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Select a Zoho Books organization first.")
        return self.integration.selected_organization_id

    @staticmethod
    def _decimal(value: Any) -> Decimal:
        try:
            return Decimal(str(value or 0))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal("0")

    @staticmethod
    def _date(value: Any) -> Optional[date]:
        try:
            return date.fromisoformat(str(value)[:10]) if value else None
        except ValueError:
            return None

    @classmethod
    def _in_range(cls, value: Any, start: Optional[str], end: Optional[str]) -> bool:
        current = cls._date(value)
        if current is None:
            return not (start or end)
        lo, hi = cls._date(start), cls._date(end)
        return (lo is None or current >= lo) and (hi is None or current <= hi)

    @classmethod
    def normalize(cls, payload: Dict[str, Any], kind: str) -> Dict[str, Any]:
        is_bill = kind == "bills"
        identifier = payload.get("bill_id" if is_bill else "vendor_credit_id") or payload.get("id")
        if identifier is None:
            raise ValueError(f"Zoho Books {kind} record is missing its ID")
        return {
            "id": str(identifier),
            "bill_id" if is_bill else "vendor_credit_id": str(identifier),
            "number": payload.get("bill_number" if is_bill else "vendor_credit_number"),
            "vendor_id": str(payload["vendor_id"]) if payload.get("vendor_id") is not None else None,
            "vendor_name": payload.get("vendor_name"),
            "date": payload.get("date"),
            "due_date": payload.get("due_date") if is_bill else None,
            "status": payload.get("status"),
            "currency_code": payload.get("currency_code"),
            "currency_symbol": payload.get("currency_symbol"),
            "reference_number": payload.get("reference_number"),
            "subtotal": payload.get("sub_total", payload.get("subtotal")),
            "tax": payload.get("tax_total", payload.get("tax")),
            "total": payload.get("total"),
            "balance": payload.get("balance"),
            "line_items": payload.get("line_items") or [],
            "applied_bill_references": payload.get("bills_credited") or payload.get("vendor_credit_bills") or [],
            "payments": payload.get("payments") or [],
            "raw_data": payload,
        }

    async def _rows(self, resource_type: str):
        org = self._org()
        q = select(IntegrationRecord).where(
            IntegrationRecord.user_id == self.integration.user_id,
            IntegrationRecord.integration_id == self.integration.id,
            IntegrationRecord.provider == "zoho", IntegrationRecord.product == "books",
            IntegrationRecord.resource_type == resource_type,
            IntegrationRecord.external_organization_id == org,
        )
        return list((await self.session.execute(q.order_by(desc(IntegrationRecord.last_synced_at)))).scalars().all())

    async def list_local(self, resource_type: str, page: int, per_page: int, start: Optional[str] = None,
                         end: Optional[str] = None, search: Optional[str] = None, record_status: Optional[str] = None):
        if resource_type == "vendor_payments":
            rows = await BooksTransactionsService(self.session, self.integration)._rows()
            items = [BooksTransactionsService.normalize(r.raw_data, r.resource_type) for r in rows if r.resource_type == "vendor_payments"]
            date_key = "transaction_date"
        else:
            items = [self.normalize(r.raw_data, resource_type) for r in await self._rows(resource_type)]
            date_key = "date"
        if start or end:
            items = [x for x in items if self._in_range(x.get(date_key), start, end)]
        if search:
            needle = search.casefold()
            items = [x for x in items if any(needle in str(x.get(k) or "").casefold() for k in ("number", "vendor_name", "reference_number", "payment_number"))]
        if record_status:
            items = [x for x in items if str(x.get("status") or "").casefold() == record_status.casefold()]
        items.sort(key=lambda x: str(x.get(date_key) or ""), reverse=True)
        offset = (page - 1) * per_page
        return {"data": items[offset:offset + per_page], "pagination": {"page": page, "per_page": per_page, "count": len(items[offset:offset + per_page]), "total": len(items), "more_records": offset + per_page < len(items)}}

    async def synchronize(self, start: Optional[str] = None, end: Optional[str] = None) -> SyncHistory:
        org = self._org()
        if start and not self._date(start) or end and not self._date(end) or (start and end and self._date(start) > self._date(end)):
            raise HTTPException(status_code=400, detail="Dates must use a valid range in YYYY-MM-DD format")
        job = SyncHistory(integration_id=self.integration.id, resource_type="purchases", status="in_progress", started_at=datetime.now(timezone.utc))
        self.session.add(job); await self.session.commit()
        job_id = job.id
        processed = inserted = updated = failed = 0
        try:
            client = ZohoBooksClient(self.integration, self.session)
            for kind, fetch in (("bills", client.list_bills_page), ("vendor_credits", client.list_vendor_credits_page)):
                page = 1
                while True:
                    response = await fetch(org, page, 200, start, end)
                    raw_items = response["items"]
                    for raw in raw_items:
                        if not self._in_range(raw.get("date"), start, end):
                            continue
                        processed += 1
                        try:
                            outcome = await self.records.upsert(self.integration.user_id, self.integration.id, "zoho", "books", org, kind, raw)
                            inserted += outcome == "inserted"; updated += outcome == "updated"
                        except (ValueError, TypeError, KeyError):
                            failed += 1
                    await self.session.commit()
                    if not response["page_context"].get("has_more_page", False) or not raw_items:
                        break
                    page += 1
            job.status = "completed" if not failed else "failed"; job.successful_at = datetime.now(timezone.utc) if not failed else None
            job.error_message = "Some records could not be persisted." if failed else None
        except Exception as exc:
            await self.session.rollback()
            # Rollback expires ORM instances under AsyncSession; use the
            # captured primary key instead of accessing job.id after rollback.
            job = (await self.session.execute(select(SyncHistory).where(SyncHistory.id == job_id))).scalar_one()
            if isinstance(exc, ZohoAPIError) and exc.status_code in {401, 403}:
                job.error_message = f"Zoho Books authorization failed (HTTP {exc.status_code}): {exc}"
            else:
                job.error_message = str(exc)
            job.status = "failed"
        job.records_processed, job.records_inserted, job.records_updated, job.records_failed = processed, inserted, updated, failed
        job.completed_at = datetime.now(timezone.utc)
        await self.session.commit(); await self.session.refresh(job)
        return job

    async def status(self) -> Dict[str, Any]:
        q = select(SyncHistory).where(SyncHistory.integration_id == self.integration.id, SyncHistory.resource_type == "purchases").order_by(desc(SyncHistory.started_at)).limit(1)
        latest = (await self.session.execute(q)).scalar_one_or_none()
        return {"sync_id": str(latest.id) if latest else None, "status": latest.status if latest else "never_synced", "error": latest.error_message if latest and latest.status == "failed" else None, "last_successful_sync": latest.successful_at if latest else None}
