from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.odoo.client import OdooClient
from app.integrations.odoo.integration import OdooIntegration, odoo_integration
from app.models.integration import Integration
from app.models.integration_record import IntegrationRecord
from app.models.user import User
from app.services.odoo_financial_service import OdooFinancialService
from app.services.sync_service import SyncService


# ---------------------------------------------------------------------------
# Test Payloads
# ---------------------------------------------------------------------------

def invoice_payload(move_id: int, move_type: str = "out_invoice", state: str = "posted", payment_state: str = "not_paid"):
    return {
        "id": move_id,
        "name": f"INV/2026/{move_id:04d}",
        "ref": f"REF-{move_id}",
        "move_type": move_type,
        "state": state,
        "payment_state": payment_state,
        "partner_id": [10, "Acme Customer"],
        "invoice_date": "2026-03-15",
        "invoice_date_due": "2026-04-15",
        "currency_id": [1, "USD"],
        "amount_untaxed": 1000.0,
        "amount_tax": 100.0,
        "amount_total": 1100.0,
        "amount_residual": 500.0,
        "write_date": "2026-03-15 10:00:00",
    }


def bill_payload(move_id: int, state: str = "posted", payment_state: str = "paid"):
    return {
        "id": move_id,
        "name": f"BILL/2026/{move_id:04d}",
        "ref": f"VENDOR-REF-{move_id}",
        "move_type": "in_invoice",
        "state": state,
        "payment_state": payment_state,
        "partner_id": [20, "Global Supplier"],
        "invoice_date": "2026-02-10",
        "invoice_date_due": "2026-03-10",
        "currency_id": [1, "USD"],
        "amount_untaxed": 500.0,
        "amount_tax": 50.0,
        "amount_total": 550.0,
        "amount_residual": 0.0,
        "write_date": "2026-02-10 09:30:00",
    }


def credit_note_payload(move_id: int, move_type: str = "out_refund"):
    return {
        "id": move_id,
        "name": f"RND/2026/{move_id:04d}",
        "ref": f"CN-REF-{move_id}",
        "move_type": move_type,
        "state": "posted",
        "payment_state": "paid",
        "partner_id": [10, "Acme Customer"],
        "invoice_date": "2026-03-20",
        "currency_id": [1, "USD"],
        "amount_untaxed": 200.0,
        "amount_tax": 20.0,
        "amount_total": 220.0,
        "amount_residual": 0.0,
        "write_date": "2026-03-20 11:00:00",
    }


def payment_payload(payment_id: int, payment_type: str = "inbound", is_reconciled: bool = True):
    return {
        "id": payment_id,
        "name": f"PAY/2026/{payment_id:04d}",
        "ref": f"WIRE-{payment_id}",
        "payment_type": payment_type,
        "partner_type": "customer" if payment_type == "inbound" else "supplier",
        "partner_id": [10, "Acme Customer"],
        "amount": 600.0,
        "currency_id": [1, "USD"],
        "date": "2026-03-18",
        "state": "posted",
        "is_reconciled": is_reconciled,
        "journal_id": [5, "Bank USD"],
        "reconciled_invoice_ids": [101],
        "reconciled_bill_ids": [],
        "write_date": "2026-03-18 14:00:00",
    }


def journal_entry_payload(move_id: int):
    return {
        "id": move_id,
        "name": f"MISC/2026/{move_id:04d}",
        "ref": f"ADJ-{move_id}",
        "move_type": "entry",
        "state": "posted",
        "date": "2026-03-31",
        "journal_id": [3, "Miscellaneous Operations"],
        "partner_id": [10, "Acme Customer"],
        "currency_id": [1, "USD"],
        "amount_total": 750.0,
        "write_date": "2026-03-31 18:00:00",
    }


def move_line_payload(line_id: int, move_id: int, name: str = "Office Supplies", price: float = 100.0, qty: float = 2.0):
    return {
        "id": line_id,
        "move_id": [move_id, f"INV-{move_id}"],
        "product_id": [501, "Paper A4"],
        "name": name,
        "quantity": qty,
        "price_unit": price,
        "discount": 5.0,
        "price_subtotal": 190.0,
        "price_total": 209.0,
        "tax_ids": [[1, "VAT 10%"]],
        "account_id": [201, "Sales Account"],
        "debit": 0.0,
        "credit": 190.0,
        "balance": -190.0,
    }


