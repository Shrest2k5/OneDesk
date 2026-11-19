from datetime import date, datetime, timezone
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


class BooksTransactionsService:
    MODULES = {
        "customer_payments": ("customerpayments", "customer_payments", "payment_id"),
        "vendor_payments": ("vendorpayments", "vendorpayments", "payment_id"),
        "sales_receipts": ("salesreceipts", "salesreceipts", "sales_receipt_id"),
        "credit_note_refunds": ("creditnotes/refunds", "creditnote_refunds", "creditnote_refund_id"),
        "customer_payment_refunds": (None, "payment_refunds", "payment_refund_id"),
        "vendor_payment_refunds": (None, "vendorpayment_refunds", "vendorpayment_refund_id"),
        "bank_transactions": ("banktransactions", "banktransactions", "transaction_id"),
    }
    REFUND_TYPES = {"credit_note_refunds", "customer_payment_refunds", "vendor_payment_refunds"}

    def __init__(self, session: AsyncSession, integration: Integration) -> None:
        self.session, self.integration = session, integration
        self.records = IntegrationRecordRepository(session)

    def _require_org(self) -> str:
        if not self.integration.selected_organization_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Select a Zoho Books organization first.")
        return self.integration.selected_organization_id

    @staticmethod
    def _decimal(value: Any) -> Decimal:
        try: return Decimal(str(value or 0))
        except (InvalidOperation, TypeError, ValueError): return Decimal("0")

    @staticmethod
    def _date(value: Any) -> Optional[date]:
        try: return date.fromisoformat(str(value)[:10]) if value else None
        except ValueError: return None

    @classmethod
    def _validate_range(cls, start_date: Optional[str], end_date: Optional[str]) -> tuple[Optional[date], Optional[date]]:
        lo, hi = cls._date(start_date), cls._date(end_date)
        if (start_date and lo is None) or (end_date and hi is None):
            raise HTTPException(status_code=400, detail="Dates must use YYYY-MM-DD format")
        if lo and hi and lo > hi:
            raise HTTPException(status_code=400, detail="start_date must be on or before end_date")
        return lo, hi

    @classmethod
    def normalize(cls, payload: Dict[str, Any], kind: str) -> Dict[str, Any]:
        ids = {"customer_payments": "payment_id", "vendor_payments": "payment_id", "sales_receipts": "sales_receipt_id", "credit_note_refunds": "creditnote_refund_id", "customer_payment_refunds": "payment_refund_id", "vendor_payment_refunds": "vendorpayment_refund_id", "bank_transactions": "transaction_id"}
        rid = payload.get(ids[kind]) or payload.get("id") or payload.get("receipt_id")
        if rid is None: raise ValueError(f"Zoho Books {kind} record is missing its ID")
        amount = payload.get("amount", payload.get("total", payload.get("amount_fcy", payload.get("amount_bcy"))))
        return {"id": str(rid), "transaction_id": str(rid), "transaction_type": kind,
                "number": payload.get("payment_number") or payload.get("receipt_number") or payload.get("creditnote_number") or payload.get("reference_number"),
                "customer_id": payload.get("customer_id"), "customer_name": payload.get("customer_name"),
                "vendor_id": payload.get("vendor_id"), "vendor_name": payload.get("vendor_name"),
                "transaction_date": payload.get("date") or payload.get("transaction_date"),
                "payment_mode": payload.get("payment_mode") or payload.get("refund_mode"),
                "reference_number": payload.get("reference_number"), "currency_code": payload.get("currency_code"),
                "currency_symbol": payload.get("currency_symbol"), "amount": amount,
                "subtotal": payload.get("sub_total", payload.get("subtotal")), "tax_amount": payload.get("tax_total", payload.get("tax_amount")),
                "status": payload.get("status"), "exchange_rate": payload.get("exchange_rate"),
                "paid_through_account": payload.get("paid_through_account_name"), "from_account": payload.get("from_account_name"), "to_account": payload.get("to_account_name"),
                "associated_invoices": payload.get("invoices") or payload.get("bills"), "line_items": payload.get("line_items", []), "raw_data": payload}

    async def _rows(self):
        org = self._require_org()
        q = select(IntegrationRecord).where(IntegrationRecord.user_id == self.integration.user_id, IntegrationRecord.integration_id == self.integration.id, IntegrationRecord.provider == "zoho", IntegrationRecord.product == "books", IntegrationRecord.resource_type.in_(list(self.MODULES)), IntegrationRecord.external_organization_id == org)
        return list((await self.session.execute(q.order_by(desc(IntegrationRecord.last_synced_at)))).scalars().all())

    async def _filtered_items(self, start_date: Optional[str], end_date: Optional[str], transaction_type: Optional[str], search: Optional[str]):
        lo, hi = self._validate_range(start_date, end_date)
        items = [self.normalize(r.raw_data, r.resource_type) for r in await self._rows()]
        if lo: items = [x for x in items if (self._date(x.get("transaction_date")) or date.min) >= lo]
        if hi: items = [x for x in items if (self._date(x.get("transaction_date")) or date.max) <= hi]
        if transaction_type: items = [x for x in items if x["transaction_type"] == transaction_type]
        if search:
            n = search.casefold(); items = [x for x in items if n in str(x.get("number") or "").casefold() or n in str(x.get("customer_name") or x.get("vendor_name") or "").casefold() or n in str(x.get("reference_number") or "").casefold()]
        items.sort(key=lambda x: str(x.get("transaction_date") or ""), reverse=True)
        return items

    async def list_local(self, page: int, per_page: int, start_date: Optional[str], end_date: Optional[str], transaction_type: Optional[str], search: Optional[str]) -> Dict[str, Any]:
        items = await self._filtered_items(start_date, end_date, transaction_type, search)
        start = (page - 1) * per_page
        return {"data": items[start:start + per_page], "pagination": {"page": page, "per_page": per_page, "count": len(items[start:start + per_page]), "total": len(items), "more_records": start + per_page < len(items)}}

    async def stats(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        items = await self._filtered_items(start_date, end_date, None, None)
        result: Dict[str, Any] = {"total": len(items), "counts": {}, "amounts": {}}
        for kind in self.MODULES:
            rows = [x for x in items if x["transaction_type"] == kind]
            result["counts"][kind] = len(rows)
            currencies = {}
            for row in rows:
                currency = str(row.get("currency_code") or "unknown")
                currencies[currency] = currencies.get(currency, Decimal("0")) + self._decimal(row.get("amount"))
            for currency, amount in currencies.items():
                result["amounts"][f"{kind}:{currency}"] = f"{amount:.2f}"
        return result

    async def synchronize(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> SyncHistory:
        org = self._require_org()
        self._validate_range(start_date, end_date)
        job = SyncHistory(integration_id=self.integration.id, resource_type="financial_transactions", status="in_progress", started_at=datetime.now(timezone.utc))
        self.session.add(job); await self.session.commit()
        client = ZohoBooksClient(self.integration, self.session); processed = inserted = updated = failed = 0
        try:
            for kind, (endpoint, response_key, _) in self.MODULES.items():
                if endpoint is None:
                    parent_kind = "customer_payments" if kind == "customer_payment_refunds" else "vendor_payments"
                    parent_endpoint, parent_key, _ = self.MODULES[parent_kind]
                    parent_page = 1
                    parent_ids = []
                    while True:
                        parent_response = await client.list_financial_page(org, parent_endpoint, parent_key, parent_page, 200)
                        parent_ids.extend(str(x.get("payment_id") or x.get("id")) for x in parent_response["items"] if x.get("payment_id") or x.get("id"))
                        if not parent_response["page_context"].get("has_more_page", False) or not parent_response["items"]: break
                        parent_page += 1
                    for parent_id in parent_ids:
                        page = 1
                        while True:
                            response = await client.list_financial_page(org, f'{parent_endpoint}/{parent_id}/refunds', response_key, page, 200)
                            raw_rows = response["items"]
                            rows = [item for item in raw_rows if self._in_range(item.get("date"), start_date, end_date)]
                            for item in rows:
                                processed += 1
                                try:
                                    outcome = await self.records.upsert(self.integration.user_id, self.integration.id, "zoho", "books", org, kind, item)
                                    inserted += outcome == "inserted"; updated += outcome == "updated"
                                except (ValueError, TypeError, KeyError): failed += 1
                            await self.session.commit()
                            if not response["page_context"].get("has_more_page", False) or not raw_rows: break
                            page += 1
                    continue
                page = 1
                while True:
                    use_server_dates = kind in {"vendor_payments", "sales_receipts", "bank_transactions"}
                    response = await client.list_financial_page(org, endpoint, response_key, page, 200, start_date if use_server_dates else None, end_date if use_server_dates else None)
                    raw_rows = response["items"]
                    rows = [item for item in raw_rows if self._in_range(item.get("date"), start_date, end_date)]
                    for item in rows:
                        processed += 1
                        try:
                            outcome = await self.records.upsert(self.integration.user_id, self.integration.id, "zoho", "books", org, kind, item)
                            inserted += outcome == "inserted"; updated += outcome == "updated"
                        except (ValueError, TypeError, KeyError): failed += 1
                    await self.session.commit()
                    if not response["page_context"].get("has_more_page", False) or not raw_rows: break
                    page += 1
            job.status = "completed" if not failed else "failed"; job.successful_at = datetime.now(timezone.utc) if not failed else None
            job.error_message = "Some records could not be persisted." if failed else None
        except Exception as exc:
            await self.session.rollback(); job = (await self.session.execute(select(SyncHistory).where(SyncHistory.id == job.id))).scalar_one(); job.status, job.error_message = "failed", str(exc)
        job.records_processed, job.records_inserted, job.records_updated, job.records_failed = processed, inserted, updated, failed; job.completed_at = datetime.now(timezone.utc)
        await self.session.commit(); await self.session.refresh(job); return job

    @classmethod
    def _in_range(cls, value: Any, start_date: Optional[str], end_date: Optional[str]) -> bool:
        current, lo, hi = cls._date(value), cls._date(start_date), cls._date(end_date)
        if current is None:
            return not (start_date or end_date)
        return (lo is None or current >= lo) and (hi is None or current <= hi)

    async def status(self) -> Dict[str, Any]:
        q = select(SyncHistory).where(SyncHistory.integration_id == self.integration.id, SyncHistory.resource_type == "financial_transactions").order_by(desc(SyncHistory.started_at)).limit(1)
        latest = (await self.session.execute(q)).scalar_one_or_none()
        return {"status": latest.status if latest else "never_synced", "error": latest.error_message if latest and latest.status == "failed" else None, "last_successful_sync": latest.successful_at if latest and latest.successful_at else None}
