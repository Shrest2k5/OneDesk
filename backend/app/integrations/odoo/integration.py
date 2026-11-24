from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.integrations.base import BaseERPIntegration
from app.integrations.odoo.client import OdooClient
from app.integrations.odoo.exceptions import OdooConfigurationError, OdooIntegrationError
from app.integrations.registry import integration_registry
from app.models.integration import Integration
from app.repositories.integration_repository import IntegrationRepository


class OdooIntegration(BaseERPIntegration):
    """External Odoo 20 JSON-2 connection lifecycle and data extraction."""

    @property
    def provider_name(self) -> str:
        return "odoo"

    @property
    def product_name(self) -> str:
        return "erp"

    def generate_authorization_url(self, *args: Any, **kwargs: Any) -> Dict[str, str]:
        raise OdooConfigurationError("Odoo uses API-key connection validation, not OAuth authorization.", status_code=400)

    async def handle_oauth_callback(self, *args: Any, **kwargs: Any) -> Integration:
        raise OdooConfigurationError("Odoo does not use an OAuth callback.", status_code=400)

    async def connect(
        self,
        user_id: uuid.UUID,
        connection_name: str,
        instance_url: str,
        api_key: str,
        database: Optional[str],
        session: AsyncSession,
        integration_id: Optional[uuid.UUID] = None,
    ) -> Integration:
        if not connection_name or not connection_name.strip():
            raise OdooConfigurationError("An Odoo connection name is required.", status_code=422)
        client = OdooClient(instance_url, api_key, database)
        context = await client.get_user_context()
        if not isinstance(context, dict):
            raise OdooIntegrationError("Odoo returned no authenticated user context.", status_code=502)

        repository = IntegrationRepository(session)
        if integration_id:
            integration = await repository.get_by_user_and_id(user_id, integration_id)
            if not integration or integration.provider != self.provider_name:
                raise OdooConfigurationError("The requested Odoo connection does not belong to this user.", status_code=404)
            integration.connection_name = connection_name.strip()
            integration.api_domain = client.base_url
            integration.external_database = database.strip() if database else None
            integration.access_token = api_key.strip()
            integration.refresh_token = None
            integration.token_expires_at = None
            integration.status = "active"
            await session.flush()
        else:
            integration = await repository.create_or_update(
                user_id=user_id,
                provider=self.provider_name,
                product=self.product_name,
                connection_name=connection_name.strip(),
                access_token=api_key.strip(),
                api_domain=client.base_url,
                external_database=database.strip() if database else None,
                status="active",
            )
        await session.commit()
        await session.refresh(integration)
        logger.info("Connected Odoo integration: id=%s user_id=%s", integration.id, user_id)
        return integration

    async def refresh_access_token(self, integration: Integration, session: AsyncSession) -> Integration:
        """Odoo API keys do not have a refresh-token flow; reconnect to replace one."""
        return integration

    async def get_connection_status(self, integration: Integration, session: AsyncSession) -> Dict[str, Any]:
        if not integration.access_token or not integration.api_domain:
            return {"status": "error", "provider": self.provider_name, "product": self.product_name, "connection_name": integration.connection_name, "error": "Odoo connection credentials are missing."}
        try:
            context = await OdooClient(integration.api_domain, integration.access_token, integration.external_database).get_user_context()
            return {
                "status": "connected",
                "provider": self.provider_name,
                "product": self.product_name,
                "connection_name": integration.connection_name,
                "api_domain": integration.api_domain,
                "token_status": "valid",
                "user_id": context.get("uid") if isinstance(context, dict) else None,
            }
        except OdooIntegrationError as exc:
            return {
                "status": "error",
                "provider": self.provider_name,
                "product": self.product_name,
                "connection_name": integration.connection_name,
                "api_domain": integration.api_domain,
                "token_status": "invalid" if exc.status_code in (401, 403) else "unverified",
                "error": str(exc),
            }

    @staticmethod
    def _format_write_date(val: Any) -> Optional[str]:
        if not val:
            return None
        if isinstance(val, (datetime, date)):
            return val.strftime("%Y-%m-%d %H:%M:%S")
        s = str(val).replace("T", " ").replace("Z", "")
        return s.split(".")[0]

    async def fetch_records(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        integration: Integration = kwargs["integration"]
        resource_type = kwargs.get("resource_type", "contacts")
        page = max(1, int(kwargs.get("page", 1)))
        per_page = max(1, min(int(kwargs.get("per_page", 200)), 500))
        modified_since = kwargs.get("modified_since")
        since_str = self._format_write_date(modified_since)

        supported_resources = {
            "contacts", "customers", "vendors",
            "invoices", "bills", "credit_notes",
            "payments", "transactions", "journal_entries",
            "bank_transactions",
        }
        if resource_type not in supported_resources:
            raise ValueError(f"Odoo synchronization does not support resource '{resource_type}'")

        client = OdooClient(integration.api_domain or "", integration.access_token or "", integration.external_database)
        offset = (page - 1) * per_page

        # 1. Partner Master Data (Contacts, Customers, Vendors)
        if resource_type in {"contacts", "customers", "vendors"}:
            domain = []
            if resource_type == "customers":
                domain = [["customer_rank", ">", 0]]
            elif resource_type == "vendors":
                domain = [["supplier_rank", ">", 0]]
            if since_str:
                domain.append(["write_date", ">=", since_str])
            fields = [
                "id", "name", "display_name", "active", "is_company", "type", "parent_id",
                "commercial_partner_id", "email", "phone", "mobile", "street", "street2",
                "city", "zip", "state_id", "country_id", "customer_rank", "supplier_rank",
                "company_type", "comment", "create_date", "write_date",
            ]
            items = await client.search_read_partners(domain, offset, per_page, fields)
            normalized = [self.normalize_partner(item) for item in items]
            return {"data": normalized, "info": {"more_records": len(items) == per_page}}

        # Move fields shared across invoices, bills, credit notes, and journal entries
        move_fields = [
            "id", "name", "ref", "state", "payment_state", "move_type", "date",
            "invoice_date", "invoice_date_due", "partner_id", "commercial_partner_id",
            "currency_id", "company_id", "journal_id", "amount_untaxed", "amount_tax",
            "amount_total", "amount_residual", "amount_untaxed_signed", "amount_tax_signed",
            "amount_total_signed", "amount_residual_signed", "invoice_user_id",
            "invoice_payment_term_id", "invoice_origin", "reversed_entry_id",
            "invoice_line_ids", "line_ids", "create_date", "write_date",
        ]

        # 2. Customer Invoices
        if resource_type == "invoices":
            domain = [["move_type", "=", "out_invoice"]]
            if since_str:
                domain.append(["write_date", ">=", since_str])
            items = await client.search_read("account.move", domain, offset, per_page, move_fields, order="invoice_date desc, id desc")
            lines_by_move = await self._fetch_move_lines(client, items, move_type="invoice")
            normalized = [self.normalize_invoice(item, lines_by_move.get(item["id"], [])) for item in items]
            return {"data": normalized, "info": {"more_records": len(items) == per_page}}

        # 3. Vendor Bills
        if resource_type == "bills":
            domain = [["move_type", "=", "in_invoice"]]
            if since_str:
                domain.append(["write_date", ">=", since_str])
            items = await client.search_read("account.move", domain, offset, per_page, move_fields, order="invoice_date desc, id desc")
            lines_by_move = await self._fetch_move_lines(client, items, move_type="bill")
            normalized = [self.normalize_bill(item, lines_by_move.get(item["id"], [])) for item in items]
            return {"data": normalized, "info": {"more_records": len(items) == per_page}}

        # 4. Customer & Vendor Credit Notes / Refunds
        if resource_type == "credit_notes":
            domain = [["move_type", "in", ["out_refund", "in_refund"]]]
            if since_str:
                domain.append(["write_date", ">=", since_str])
            items = await client.search_read("account.move", domain, offset, per_page, move_fields, order="invoice_date desc, id desc")
            lines_by_move = await self._fetch_move_lines(client, items, move_type="credit_note")
            normalized = [self.normalize_credit_note(item, lines_by_move.get(item["id"], [])) for item in items]
            return {"data": normalized, "info": {"more_records": len(items) == per_page}}

        # 5. Customer & Vendor Payments
        if resource_type == "payments":
            domain = []
            if since_str:
                domain.append(["write_date", ">=", since_str])
            payment_fields = [
                "id", "name", "payment_type", "partner_type", "partner_id", "amount",
                "currency_id", "date", "state", "payment_reference", "journal_id",
                "is_reconciled", "is_matched", "move_id", "reconciled_invoice_ids",
                "reconciled_bill_ids", "create_date", "write_date",
            ]
            items = await client.search_read("account.payment", domain, offset, per_page, payment_fields, order="date desc, id desc")
            normalized = [self.normalize_payment(item) for item in items]
            return {"data": normalized, "info": {"more_records": len(items) == per_page}}

        # 6. Accounting Transactions / Journal Entries
        if resource_type in {"transactions", "journal_entries"}:
            domain = [["move_type", "=", "entry"]]
            if since_str:
                domain.append(["write_date", ">=", since_str])
            items = await client.search_read("account.move", domain, offset, per_page, move_fields, order="date desc, id desc")
            lines_by_move = await self._fetch_move_lines(client, items, move_type="entry")
            normalized = [self.normalize_journal_entry(item, lines_by_move.get(item["id"], [])) for item in items]
            return {"data": normalized, "info": {"more_records": len(items) == per_page}}

        # 7. Bank Transactions
        if resource_type == "bank_transactions":
            domain = []
            if since_str:
                domain.append(["write_date", ">=", since_str])
            bank_fields = [
                "id", "name", "payment_ref", "date", "amount", "amount_currency",
                "currency_id", "partner_id", "journal_id", "statement_id",
                "is_reconciled", "move_id", "create_date", "write_date",
            ]
            try:
                items = await client.search_read("account.bank.statement.line", domain, offset, per_page, bank_fields, order="date desc, id desc")
            except Exception:
                # If account.bank.statement.line is not present, return empty
                items = []
            normalized = [self.normalize_bank_transaction(item) for item in items]
            return {"data": normalized, "info": {"more_records": len(items) == per_page}}

        return {"data": [], "info": {"more_records": False}}

    @classmethod
    async def _fetch_move_lines(cls, client: OdooClient, items: List[Dict[str, Any]], move_type: str = "invoice") -> Dict[int, List[Dict[str, Any]]]:
        move_ids = [item["id"] for item in items if isinstance(item, dict) and "id" in item]
        if not move_ids:
            return {}
        try:
            if move_type in {"invoice", "bill", "credit_note"}:
                fields = [
                    "id", "move_id", "name", "product_id", "quantity", "price_unit",
                    "discount", "price_subtotal", "price_total", "tax_ids", "account_id",
                    "currency_id", "display_type",
                ]
                domain = [["move_id", "in", move_ids], ["display_type", "in", [False, "product"]]]
            else:
                fields = [
                    "id", "move_id", "account_id", "partner_id", "name", "debit", "credit",
                    "balance", "amount_currency", "currency_id", "date", "reconciled",
                    "matching_number",
                ]
                domain = [["move_id", "in", move_ids]]
            lines = await client.search_read(
                "account.move.line",
                domain=domain,
                offset=0,
                limit=max(500, len(move_ids) * 50),
                fields=fields,
            )
            grouped: Dict[int, List[Dict[str, Any]]] = {}
            for line in lines:
                mid = line.get("move_id")
                if isinstance(mid, (list, tuple)) and mid:
                    grouped.setdefault(mid[0], []).append(line)
            return grouped
        except Exception as exc:
            logger.warning("Could not fetch lines for Odoo moves: %s", exc)
            return {}

    @staticmethod
    def _many2one(value: Any) -> Optional[Dict[str, Any]]:
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return {"id": value[0], "name": value[1]}
        return None

    @staticmethod
    def _decimal(value: Any) -> Decimal:
        try:
            return Decimal(str(value or 0))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal("0")

    @classmethod
    def normalize_partner(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        partner_id = payload.get("id")
        if partner_id is None:
            raise ValueError("Odoo partner is missing id")
        customer_rank = payload.get("customer_rank") or 0
        supplier_rank = payload.get("supplier_rank") or 0
        try:
            customer_rank = int(customer_rank)
        except (TypeError, ValueError):
            customer_rank = 0
        try:
            supplier_rank = int(supplier_rank)
        except (TypeError, ValueError):
            supplier_rank = 0
        classifications = []
        if customer_rank > 0:
            classifications.append("customer")
        if supplier_rank > 0:
            classifications.append("vendor")
        return {
            "id": str(partner_id),
            "partner_id": str(partner_id),
            "name": payload.get("name") or payload.get("display_name"),
            "display_name": payload.get("display_name") or payload.get("name"),
            "active": payload.get("active", True),
            "is_company": payload.get("is_company", False),
            "company_type": payload.get("company_type"),
            "contact_type": payload.get("type"),
            "parent": cls._many2one(payload.get("parent_id")),
            "commercial_partner": cls._many2one(payload.get("commercial_partner_id")),
            "email": payload.get("email"),
            "phone": payload.get("phone"),
            "mobile": payload.get("mobile"),
            "street": payload.get("street"),
            "street2": payload.get("street2"),
            "city": payload.get("city"),
            "zip": payload.get("zip"),
            "state": cls._many2one(payload.get("state_id")),
            "country": cls._many2one(payload.get("country_id")),
            "customer_rank": customer_rank,
            "supplier_rank": supplier_rank,
            "classifications": classifications,
            "created_at": payload.get("create_date"),
            "updated_at": payload.get("write_date"),
            "raw_data": payload,
        }

    @classmethod
    def normalize_line_item(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        line_id = payload.get("id")
        product = cls._many2one(payload.get("product_id"))
        return {
            "id": str(line_id) if line_id is not None else None,
            "line_id": str(line_id) if line_id is not None else None,
            "product_id": str(product["id"]) if product else None,
            "product_name": product["name"] if product else (payload.get("name") or "Item"),
            "description": payload.get("name"),
            "quantity": str(cls._decimal(payload.get("quantity"))),
            "price_unit": str(cls._decimal(payload.get("price_unit"))),
            "discount": str(cls._decimal(payload.get("discount"))),
            "price_subtotal": str(cls._decimal(payload.get("price_subtotal"))),
            "price_total": str(cls._decimal(payload.get("price_total"))),
            "tax_ids": payload.get("tax_ids") or [],
            "account": cls._many2one(payload.get("account_id")),
            "raw_data": payload,
        }

    @classmethod
    def normalize_invoice(cls, payload: Dict[str, Any], lines: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        move_id = payload.get("id")
        if move_id is None:
            raise ValueError("Odoo invoice move is missing id")
        partner = cls._many2one(payload.get("partner_id"))
        currency = cls._many2one(payload.get("currency_id"))
        journal = cls._many2one(payload.get("journal_id"))
        company = cls._many2one(payload.get("company_id"))
        commercial = cls._many2one(payload.get("commercial_partner_id"))
        salesperson = cls._many2one(payload.get("invoice_user_id"))
        payment_terms = cls._many2one(payload.get("invoice_payment_term_id"))

        amount_total = cls._decimal(payload.get("amount_total"))
        amount_residual = cls._decimal(payload.get("amount_residual"))
        amount_paid = amount_total - amount_residual

        normalized_lines = [cls.normalize_line_item(l) for l in (lines or [])]

        return {
            "id": str(move_id),
            "invoice_id": str(move_id),
            "invoice_number": payload.get("name") or f"INV-{move_id}",
            "reference_number": payload.get("ref"),
            "invoice_date": payload.get("invoice_date") or payload.get("date"),
            "due_date": payload.get("invoice_date_due"),
            "customer_id": str(partner["id"]) if partner else None,
            "customer_name": partner["name"] if partner else None,
            "customer": partner,
            "commercial_partner": commercial,
            "journal": journal,
            "company": company,
            "salesperson": salesperson,
            "payment_terms": payment_terms,
            "source_document": payload.get("invoice_origin"),
            "status": payload.get("state") or "draft",
            "payment_state": payload.get("payment_state") or "not_paid",
            "currency_code": currency["name"] if currency else "USD",
            "currency_id": currency["id"] if currency else None,
            "subtotal": f"{cls._decimal(payload.get('amount_untaxed')):.2f}",
            "tax_amount": f"{cls._decimal(payload.get('amount_tax')):.2f}",
            "total": f"{amount_total:.2f}",
            "balance_due": f"{amount_residual:.2f}",
            "amount_paid": f"{amount_paid:.2f}",
            "line_items": normalized_lines,
            "move_type": payload.get("move_type", "out_invoice"),
            "created_at": payload.get("create_date"),
            "updated_at": payload.get("write_date"),
            "raw_data": payload,
        }

    @classmethod
    def normalize_bill(cls, payload: Dict[str, Any], lines: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        move_id = payload.get("id")
        if move_id is None:
            raise ValueError("Odoo bill move is missing id")
        partner = cls._many2one(payload.get("partner_id"))
        currency = cls._many2one(payload.get("currency_id"))
        journal = cls._many2one(payload.get("journal_id"))
        company = cls._many2one(payload.get("company_id"))
        commercial = cls._many2one(payload.get("commercial_partner_id"))
        payment_terms = cls._many2one(payload.get("invoice_payment_term_id"))

        amount_total = cls._decimal(payload.get("amount_total"))
        amount_residual = cls._decimal(payload.get("amount_residual"))
        amount_paid = amount_total - amount_residual

        normalized_lines = [cls.normalize_line_item(l) for l in (lines or [])]

        return {
            "id": str(move_id),
            "bill_id": str(move_id),
            "bill_number": payload.get("name") or f"BILL-{move_id}",
            "reference_number": payload.get("ref"),
            "bill_date": payload.get("invoice_date") or payload.get("date"),
            "due_date": payload.get("invoice_date_due"),
            "vendor_id": str(partner["id"]) if partner else None,
            "vendor_name": partner["name"] if partner else None,
            "vendor": partner,
            "commercial_partner": commercial,
            "journal": journal,
            "company": company,
            "payment_terms": payment_terms,
            "source_document": payload.get("invoice_origin"),
            "status": payload.get("state") or "draft",
            "payment_state": payload.get("payment_state") or "not_paid",
            "currency_code": currency["name"] if currency else "USD",
            "currency_id": currency["id"] if currency else None,
            "subtotal": f"{cls._decimal(payload.get('amount_untaxed')):.2f}",
            "tax_amount": f"{cls._decimal(payload.get('amount_tax')):.2f}",
            "total": f"{amount_total:.2f}",
            "balance_due": f"{amount_residual:.2f}",
            "amount_paid": f"{amount_paid:.2f}",
            "line_items": normalized_lines,
            "move_type": payload.get("move_type", "in_invoice"),
            "created_at": payload.get("create_date"),
            "updated_at": payload.get("write_date"),
            "raw_data": payload,
        }

    @classmethod
    def normalize_credit_note(cls, payload: Dict[str, Any], lines: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        move_id = payload.get("id")
        if move_id is None:
            raise ValueError("Odoo credit note move is missing id")
        partner = cls._many2one(payload.get("partner_id"))
        currency = cls._many2one(payload.get("currency_id"))
        journal = cls._many2one(payload.get("journal_id"))
        company = cls._many2one(payload.get("company_id"))
        reversed_entry = cls._many2one(payload.get("reversed_entry_id"))

        amount_total = cls._decimal(payload.get("amount_total"))
        amount_residual = cls._decimal(payload.get("amount_residual"))

        normalized_lines = [cls.normalize_line_item(l) for l in (lines or [])]
        move_type = payload.get("move_type", "out_refund")
        credit_note_type = "customer" if move_type == "out_refund" else "vendor"

        return {
            "id": str(move_id),
            "credit_note_id": str(move_id),
            "credit_note_number": payload.get("name") or f"CN-{move_id}",
            "reference_number": payload.get("ref"),
            "credit_note_type": credit_note_type,
            "move_type": move_type,
            "date": payload.get("invoice_date") or payload.get("date"),
            "partner_id": str(partner["id"]) if partner else None,
            "partner_name": partner["name"] if partner else None,
            "partner": partner,
            "reversed_entry": reversed_entry,
            "journal": journal,
            "company": company,
            "source_document": payload.get("invoice_origin"),
            "status": payload.get("state") or "draft",
            "payment_state": payload.get("payment_state") or "not_paid",
            "currency_code": currency["name"] if currency else "USD",
            "currency_id": currency["id"] if currency else None,
            "subtotal": f"{cls._decimal(payload.get('amount_untaxed')):.2f}",
            "tax_amount": f"{cls._decimal(payload.get('amount_tax')):.2f}",
            "total": f"{amount_total:.2f}",
            "balance_due": f"{amount_residual:.2f}",
            "line_items": normalized_lines,
            "created_at": payload.get("create_date"),
            "updated_at": payload.get("write_date"),
            "raw_data": payload,
        }

    @classmethod
    def normalize_payment(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        payment_id = payload.get("id")
        if payment_id is None:
            raise ValueError("Odoo payment is missing id")
        partner = cls._many2one(payload.get("partner_id"))
        currency = cls._many2one(payload.get("currency_id"))
        journal = cls._many2one(payload.get("journal_id"))
        move = cls._many2one(payload.get("move_id"))

        reconciled_invoices = payload.get("reconciled_invoice_ids") or []
        reconciled_bills = payload.get("reconciled_bill_ids") or []

        payment_type = payload.get("payment_type") or ("inbound" if payload.get("partner_type") == "customer" else "outbound")
        amount = cls._decimal(payload.get("amount"))

        return {
            "id": str(payment_id),
            "payment_id": str(payment_id),
            "payment_number": payload.get("name") or f"PAY-{payment_id}",
            "payment_type": payment_type,
            "partner_type": payload.get("partner_type") or ("customer" if payment_type == "inbound" else "supplier"),
            "partner_id": str(partner["id"]) if partner else None,
            "partner_name": partner["name"] if partner else None,
            "partner": partner,
            "amount": f"{amount:.2f}",
            "currency_code": currency["name"] if currency else "USD",
            "currency_id": currency["id"] if currency else None,
            "payment_date": payload.get("date"),
            "status": payload.get("state") or "draft",
            "payment_reference": payload.get("payment_reference") or payload.get("ref"),
            "journal": journal,
            "is_reconciled": bool(payload.get("is_reconciled") or payload.get("is_matched")),
            "move": move,
            "reconciled_invoice_ids": reconciled_invoices,
            "reconciled_bill_ids": reconciled_bills,
            "created_at": payload.get("create_date"),
            "updated_at": payload.get("write_date"),
            "raw_data": payload,
        }

    @classmethod
    def normalize_journal_entry(cls, payload: Dict[str, Any], lines: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        move_id = payload.get("id")
        if move_id is None:
            raise ValueError("Odoo journal move is missing id")
        journal = cls._many2one(payload.get("journal_id"))
        company = cls._many2one(payload.get("company_id"))
        currency = cls._many2one(payload.get("currency_id"))

        normalized_lines = []
        for line in (lines or []):
            line_id = line.get("id")
            account = cls._many2one(line.get("account_id"))
            lpartner = cls._many2one(line.get("partner_id"))
            lcurrency = cls._many2one(line.get("currency_id"))
            normalized_lines.append({
                "id": str(line_id) if line_id is not None else None,
                "line_id": str(line_id) if line_id is not None else None,
                "account": account,
                "partner": lpartner,
                "label": line.get("name"),
                "debit": f"{cls._decimal(line.get('debit')):.2f}",
                "credit": f"{cls._decimal(line.get('credit')):.2f}",
                "balance": f"{cls._decimal(line.get('balance')):.2f}",
                "amount_currency": f"{cls._decimal(line.get('amount_currency')):.2f}",
                "currency": lcurrency,
                "date": line.get("date"),
                "reconciled": bool(line.get("reconciled")),
                "matching_number": line.get("matching_number"),
                "raw_data": line,
            })

        amount_total = cls._decimal(payload.get("amount_total"))

        return {
            "id": str(move_id),
            "transaction_id": str(move_id),
            "entry_number": payload.get("name") or f"ENTRY-{move_id}",
            "reference": payload.get("ref"),
            "date": payload.get("date"),
            "journal": journal,
            "company": company,
            "status": payload.get("state") or "draft",
            "total_amount": f"{amount_total:.2f}",
            "currency_code": currency["name"] if currency else "USD",
            "currency_id": currency["id"] if currency else None,
            "move_type": payload.get("move_type", "entry"),
            "transaction_type": "journal_entry",
            "lines": normalized_lines,
            "created_at": payload.get("create_date"),
            "updated_at": payload.get("write_date"),
            "raw_data": payload,
        }

    @classmethod
    def normalize_bank_transaction(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        line_id = payload.get("id")
        if line_id is None:
            raise ValueError("Odoo bank statement line is missing id")
        partner = cls._many2one(payload.get("partner_id"))
        currency = cls._many2one(payload.get("currency_id"))
        journal = cls._many2one(payload.get("journal_id"))
        statement = cls._many2one(payload.get("statement_id"))
        move = cls._many2one(payload.get("move_id"))

        amount = cls._decimal(payload.get("amount"))

        return {
            "id": str(line_id),
            "transaction_id": str(line_id),
            "transaction_type": "bank_transaction",
            "number": payload.get("payment_ref") or payload.get("name") or f"BANK-{line_id}",
            "reference": payload.get("payment_ref"),
            "date": payload.get("date"),
            "amount": f"{amount:.2f}",
            "currency_code": currency["name"] if currency else "USD",
            "currency_id": currency["id"] if currency else None,
            "partner": partner,
            "journal": journal,
            "statement": statement,
            "is_reconciled": bool(payload.get("is_reconciled")),
            "move": move,
            "created_at": payload.get("create_date"),
            "updated_at": payload.get("write_date"),
            "raw_data": payload,
        }

    async def get_record(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        raise NotImplementedError("Single record retrieval via get_record is not implemented for Odoo.")


odoo_integration = OdooIntegration()
integration_registry.register(odoo_integration)