# ---------------------------------------------------------------------------
# 1. External JSON-2 Client Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_odoo_client_search_read_generic():
    """Verify OdooClient.search_read queries POST /json/2/{model}/search_read."""
    client = OdooClient(
        instance_url="https://odoo.example.com",
        api_key="secret-api-key",
        database="production_db",
    )
    mock_resp = httpx.Response(
        200,
        json=[invoice_payload(101)],
        request=httpx.Request("POST", "https://odoo.example.com/json/2/account.move/search_read"),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
        data = await client.search_read(
            model="account.move",
            domain=[["move_type", "=", "out_invoice"]],
            offset=10,
            limit=25,
            fields=["name", "amount_total"],
            order="invoice_date desc",
        )
        assert len(data) == 1
        assert data[0]["id"] == 101

        mock_post.assert_awaited_once()
        url = mock_post.await_args[0][0]
        assert url == "https://odoo.example.com/json/2/account.move/search_read"
        payload = mock_post.await_args[1]["json"]
        assert payload["domain"] == [["move_type", "=", "out_invoice"]]
        assert payload["offset"] == 10
        assert payload["limit"] == 25
        assert payload["order"] == "invoice_date desc"
        headers = mock_post.await_args[1]["headers"]
        assert headers["Authorization"] == "bearer secret-api-key"
        assert headers["X-Odoo-Database"] == "production_db"


# ---------------------------------------------------------------------------
# 2. Document Classification and Normalization Tests
# ---------------------------------------------------------------------------

def test_document_classification_and_normalizers():
    """Verify document classification: out_invoice, in_invoice, out_refund, in_refund."""
    # Customer Invoice
    inv = OdooIntegration.normalize_invoice(invoice_payload(101))
    assert inv["id"] == "101"
    assert inv["invoice_number"] == "INV/2026/0101"
    assert inv["customer_name"] == "Acme Customer"
    assert inv["subtotal"] == "1000.00"
    assert inv["tax_amount"] == "100.00"
    assert inv["total"] == "1100.00"
    assert inv["balance_due"] == "500.00"
    assert inv["amount_paid"] == "600.00"
    assert inv["currency_code"] == "USD"
    assert inv["status"] == "posted"
    assert inv["payment_state"] == "not_paid"

    # Vendor Bill
    bill = OdooIntegration.normalize_bill(bill_payload(201))
    assert bill["id"] == "201"
    assert bill["bill_number"] == "BILL/2026/0201"
    assert bill["vendor_name"] == "Global Supplier"
    assert bill["total"] == "550.00"
    assert bill["balance_due"] == "0.00"
    assert bill["amount_paid"] == "550.00"
    assert bill["status"] == "posted"
    assert bill["payment_state"] == "paid"

    # Customer Credit Note (out_refund)
    cn_cust = OdooIntegration.normalize_credit_note(credit_note_payload(301, "out_refund"))
    assert cn_cust["credit_note_type"] == "customer"
    assert cn_cust["partner_name"] == "Acme Customer"
    assert cn_cust["total"] == "220.00"

    # Vendor Credit Note / Refund (in_refund)
    cn_vend = OdooIntegration.normalize_credit_note(credit_note_payload(302, "in_refund"))
    assert cn_vend["credit_note_type"] == "vendor"
    assert cn_vend["total"] == "220.00"


def test_line_item_and_tax_normalization():
    """Verify normalization of account.move.line line items and taxes."""
    raw_line = move_line_payload(901, 101)
    line = OdooIntegration.normalize_line_item(raw_line)
    assert line["id"] == "901"
    assert line["product_id"] == "501"
    assert line["product_name"] == "Paper A4"
    assert line["quantity"] == "2.0"
    assert line["price_unit"] == "100.0"
    assert line["discount"] == "5.0"
    assert line["price_subtotal"] == "190.0"
    assert line["price_total"] == "209.0"
    assert line["tax_ids"] == [[1, "VAT 10%"]]


def test_payment_extraction_and_reconciliation_links():
    """Verify payment normalization with inbound/outbound classification and reconciled links."""
    inbound = OdooIntegration.normalize_payment(payment_payload(401, "inbound", is_reconciled=True))
    assert inbound["payment_id"] == "401"
    assert inbound["payment_type"] == "inbound"
    assert inbound["partner_type"] == "customer"
    assert inbound["amount"] == "600.00"
    assert inbound["currency_code"] == "USD"
    assert inbound["is_reconciled"] is True
    assert inbound["reconciled_invoice_ids"] == [101]
    assert inbound["journal"] == {"id": 5, "name": "Bank USD"}

    outbound = OdooIntegration.normalize_payment(payment_payload(402, "outbound", is_reconciled=False))
    assert outbound["payment_type"] == "outbound"
    assert outbound["is_reconciled"] is False


@pytest.mark.asyncio
async def test_payment_fetch_uses_odoo20_fields_and_paginates_live_shape():
    """Odoo 20 account.payment has payment_reference, but no ref field."""
    client = OdooClient.__new__(OdooClient)
    page_one = [payment_payload(3, "inbound", True), payment_payload(2, "outbound", False)]
    client.search_read = AsyncMock(return_value=page_one)
    integration = Integration(
        user_id=uuid.uuid4(), provider="odoo", product="erp", connection_name="Live-shaped Odoo",
        api_domain="https://odoo.example.com", access_token="api-key", status="active",
    )

    with patch("app.integrations.odoo.integration.OdooClient", return_value=client):
        result = await odoo_integration.fetch_records(
            integration=integration, resource_type="payments", page=2, per_page=2, session=None,
        )

    args, kwargs = client.search_read.await_args
    assert args[0] == "account.payment"
    assert args[1] == []
    assert args[2:4] == (2, 2)
    fields = args[4]
    assert "payment_reference" in fields
    assert "ref" not in fields
    assert result["info"]["more_records"] is True
    assert result["data"][0]["status"] == "posted"
    assert result["data"][0]["payment_type"] == "inbound"


@pytest.mark.asyncio
async def test_live_payment_states_and_partner_types_normalize_without_filters():
    """Customer inbound and vendor outbound records are both retained."""
    client = OdooClient.__new__(OdooClient)
    customer = payment_payload(3, "inbound", True)
    customer["state"] = "reconciled"
    customer["payment_reference"] = False
    customer.pop("ref", None)
    vendor = payment_payload(1, "outbound", True)
    vendor["partner_type"] = "supplier"
    vendor["state"] = "reconciled"
    vendor["payment_reference"] = False
    vendor.pop("ref", None)
    client.search_read = AsyncMock(return_value=[customer, vendor])
    integration = Integration(
        user_id=uuid.uuid4(), provider="odoo", product="erp", connection_name="Live-shaped Odoo",
        api_domain="https://odoo.example.com", access_token="api-key", status="active",
    )

    with patch("app.integrations.odoo.integration.OdooClient", return_value=client):
        result = await odoo_integration.fetch_records(
            integration=integration, resource_type="payments", page=1, per_page=200, session=None,
        )

    assert len(result["data"]) == 2
    assert {item["partner_type"] for item in result["data"]} == {"customer", "supplier"}
    assert {item["status"] for item in result["data"]} == {"reconciled"}


@pytest.mark.asyncio
async def test_payment_incremental_sync_uses_write_date_without_state_filter():
    client = OdooClient.__new__(OdooClient)
    client.search_read = AsyncMock(return_value=[])
    integration = Integration(
        user_id=uuid.uuid4(), provider="odoo", product="erp", connection_name="Delta Odoo",
        api_domain="https://odoo.example.com", status="active",
    )
    since = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)

    with patch("app.integrations.odoo.integration.OdooClient", return_value=client):
        await odoo_integration.fetch_records(
            integration=integration, resource_type="payments", page=1, per_page=50,
            modified_since=since, session=None,
        )

    args, _ = client.search_read.await_args
    assert args[1] == [["write_date", ">=", "2026-11-01 12:00:00"]]


