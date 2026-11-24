from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.integrations.odoo.integration import odoo_integration
from app.models.user import User
from app.services.integration_service import IntegrationService
from app.services.odoo_contacts_service import OdooContactsService
from app.services.odoo_financial_service import OdooFinancialService
from app.services.sync_service import SyncService


router = APIRouter(prefix="/integrations/odoo", tags=["Odoo Integration"])


class OdooConnectRequest(BaseModel):
    connection_name: str = Field(default="My Odoo ERP", min_length=1, max_length=100)
    instance_url: HttpUrl = Field(description="Externally hosted Odoo base URL")
    api_key: str = Field(min_length=1, max_length=2048, repr=False)
    database: Optional[str] = Field(default=None, min_length=1, max_length=100)
    integration_id: Optional[uuid.UUID] = None


class OdooConnectResponse(BaseModel):
    id: uuid.UUID
    provider: str
    product: str
    connection_name: str
    api_domain: Optional[str]
    external_database: Optional[str]
    status: str


class OdooContactsResponse(BaseModel):
    data: List[Dict[str, Any]]
    pagination: Dict[str, Any]
    sync: Dict[str, Any]


class OdooFinancialResponse(BaseModel):
    data: List[Dict[str, Any]]
    pagination: Dict[str, Any]
    sync: Dict[str, Any]


@router.post(
    "/connect",
    response_model=OdooConnectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Validate and connect an external Odoo JSON-2 instance",
)
async def connect_odoo(
    request: OdooConnectRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> OdooConnectResponse:
    integration = await odoo_integration.connect(
        user_id=current_user.id,
        connection_name=request.connection_name,
        instance_url=str(request.instance_url),
        api_key=request.api_key,
        database=request.database,
        integration_id=request.integration_id,
        session=session,
    )
    return OdooConnectResponse(
        id=integration.id,
        provider=integration.provider,
        product=integration.product,
        connection_name=integration.connection_name,
        api_domain=integration.api_domain,
        external_database=integration.external_database,
        status=integration.status,
    )


async def _owned_odoo_integration(user: User, integration_id: uuid.UUID, session: AsyncSession):
    integration = await IntegrationService(session).get_user_integration(user.id, integration_id)
    if integration.provider != "odoo" or integration.product != "erp":
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="The selected integration is not an Odoo ERP connection.")
    return integration


@router.get("/{integration_id}/contacts", response_model=OdooContactsResponse)
async def list_odoo_contacts(
    integration_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=500),
    kind: Optional[str] = Query(None, pattern="^(customer|vendor)$"),
    search: Optional[str] = Query(None, max_length=200),
    include_archived: bool = True,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    integration = await _owned_odoo_integration(current_user, integration_id, session)
    service = OdooContactsService(session, integration)
    result = await service.list_local(page, per_page, kind, search, include_archived)
    result["sync"] = await service.sync_status()
    return result


