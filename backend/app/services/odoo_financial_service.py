from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import Integration
from app.models.integration_record import IntegrationRecord
from app.models.sync_history import SyncHistory


class OdooFinancialService:
    """Tenant-scoped local read and statistics service for Odoo 20 accounting data."""

    def __init__(self, session: AsyncSession, integration: Integration) -> None:
        self.session = session
        self.integration = integration
        self.scope = integration.external_database or integration.api_domain or "odoo-default"

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

    async def _fetch_records(self, resource_types: List[str]) -> List[Dict[str, Any]]:
        query = select(IntegrationRecord).where(
            IntegrationRecord.user_id == self.integration.user_id,
            IntegrationRecord.integration_id == self.integration.id,
            IntegrationRecord.provider == "odoo",
            IntegrationRecord.product == "erp",
            IntegrationRecord.resource_type.in_(resource_types),
            IntegrationRecord.external_organization_id == self.scope,
        ).order_by(desc(IntegrationRecord.last_synced_at))
        rows = list((await self.session.execute(query)).scalars().all())
        return [r.raw_data for r in rows if isinstance(r.raw_data, dict)]

    # -------------------------------------------------------------------------
    # 1. Customer Invoices
    # -------------------------------------------------------------------------

    async def list_invoices(
        self,
        page: int = 1,
        per_page: int = 25,
        search: Optional[str] = None,
        status: Optional[str] = None,
        payment_state: Optional[str] = None,
        partner_id: Optional[str] = None,
        sort_by: str = "invoice_date",
        sort_order: str = "desc",
    ) -> Dict[str, Any]:
        items = await self._fetch_records(["invoices"])
        if search:
            needle = search.casefold()
            items = [
                x for x in items
                if needle in str(x.get("invoice_number") or "").casefold()
                or needle in str(x.get("reference_number") or "").casefold()
                or needle in str(x.get("customer_name") or "").casefold()
            ]
        if status:
            items = [x for x in items if str(x.get("status") or "").casefold() == status.casefold()]
        if payment_state:
            items = [x for x in items if str(x.get("payment_state") or "").casefold() == payment_state.casefold()]
        if partner_id:
            items = [x for x in items if str(x.get("customer_id") or "") == str(partner_id)]

        if sort_by == "total":
            items.sort(key=lambda x: self._decimal(x.get("total")), reverse=(sort_order == "desc"))
        else:
            items.sort(key=lambda x: str(x.get("invoice_date") or x.get("created_at") or ""), reverse=(sort_order == "desc"))

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

    async def invoice_stats(self) -> Dict[str, Any]:
        items = await self._fetch_records(["invoices"])
        total_amount = sum((self._decimal(x.get("total")) for x in items), Decimal("0"))
        total_outstanding = sum((self._decimal(x.get("balance_due")) for x in items), Decimal("0"))
        total_paid = sum((self._decimal(x.get("amount_paid")) for x in items), Decimal("0"))
        statuses = [str(x.get("status") or "").casefold() for x in items]
        payment_states = [str(x.get("payment_state") or "").casefold() for x in items]
        return {
            "total": len(items),
            "draft": statuses.count("draft"),
            "posted": statuses.count("posted"),
            "cancelled": statuses.count("cancel"),
            "paid": payment_states.count("paid"),
            "not_paid": payment_states.count("not_paid"),
            "partial": payment_states.count("partial"),
            "in_payment": payment_states.count("in_payment"),
            "total_amount": f"{total_amount:.2f}",
            "total_outstanding": f"{total_outstanding:.2f}",
            "total_paid": f"{total_paid:.2f}",
        }

    # -------------------------------------------------------------------------
    # 2. Vendor Bills
    # -------------------------------------------------------------------------

    async def list_bills(
        self,
        page: int = 1,
        per_page: int = 25,
        search: Optional[str] = None,
        status: Optional[str] = None,
        payment_state: Optional[str] = None,
        partner_id: Optional[str] = None,
        sort_by: str = "bill_date",
        sort_order: str = "desc",
    ) -> Dict[str, Any]:
        items = await self._fetch_records(["bills"])
        if search:
            needle = search.casefold()
            items = [
                x for x in items
                if needle in str(x.get("bill_number") or "").casefold()
                or needle in str(x.get("reference_number") or "").casefold()
                or needle in str(x.get("vendor_name") or "").casefold()
            ]
        if status:
            items = [x for x in items if str(x.get("status") or "").casefold() == status.casefold()]
        if payment_state:
            items = [x for x in items if str(x.get("payment_state") or "").casefold() == payment_state.casefold()]
        if partner_id:
            items = [x for x in items if str(x.get("vendor_id") or "") == str(partner_id)]

        if sort_by == "total":
            items.sort(key=lambda x: self._decimal(x.get("total")), reverse=(sort_order == "desc"))
        else:
            items.sort(key=lambda x: str(x.get("bill_date") or x.get("created_at") or ""), reverse=(sort_order == "desc"))

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

    async def bill_stats(self) -> Dict[str, Any]:
        items = await self._fetch_records(["bills"])
        total_amount = sum((self._decimal(x.get("total")) for x in items), Decimal("0"))
        total_outstanding = sum((self._decimal(x.get("balance_due")) for x in items), Decimal("0"))
        total_paid = sum((self._decimal(x.get("amount_paid")) for x in items), Decimal("0"))
        statuses = [str(x.get("status") or "").casefold() for x in items]
        payment_states = [str(x.get("payment_state") or "").casefold() for x in items]
        return {
            "total": len(items),
            "draft": statuses.count("draft"),
            "posted": statuses.count("posted"),
            "cancelled": statuses.count("cancel"),
            "paid": payment_states.count("paid"),
            "not_paid": payment_states.count("not_paid"),
            "partial": payment_states.count("partial"),
            "in_payment": payment_states.count("in_payment"),
            "total_amount": f"{total_amount:.2f}",
            "total_outstanding": f"{total_outstanding:.2f}",
            "total_paid": f"{total_paid:.2f}",
        }

    # -------------------------------------------------------------------------
    # 3. Customer & Vendor Credit Notes / Refunds
    # -------------------------------------------------------------------------

    async def list_credit_notes(
        self,
        page: int = 1,
        per_page: int = 25,
        search: Optional[str] = None,
        kind: Optional[str] = None,
        status: Optional[str] = None,
        partner_id: Optional[str] = None,
        sort_by: str = "date",
        sort_order: str = "desc",
    ) -> Dict[str, Any]:
        items = await self._fetch_records(["credit_notes"])
        if kind in {"customer", "vendor"}:
            items = [x for x in items if x.get("credit_note_type") == kind]
        if search:
            needle = search.casefold()
            items = [
                x for x in items
                if needle in str(x.get("credit_note_number") or "").casefold()
                or needle in str(x.get("reference_number") or "").casefold()
                or needle in str(x.get("partner_name") or "").casefold()
            ]
        if status:
            items = [x for x in items if str(x.get("status") or "").casefold() == status.casefold()]
        if partner_id:
            items = [x for x in items if str(x.get("partner_id") or "") == str(partner_id)]

        if sort_by == "total":
            items.sort(key=lambda x: self._decimal(x.get("total")), reverse=(sort_order == "desc"))
        else:
            items.sort(key=lambda x: str(x.get("date") or x.get("created_at") or ""), reverse=(sort_order == "desc"))

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

    async def credit_note_stats(self) -> Dict[str, Any]:
        items = await self._fetch_records(["credit_notes"])
        total_amount = sum((self._decimal(x.get("total")) for x in items), Decimal("0"))
        customer_cnt = sum(1 for x in items if x.get("credit_note_type") == "customer")
        vendor_cnt = sum(1 for x in items if x.get("credit_note_type") == "vendor")
        return {
            "total": len(items),
            "customer_credit_notes": customer_cnt,
            "vendor_credit_notes": vendor_cnt,
            "total_amount": f"{total_amount:.2f}",
        }

    # -------------------------------------------------------------------------
    # 4. Customer & Vendor Payments
    # -------------------------------------------------------------------------

    async def list_payments(
        self,
        page: int = 1,
        per_page: int = 25,
        search: Optional[str] = None,
        payment_type: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        sort_by: str = "payment_date",
        sort_order: str = "desc",
    ) -> Dict[str, Any]:
        items = await self._fetch_records(["payments"])
        if payment_type in {"inbound", "outbound"}:
            items = [x for x in items if x.get("payment_type") == payment_type]
        if search:
            needle = search.casefold()
            items = [
                x for x in items
                if needle in str(x.get("payment_number") or "").casefold()
                or needle in str(x.get("payment_reference") or "").casefold()
                or needle in str(x.get("partner_name") or "").casefold()
            ]
        if status:
            items = [x for x in items if str(x.get("status") or "").casefold() == status.casefold()]

        lo, hi = self._date(start_date), self._date(end_date)
        if lo:
            items = [x for x in items if (self._date(x.get("payment_date")) or date.min) >= lo]
        if hi:
            items = [x for x in items if (self._date(x.get("payment_date")) or date.max) <= hi]

        if sort_by == "amount":
            items.sort(key=lambda x: self._decimal(x.get("amount")), reverse=(sort_order == "desc"))
        else:
            items.sort(key=lambda x: str(x.get("payment_date") or x.get("created_at") or ""), reverse=(sort_order == "desc"))

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

    async def payment_stats(self) -> Dict[str, Any]:
        items = await self._fetch_records(["payments"])
        inbound_items = [x for x in items if x.get("payment_type") == "inbound"]
        outbound_items = [x for x in items if x.get("payment_type") == "outbound"]
        total_inbound = sum((self._decimal(x.get("amount")) for x in inbound_items), Decimal("0"))
        total_outbound = sum((self._decimal(x.get("amount")) for x in outbound_items), Decimal("0"))
        return {
            "total": len(items),
            "customer_payments": len(inbound_items),
            "vendor_payments": len(outbound_items),
            "total_inbound": f"{total_inbound:.2f}",
            "total_outbound": f"{total_outbound:.2f}",
            "reconciled": sum(1 for x in items if x.get("is_reconciled")),
        }

    # -------------------------------------------------------------------------
    # 5. Accounting Transactions & Journal Entries
    # -------------------------------------------------------------------------

    async def list_transactions(
        self,
        page: int = 1,
        per_page: int = 25,
        search: Optional[str] = None,
        transaction_type: Optional[str] = None,
        journal_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        sort_by: str = "date",
        sort_order: str = "desc",
    ) -> Dict[str, Any]:
        items = await self._fetch_records(["transactions", "journal_entries", "bank_transactions"])
        if transaction_type:
            items = [x for x in items if x.get("transaction_type") == transaction_type]
        if journal_id:
            items = [
                x for x in items
                if str(x.get("journal", {}).get("id") if isinstance(x.get("journal"), dict) else "") == str(journal_id)
            ]
        if search:
            needle = search.casefold()
            items = [
                x for x in items
                if needle in str(x.get("entry_number") or x.get("number") or "").casefold()
                or needle in str(x.get("reference") or "").casefold()
                or needle in str(x.get("partner", {}).get("name") if isinstance(x.get("partner"), dict) else "").casefold()
            ]

        lo, hi = self._date(start_date), self._date(end_date)
        if lo:
            items = [x for x in items if (self._date(x.get("date")) or date.min) >= lo]
        if hi:
            items = [x for x in items if (self._date(x.get("date")) or date.max) <= hi]

        if sort_by == "amount":
            items.sort(key=lambda x: self._decimal(x.get("total_amount") or x.get("amount")), reverse=(sort_order == "desc"))
        else:
            items.sort(key=lambda x: str(x.get("date") or x.get("created_at") or ""), reverse=(sort_order == "desc"))

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

    async def transaction_stats(self) -> Dict[str, Any]:
        items = await self._fetch_records(["transactions", "journal_entries", "bank_transactions"])
        journal_entries = [x for x in items if x.get("transaction_type") == "journal_entry"]
        bank_txs = [x for x in items if x.get("transaction_type") == "bank_transaction"]
        total_amount = sum((self._decimal(x.get("total_amount") or x.get("amount")) for x in items), Decimal("0"))
        return {
            "total": len(items),
            "journal_entries": len(journal_entries),
            "bank_transactions": len(bank_txs),
            "total_amount": f"{total_amount:.2f}",
        }

    # -------------------------------------------------------------------------
    # Sync Status Helper
    # -------------------------------------------------------------------------

    async def sync_status(self, resource_type: str) -> Dict[str, Any]:
        latest_result = await self.session.execute(
            select(SyncHistory)
            .where(SyncHistory.integration_id == self.integration.id, SyncHistory.resource_type == resource_type)
            .order_by(desc(SyncHistory.started_at)).limit(1)
        )
        latest = latest_result.scalar_one_or_none()

        successful_result = await self.session.execute(
            select(SyncHistory)
            .where(
                SyncHistory.integration_id == self.integration.id,
                SyncHistory.resource_type == resource_type,
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