def test_journal_entry_normalization():
    """Verify accounting journal entries (account.move entry)."""
    entry = OdooIntegration.normalize_journal_entry(journal_entry_payload(501))
    assert entry["transaction_id"] == "501"
    assert entry["transaction_type"] == "journal_entry"
    assert entry["entry_number"] == "MISC/2026/0501"
    assert entry["journal"] == {"id": 3, "name": "Miscellaneous Operations"}
    assert entry["total_amount"] == "750.00"


# ---------------------------------------------------------------------------
# 3. Decimal Precision Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_decimal_monetary_precision_in_service(db_session: AsyncSession):
    """Verify Decimal monetary precision avoids floating-point inaccuracies."""
    user = User(name="Precision User", email=f"prec_{uuid.uuid4().hex}@example.com", hashed_password="hashed")
    db_session.add(user)
    await db_session.commit()

    integration = Integration(
        user_id=user.id, provider="odoo", product="erp", connection_name="Precision Odoo",
        api_domain="https://odoo.example.com", status="active",
    )
    db_session.add(integration)
    await db_session.commit()

    # Three invoices with fractional amounts: 0.1, 0.2, 0.3 -> total 0.60
    for idx, (tot, res) in enumerate([("100.10", "50.05"), ("200.20", "100.10"), ("300.30", "150.15")]):
        raw = invoice_payload(1000 + idx)
        raw["amount_total"] = float(tot)
        raw["amount_residual"] = float(res)
        norm = OdooIntegration.normalize_invoice(raw)
        db_session.add(IntegrationRecord(
            user_id=user.id,
            integration_id=integration.id,
            provider="odoo",
            product="erp",
            resource_type="invoices",
            external_record_id=str(1000 + idx),
            external_organization_id="https://odoo.example.com",
            raw_data=norm,
        ))
    await db_session.commit()

    service = OdooFinancialService(db_session, integration)
    stats = await service.invoice_stats()
    assert stats["total"] == 3
    assert stats["total_amount"] == "600.60"
    assert stats["total_outstanding"] == "300.30"
    assert stats["total_paid"] == "300.30"


