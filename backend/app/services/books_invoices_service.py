from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.zoho.books_client import ZohoBooksClient
from app.models.integration import Integration
from app.models.integration_record import IntegrationRecord
from app.models.sync_history import SyncHistory
from app.repositories.integration_record_repository import IntegrationRecordRepository


class BooksInvoicesService:
    resource_type = "invoices"

    def __init__(self, session: AsyncSession, integration: Integration) -> None:
        self.session = session
        self.integration = integration
        self.records = IntegrationRecordRepository(session)

    @staticmethod
    def _decimal(value: Any) -> Decimal:
        try:
            return Decimal(str(value or 0))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal("0")

    @classmethod
    def normalize(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        invoice_id = payload.get("invoice_id", payload.get("id"))
        if invoice_id is None:
            raise ValueError("Zoho Books invoice is missing invoice_id")
        total = payload.get("total", payload.get("total_amount"))
        balance = payload.get("balance", payload.get("balance_due"))
        amount_paid = payload.get("amount_paid")
        if amount_paid is None and total is not None and balance is not None:
            amount_paid = str(cls._decimal(total) - cls._decimal(balance))
        return {
            "id": str(invoice_id),
            "invoice_id": str(invoice_id),
            "invoice_number": payload.get("invoice_number"),
            "reference_number": payload.get("reference_number"),
            "invoice_date": payload.get("date") or payload.get("invoice_date"),
            "due_date": payload.get("due_date"),
            "customer_id": str(payload["customer_id"]) if payload.get("customer_id") is not None else None,
            "customer_name": payload.get("customer_name"),
            "customer_email": payload.get("customer_email") or payload.get("email"),
            "status": payload.get("status"),
            "currency_code": payload.get("currency_code"),
            "currency_symbol": payload.get("currency_symbol"),
            "subtotal": payload.get("sub_total", payload.get("subtotal")),
            "tax_amount": payload.get("tax_total", payload.get("tax_amount")),
            "discount": payload.get("discount") or payload.get("discount_amount"),
            "total": total,
            "balance_due": balance,
            "amount_paid": amount_paid,
            "purchase_order_number": payload.get("purchaseorder_number") or payload.get("purchase_order_number"),
            "payment_terms": payload.get("payment_terms") or payload.get("payment_terms_label"),
            "exchange_rate": payload.get("exchange_rate"),
            "created_time": payload.get("created_time"),
            "last_modified_time": payload.get("last_modified_time"),
            "line_items": payload.get("line_items", []),
            "tax_details": payload.get("taxes") or payload.get("tax_details"),
            "notes": payload.get("notes"),
            "terms_and_conditions": payload.get("terms") or payload.get("terms_and_conditions"),
            "raw_data": payload,
        }

    async def _rows(self):
        self._require_selected_org()
        query = select(IntegrationRecord).where(
            IntegrationRecord.user_id == self.integration.user_id,
            IntegrationRecord.integration_id == self.integration.id,
            IntegrationRecord.provider == "zoho", IntegrationRecord.product == "books",
            IntegrationRecord.resource_type == self.resource_type,
            IntegrationRecord.external_organization_id == self.integration.selected_organization_id,
        )
        return list((await self.session.execute(query.order_by(desc(IntegrationRecord.last_synced_at)))).scalars().all())

    async def list_local(
        self, page: int, per_page: int, search: Optional[str] = None,
        invoice_status: Optional[str] = None, customer_id: Optional[str] = None,
        sort_by: str = "invoice_date", sort_order: str = "desc",
    ) -> Dict[str, Any]:
        items = [self.normalize(row.raw_data) for row in await self._rows()]
        if search:
            needle = search.casefold()
            items = [x for x in items if needle in str(x.get("invoice_number") or "").casefold() or needle in str(x.get("customer_name") or "").casefold()]
        if invoice_status:
            items = [x for x in items if str(x.get("status") or "").casefold() == invoice_status.casefold()]
        if customer_id:
            items = [x for x in items if x.get("customer_id") == customer_id]
        if sort_by == "total":
            items.sort(key=lambda x: self._decimal(x.get("total")), reverse=sort_order == "desc")
        else:
            items.sort(key=lambda x: str(x.get("invoice_date") or ""), reverse=sort_order == "desc")
        start = (page - 1) * per_page
        page_items = items[start:start + per_page]
        return {"data": page_items, "pagination": {"page": page, "per_page": per_page, "count": len(page_items), "total": len(items), "more_records": start + per_page < len(items)}}

    async def stats(self) -> Dict[str, Any]:
        items = [self.normalize(row.raw_data) for row in await self._rows()]
        statuses = [str(x.get("status") or "").casefold() for x in items]
        total_amount = sum((self._decimal(x.get("total")) for x in items), Decimal("0"))
        outstanding = sum((self._decimal(x.get("balance_due")) for x in items), Decimal("0"))
        return {
            "total": len(items),
            "outstanding": sum(self._decimal(x.get("balance_due")) > 0 for x in items),
            "draft": statuses.count("draft"), "sent": statuses.count("sent"),
            "overdue": statuses.count("overdue"), "paid": statuses.count("paid"),
            "partially_paid": statuses.count("partially_paid"),
            "total_amount": f"{total_amount:.2f}", "total_outstanding": f"{outstanding:.2f}",
        }

    async def synchronize(self) -> SyncHistory:
        self._require_selected_org()
        job = SyncHistory(integration_id=self.integration.id, resource_type=self.resource_type, status="in_progress", started_at=datetime.now(timezone.utc))
        self.session.add(job)
        await self.session.commit()
        client = ZohoBooksClient(self.integration, self.session)
        page, processed, inserted, updated, failed = 1, 0, 0, 0, 0
        try:
            while True:
                response = await client.list_invoices_page(self.integration.selected_organization_id, page, 200)
                items = response["invoices"]
                for item in items:
                    processed += 1
                    try:
                        outcome = await self.records.upsert(self.integration.user_id, self.integration.id, "zoho", "books", self.integration.selected_organization_id, self.resource_type, item)
                        inserted += outcome == "inserted"; updated += outcome == "updated"
                    except (ValueError, TypeError, KeyError):
                        failed += 1
                await self.session.commit()
                if not response["page_context"].get("has_more_page", False) or not items:
                    break
                page += 1
            job.status = "completed" if failed == 0 else "failed"
            job.error_message = "One or more invoices could not be persisted." if failed else None
            job.successful_at = datetime.now(timezone.utc) if failed == 0 else None
        except Exception as exc:
            await self.session.rollback()
            job = (await self.session.execute(select(SyncHistory).where(SyncHistory.id == job.id))).scalar_one()
            job.status, job.error_message = "failed", str(exc)
        job.records_processed, job.records_inserted, job.records_updated, job.records_failed = processed, inserted, updated, failed
        job.completed_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def sync_status(self) -> Dict[str, Any]:
        latest = await self.session.execute(select(SyncHistory).where(SyncHistory.integration_id == self.integration.id, SyncHistory.resource_type == self.resource_type).order_by(desc(SyncHistory.started_at)).limit(1))
        latest_job = latest.scalar_one_or_none()
        successful = await self.session.execute(select(SyncHistory).where(SyncHistory.integration_id == self.integration.id, SyncHistory.resource_type == self.resource_type, SyncHistory.successful_at.is_not(None)).order_by(desc(SyncHistory.successful_at)).limit(1))
        successful_job = successful.scalar_one_or_none()
        return {"status": latest_job.status if latest_job else "never_synced", "error": latest_job.error_message if latest_job and latest_job.status == "failed" else None, "last_successful_sync": successful_job.successful_at if successful_job else None}

    def _require_selected_org(self) -> None:
        if not self.integration.selected_organization_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Select a Zoho Books organization before accessing invoices.")