@router.get("/{integration_id}/contacts/stats")
async def odoo_contact_stats(
    integration_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    integration = await _owned_odoo_integration(current_user, integration_id, session)
    return await OdooContactsService(session, integration).stats()


@router.post("/{integration_id}/contacts/refresh")
async def refresh_odoo_contacts(
    integration_id: uuid.UUID,
    async_mode: bool = True,
    per_page: int = Query(200, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    integration = await _owned_odoo_integration(current_user, integration_id, session)
    sync = SyncService(session)
    if async_mode:
        from app.workers.sync_worker import sync_resource_task
        job = await sync.start_sync_record(integration.id, "contacts")
        task = sync_resource_task.delay(
            integration_id=str(integration.id), resource_type="contacts", incremental=False,
            sync_id=str(job.id), per_page=per_page,
        )
        return {"status": "queued", "task_id": task.id, "sync_id": str(job.id)}
    job = await sync.sync_resource(integration, "contacts", incremental=False, per_page=per_page)
    return {"status": job.status, "sync_id": str(job.id), "records_processed": job.records_processed}


# -------------------------------------------------------------------------
# Financial Resources: Invoices
# -------------------------------------------------------------------------

@router.get("/{integration_id}/invoices", response_model=OdooFinancialResponse)
async def list_odoo_invoices(
    integration_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=500),
    search: Optional[str] = Query(None, max_length=200),
    status: Optional[str] = Query(None, max_length=50),
    payment_state: Optional[str] = Query(None, max_length=50),
    partner_id: Optional[str] = Query(None, max_length=100),
    sort_by: str = Query("invoice_date"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    integration = await _owned_odoo_integration(current_user, integration_id, session)
    service = OdooFinancialService(session, integration)
    result = await service.list_invoices(
        page=page,
        per_page=per_page,
        search=search,
        status=status,
        payment_state=payment_state,
        partner_id=partner_id,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    result["sync"] = await service.sync_status("invoices")
    return result


@router.get("/{integration_id}/invoices/stats")
async def odoo_invoice_stats(
    integration_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    integration = await _owned_odoo_integration(current_user, integration_id, session)
    return await OdooFinancialService(session, integration).invoice_stats()


@router.post("/{integration_id}/invoices/refresh")
async def refresh_odoo_invoices(
    integration_id: uuid.UUID,
    async_mode: bool = True,
    per_page: int = Query(200, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    integration = await _owned_odoo_integration(current_user, integration_id, session)
    sync = SyncService(session)
    if async_mode:
        from app.workers.sync_worker import sync_resource_task
        job = await sync.start_sync_record(integration.id, "invoices")
        task = sync_resource_task.delay(
            integration_id=str(integration.id), resource_type="invoices", incremental=False,
            sync_id=str(job.id), per_page=per_page,
        )
        return {"status": "queued", "task_id": task.id, "sync_id": str(job.id), "resource_type": "invoices"}
    job = await sync.sync_resource(integration, "invoices", incremental=False, per_page=per_page)
    return {"status": job.status, "sync_id": str(job.id), "records_processed": job.records_processed}


# -------------------------------------------------------------------------
# Financial Resources: Vendor Bills
# -------------------------------------------------------------------------

@router.get("/{integration_id}/bills", response_model=OdooFinancialResponse)
async def list_odoo_bills(
    integration_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=500),
    search: Optional[str] = Query(None, max_length=200),
    status: Optional[str] = Query(None, max_length=50),
    payment_state: Optional[str] = Query(None, max_length=50),
    partner_id: Optional[str] = Query(None, max_length=100),
    sort_by: str = Query("bill_date"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    integration = await _owned_odoo_integration(current_user, integration_id, session)
    service = OdooFinancialService(session, integration)
    result = await service.list_bills(
        page=page,
        per_page=per_page,
        search=search,
        status=status,
        payment_state=payment_state,
        partner_id=partner_id,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    result["sync"] = await service.sync_status("bills")
    return result


@router.get("/{integration_id}/bills/stats")
async def odoo_bill_stats(
    integration_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    integration = await _owned_odoo_integration(current_user, integration_id, session)
    return await OdooFinancialService(session, integration).bill_stats()


@router.post("/{integration_id}/bills/refresh")
async def refresh_odoo_bills(
    integration_id: uuid.UUID,
    async_mode: bool = True,
    per_page: int = Query(200, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    integration = await _owned_odoo_integration(current_user, integration_id, session)
    sync = SyncService(session)
    if async_mode:
        from app.workers.sync_worker import sync_resource_task
        job = await sync.start_sync_record(integration.id, "bills")
        task = sync_resource_task.delay(
            integration_id=str(integration.id), resource_type="bills", incremental=False,
            sync_id=str(job.id), per_page=per_page,
        )
        return {"status": "queued", "task_id": task.id, "sync_id": str(job.id), "resource_type": "bills"}
    job = await sync.sync_resource(integration, "bills", incremental=False, per_page=per_page)
    return {"status": job.status, "sync_id": str(job.id), "records_processed": job.records_processed}


# -------------------------------------------------------------------------
# Financial Resources: Credit Notes / Refunds
# -------------------------------------------------------------------------

@router.get("/{integration_id}/credit-notes", response_model=OdooFinancialResponse)
async def list_odoo_credit_notes(
    integration_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=500),
    search: Optional[str] = Query(None, max_length=200),
    kind: Optional[str] = Query(None, pattern="^(customer|vendor)$"),
    status: Optional[str] = Query(None, max_length=50),
    partner_id: Optional[str] = Query(None, max_length=100),
    sort_by: str = Query("date"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    integration = await _owned_odoo_integration(current_user, integration_id, session)
    service = OdooFinancialService(session, integration)
    result = await service.list_credit_notes(
        page=page,
        per_page=per_page,
        search=search,
        kind=kind,
        status=status,
        partner_id=partner_id,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    result["sync"] = await service.sync_status("credit_notes")
    return result


@router.get("/{integration_id}/credit-notes/stats")
async def odoo_credit_note_stats(
    integration_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    integration = await _owned_odoo_integration(current_user, integration_id, session)
    return await OdooFinancialService(session, integration).credit_note_stats()


@router.post("/{integration_id}/credit-notes/refresh")
async def refresh_odoo_credit_notes(
    integration_id: uuid.UUID,
    async_mode: bool = True,
    per_page: int = Query(200, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    integration = await _owned_odoo_integration(current_user, integration_id, session)
    sync = SyncService(session)
    if async_mode:
        from app.workers.sync_worker import sync_resource_task
        job = await sync.start_sync_record(integration.id, "credit_notes")
        task = sync_resource_task.delay(
            integration_id=str(integration.id), resource_type="credit_notes", incremental=False,
            sync_id=str(job.id), per_page=per_page,
        )
        return {"status": "queued", "task_id": task.id, "sync_id": str(job.id), "resource_type": "credit_notes"}
    job = await sync.sync_resource(integration, "credit_notes", incremental=False, per_page=per_page)
    return {"status": job.status, "sync_id": str(job.id), "records_processed": job.records_processed}


# -------------------------------------------------------------------------
# Financial Resources: Payments
# -------------------------------------------------------------------------

@router.get("/{integration_id}/payments", response_model=OdooFinancialResponse)
async def list_odoo_payments(
    integration_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=500),
    search: Optional[str] = Query(None, max_length=200),
    payment_type: Optional[str] = Query(None, pattern="^(inbound|outbound)$"),
    status: Optional[str] = Query(None, max_length=50),
    start_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    sort_by: str = Query("payment_date"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    integration = await _owned_odoo_integration(current_user, integration_id, session)
    service = OdooFinancialService(session, integration)
    result = await service.list_payments(
        page=page,
        per_page=per_page,
        search=search,
        payment_type=payment_type,
        status=status,
        start_date=start_date,
        end_date=end_date,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    result["sync"] = await service.sync_status("payments")
    return result


@router.get("/{integration_id}/payments/stats")
async def odoo_payment_stats(
    integration_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    integration = await _owned_odoo_integration(current_user, integration_id, session)
    return await OdooFinancialService(session, integration).payment_stats()


@router.post("/{integration_id}/payments/refresh")
async def refresh_odoo_payments(
    integration_id: uuid.UUID,
    async_mode: bool = True,
    per_page: int = Query(200, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    integration = await _owned_odoo_integration(current_user, integration_id, session)
    sync = SyncService(session)
    if async_mode:
        from app.workers.sync_worker import sync_resource_task
        job = await sync.start_sync_record(integration.id, "payments")
        task = sync_resource_task.delay(
            integration_id=str(integration.id), resource_type="payments", incremental=False,
            sync_id=str(job.id), per_page=per_page,
        )
        return {"status": "queued", "task_id": task.id, "sync_id": str(job.id), "resource_type": "payments"}
    job = await sync.sync_resource(integration, "payments", incremental=False, per_page=per_page)
    return {"status": job.status, "sync_id": str(job.id), "records_processed": job.records_processed}


# -------------------------------------------------------------------------
# Financial Resources: Accounting Transactions
# -------------------------------------------------------------------------

@router.get("/{integration_id}/transactions", response_model=OdooFinancialResponse)
async def list_odoo_transactions(
    integration_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=500),
    search: Optional[str] = Query(None, max_length=200),
    transaction_type: Optional[str] = Query(None, pattern="^(journal_entry|bank_transaction)$"),
    journal_id: Optional[str] = Query(None, max_length=100),
    start_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    sort_by: str = Query("date"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    integration = await _owned_odoo_integration(current_user, integration_id, session)
    service = OdooFinancialService(session, integration)
    result = await service.list_transactions(
        page=page,
        per_page=per_page,
        search=search,
        transaction_type=transaction_type,
        journal_id=journal_id,
        start_date=start_date,
        end_date=end_date,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    result["sync"] = await service.sync_status("transactions")
    return result


@router.get("/{integration_id}/transactions/stats")
async def odoo_transaction_stats(
    integration_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    integration = await _owned_odoo_integration(current_user, integration_id, session)
    return await OdooFinancialService(session, integration).transaction_stats()


@router.post("/{integration_id}/transactions/refresh")
async def refresh_odoo_transactions(
    integration_id: uuid.UUID,
    async_mode: bool = True,
    per_page: int = Query(200, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    integration = await _owned_odoo_integration(current_user, integration_id, session)
    sync = SyncService(session)
    if async_mode:
        from app.workers.sync_worker import sync_resource_task
        job = await sync.start_sync_record(integration.id, "transactions")
        task = sync_resource_task.delay(
            integration_id=str(integration.id), resource_type="transactions", incremental=False,
            sync_id=str(job.id), per_page=per_page,
        )
        return {"status": "queued", "task_id": task.id, "sync_id": str(job.id), "resource_type": "transactions"}
    job = await sync.sync_resource(integration, "transactions", incremental=False, per_page=per_page)
    return {"status": job.status, "sync_id": str(job.id), "records_processed": job.records_processed}