# ---------------------------------------------------------------------------
# 4. Idempotent Synchronization & Duplicate Prevention
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_idempotent_financial_sync(db_session: AsyncSession):
    """Verify repeated syncs update existing IntegrationRecord rows without duplicating."""
    user = User(name="Sync User", email=f"sync_fin_{uuid.uuid4().hex}@example.com", hashed_password="hashed")
    db_session.add(user)
    await db_session.commit()

    integration = Integration(
        user_id=user.id, provider="odoo", product="erp", connection_name="Sync Odoo",
        api_domain="https://odoo.example.com", status="active",
    )
    db_session.add(integration)
    await db_session.commit()

    # Page 1: 2 bills; Page 2: 1 updated bill
    page1 = {
        "data": [
            OdooIntegration.normalize_bill(bill_payload(1)),
            OdooIntegration.normalize_bill(bill_payload(2)),
        ],
        "info": {"more_records": True},
    }
    updated_bill = bill_payload(1)
    updated_bill["amount_total"] = 999.0
    page2 = {
        "data": [OdooIntegration.normalize_bill(updated_bill)],
        "info": {"more_records": False},
    }

    with patch.object(odoo_integration, "fetch_records", new_callable=AsyncMock, side_effect=[page1, page2]):
        job = await SyncService(db_session).sync_resource(integration, "bills", incremental=False, per_page=2)

    assert job.status == "completed"
    assert job.records_processed == 3
    assert job.records_inserted == 2
    assert job.records_updated == 1

    # Ensure table has exactly 2 records
    count = await db_session.scalar(
        select(func.count())
        .select_from(IntegrationRecord)
        .where(IntegrationRecord.integration_id == integration.id, IntegrationRecord.resource_type == "bills")
    )
    assert count == 2

    # Verify updated total
    record_1 = await db_session.scalar(
        select(IntegrationRecord.raw_data).where(
            IntegrationRecord.integration_id == integration.id,
            IntegrationRecord.external_record_id == "1",
        )
    )
    assert record_1["total"] == "999.00"


# ---------------------------------------------------------------------------
# 5. Incremental Sync with write_date
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_incremental_sync_write_date():
    """Verify fetch_records builds write_date >= filter when modified_since is provided."""
    client = OdooClient.__new__(OdooClient)
    client.search_read = AsyncMock(return_value=[])

    integration = Integration(
        user_id=uuid.uuid4(), provider="odoo", product="erp", connection_name="Delta Odoo",
        api_domain="https://odoo.example.com", status="active",
    )

    since = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    with patch("app.integrations.odoo.integration.OdooClient", return_value=client):
        await odoo_integration.fetch_records(
            integration=integration,
            resource_type="invoices",
            page=1,
            per_page=50,
            modified_since=since,
            session=None,
        )

    client.search_read.assert_awaited_once()
    args, kwargs = client.search_read.await_args
    domain = args[1] if len(args) > 1 else kwargs.get("domain")
    assert ["move_type", "=", "out_invoice"] in domain
    assert ["write_date", ">=", "2026-03-01 12:00:00"] in domain


# ---------------------------------------------------------------------------
# 6. Tenant Isolation Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tenant_isolation_in_financial_service(db_session: AsyncSession):
    """Verify tenant isolation: User A cannot access User B's financial records."""
    user_a = User(name="User A", email=f"a_{uuid.uuid4().hex}@example.com", hashed_password="hashed")
    user_b = User(name="User B", email=f"b_{uuid.uuid4().hex}@example.com", hashed_password="hashed")
    db_session.add_all([user_a, user_b])
    await db_session.commit()

    int_a = Integration(user_id=user_a.id, provider="odoo", product="erp", connection_name="A Odoo", api_domain="https://a.odoo.com", status="active")
    int_b = Integration(user_id=user_b.id, provider="odoo", product="erp", connection_name="B Odoo", api_domain="https://b.odoo.com", status="active")
    db_session.add_all([int_a, int_b])
    await db_session.commit()

    # User A has 2 invoices, User B has 1 invoice
    for u, i, count in [(user_a, int_a, 2), (user_b, int_b, 1)]:
        for idx in range(count):
            db_session.add(IntegrationRecord(
                user_id=u.id,
                integration_id=i.id,
                provider="odoo",
                product="erp",
                resource_type="invoices",
                external_record_id=f"{u.id}-{idx}",
                external_organization_id=i.api_domain,
                raw_data=OdooIntegration.normalize_invoice(invoice_payload(idx + 1)),
            ))
    await db_session.commit()

    service_a = OdooFinancialService(db_session, int_a)
    service_b = OdooFinancialService(db_session, int_b)

    result_a = await service_a.list_invoices(page=1, per_page=10)
    result_b = await service_b.list_invoices(page=1, per_page=10)

    assert result_a["pagination"]["total"] == 2
    assert result_b["pagination"]["total"] == 1
    assert all(r["customer_name"] for r in result_a["data"])


# ---------------------------------------------------------------------------
# 7. Celery Task Execution for Financial Resources
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_celery_sync_worker_accepts_financial_resources():
    """Verify RESOURCE_TYPES_BY_PRODUCT contains all financial resources."""
    from app.workers.sync_worker import RESOURCE_TYPES_BY_PRODUCT
    erp_resources = RESOURCE_TYPES_BY_PRODUCT.get("erp", ())
    for expected in ("invoices", "bills", "credit_notes", "payments", "transactions"):
        assert expected in erp_resources, f"Expected {expected} in erp resources"


# ---------------------------------------------------------------------------
# 8. Financial Router Endpoints Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_odoo_financial_router_endpoints(client: httpx.AsyncClient, db_session: AsyncSession):
    """Verify financial router endpoints for list, stats, and refresh."""
    email = f"router_{uuid.uuid4().hex[:6]}@example.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"name": "Odoo Fin Tester", "email": email, "password": "Password123!"},
    )
    user_id = uuid.UUID(reg.json()["id"])
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    integration = Integration(
        user_id=user_id,
        provider="odoo",
        product="erp",
        connection_name="API Odoo",
        api_domain="https://api.odoo.com",
        access_token="api-key-test",
        status="active",
    )
    db_session.add(integration)
    await db_session.commit()
    await db_session.refresh(integration)

    # Add an invoice and a bill record
    db_session.add(IntegrationRecord(
        user_id=user_id,
        integration_id=integration.id,
        provider="odoo",
        product="erp",
        resource_type="invoices",
        external_record_id="inv-101",
        external_organization_id="https://api.odoo.com",
        raw_data=OdooIntegration.normalize_invoice(invoice_payload(101)),
    ))
    db_session.add(IntegrationRecord(
        user_id=user_id,
        integration_id=integration.id,
        provider="odoo",
        product="erp",
        resource_type="bills",
        external_record_id="bill-201",
        external_organization_id="https://api.odoo.com",
        raw_data=OdooIntegration.normalize_bill(bill_payload(201)),
    ))
    live_payment = payment_payload(3, "inbound", is_reconciled=True)
    live_payment["state"] = "reconciled"
    live_payment["payment_reference"] = False
    live_payment.pop("ref", None)
    db_session.add(IntegrationRecord(
        user_id=user_id,
        integration_id=integration.id,
        provider="odoo",
        product="erp",
        resource_type="payments",
        external_record_id="3",
        external_organization_id="https://api.odoo.com",
        raw_data=OdooIntegration.normalize_payment(live_payment),
    ))
    await db_session.commit()

    # 1. Invoices list & stats
    inv_resp = await client.get(f"/api/v1/integrations/odoo/{integration.id}/invoices", headers=headers)
    assert inv_resp.status_code == 200
    inv_data = inv_resp.json()
    assert inv_data["pagination"]["total"] == 1
    assert inv_data["data"][0]["invoice_number"] == "INV/2026/0101"

    inv_stats = await client.get(f"/api/v1/integrations/odoo/{integration.id}/invoices/stats", headers=headers)
    assert inv_stats.status_code == 200
    assert inv_stats.json()["total"] == 1
    assert inv_stats.json()["posted"] == 1

    # 2. Bills list & stats
    bill_resp = await client.get(f"/api/v1/integrations/odoo/{integration.id}/bills", headers=headers)
    assert bill_resp.status_code == 200
    bill_data = bill_resp.json()
    assert bill_data["pagination"]["total"] == 1
    assert bill_data["data"][0]["bill_number"] == "BILL/2026/0201"

    bill_stats = await client.get(f"/api/v1/integrations/odoo/{integration.id}/bills/stats", headers=headers)
    assert bill_stats.status_code == 200
    assert bill_stats.json()["total"] == 1

    # 3. Credit Notes, persisted Payments, Transactions empty list
    cn_resp = await client.get(f"/api/v1/integrations/odoo/{integration.id}/credit-notes", headers=headers)
    assert cn_resp.status_code == 200
    assert cn_resp.json()["pagination"]["total"] == 0

    pmt_resp = await client.get(f"/api/v1/integrations/odoo/{integration.id}/payments", headers=headers)
    assert pmt_resp.status_code == 200
    assert pmt_resp.json()["pagination"]["total"] == 1
    assert pmt_resp.json()["data"][0]["payment_id"] == "3"
    assert pmt_resp.json()["data"][0]["status"] == "reconciled"

    pmt_stats = await client.get(f"/api/v1/integrations/odoo/{integration.id}/payments/stats", headers=headers)
    assert pmt_stats.status_code == 200
    assert pmt_stats.json()["total"] == 1
    assert pmt_stats.json()["customer_payments"] == 1

    tx_resp = await client.get(f"/api/v1/integrations/odoo/{integration.id}/transactions", headers=headers)
    assert tx_resp.status_code == 200
    assert tx_resp.json()["pagination"]["total"] == 0

    # 4. Refresh endpoint with async_mode=False
    with patch.object(SyncService, "sync_resource", new_callable=AsyncMock) as mock_sync:
        mock_job = MagicMock()
        mock_job.id = uuid.uuid4()
        mock_job.status = "completed"
        mock_job.records_processed = 5
        mock_sync.return_value = mock_job

        ref_resp = await client.post(
            f"/api/v1/integrations/odoo/{integration.id}/invoices/refresh?async_mode=false",
            headers=headers,
        )
        assert ref_resp.status_code == 200
        assert ref_resp.json()["status"] == "completed"
        assert ref_resp.json()["records_processed"] == 5
