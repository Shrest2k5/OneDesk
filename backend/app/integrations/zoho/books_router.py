from datetime import datetime
from typing import List, Optional
from urllib.parse import urlencode
import uuid

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.core.config import settings
from app.core.logging import logger
from app.integrations.zoho.books_integration import zoho_books_integration
from app.integrations.zoho.books_client import ZohoBooksClient
from app.integrations.zoho.exceptions import ZohoOAuthError
from app.models.user import User
from app.models.books_organization import BooksOrganization
from app.services.integration_service import IntegrationService
from app.repositories.books_organization_repository import BooksOrganizationRepository
from app.services.books_contacts_service import BooksContactsService
from app.services.books_invoices_service import BooksInvoicesService
from app.services.books_transactions_service import BooksTransactionsService

router = APIRouter(prefix="/integrations/zoho/books", tags=["Zoho Books Integration"])


class ZohoBooksConnectRequest(BaseModel):
    connection_name: str = Field(default="My Zoho Books", min_length=1, max_length=100)
    data_center: Optional[str] = Field(
        default=None,
        pattern="^(us|eu|in|cn|au|ca|jp)$",
        description="Zoho data center: us, eu, in, cn, au, ca, jp",
    )


class ZohoBooksConnectResponse(BaseModel):
    authorization_url: str
    state: str
    data_center: str


class BooksOrganizationResponse(BaseModel):
    id: uuid.UUID
    external_organization_id: str
    name: str
    email: Optional[str] = None
    currency_code: Optional[str] = None
    currency_symbol: Optional[str] = None
    time_zone: Optional[str] = None
    is_default_org: bool
    is_org_active: bool
    fetched_at: datetime
    selected: bool = False

    model_config = ConfigDict(from_attributes=True)


class BooksContactsResponse(BaseModel):
    data: List[dict]
    pagination: dict
    sync: dict


class BooksContactStatsResponse(BaseModel):
    total: int
    customers: int
    vendors: int


class BooksInvoicesResponse(BaseModel):
    data: List[dict]
    pagination: dict
    sync: dict


class BooksInvoiceStatsResponse(BaseModel):
    total: int
    outstanding: int
    draft: int
    sent: int
    overdue: int
    paid: int
    partially_paid: int
    total_amount: str
    total_outstanding: str

class BooksTransactionsResponse(BaseModel):
    data: List[dict]
    pagination: dict
    sync: dict


def _organization_response(org: BooksOrganization, selected_id: Optional[str]) -> BooksOrganizationResponse:
    return BooksOrganizationResponse(
        id=org.id,
        external_organization_id=org.external_organization_id,
        name=org.name,
        email=org.email,
        currency_code=org.currency_code,
        currency_symbol=org.currency_symbol,
        time_zone=org.time_zone,
        is_default_org=org.is_default_org,
        is_org_active=org.is_org_active,
        fetched_at=org.fetched_at,
        selected=org.external_organization_id == selected_id,
    )


async def _list_books_organizations(
    integration_id: uuid.UUID,
    current_user: User,
    session: AsyncSession,
    refresh: bool,
) -> List[BooksOrganizationResponse]:
    integration = await IntegrationService(session).resolve_books_integration(current_user.id, integration_id)
    repo = BooksOrganizationRepository(session)
    if refresh:
        payload = await ZohoBooksClient(integration, session).list_organizations()
        await repo.upsert_many(current_user.id, integration.id, payload)
        await session.commit()
    organizations = await repo.list_for_user(current_user.id, integration.id)
    return [_organization_response(org, integration.selected_organization_id) for org in organizations]


@router.post("/connect", response_model=ZohoBooksConnectResponse, status_code=status.HTTP_200_OK)
async def initiate_zoho_books_connect(
    request: ZohoBooksConnectRequest,
    current_user: User = Depends(get_current_user),
):
    auth_data = zoho_books_integration.generate_authorization_url(
        user_id=current_user.id,
        connection_name=request.connection_name,
        data_center=request.data_center,
    )
    return ZohoBooksConnectResponse(
        authorization_url=auth_data["authorization_url"],
        state=auth_data["state"],
        data_center=auth_data["data_center"],
    )


@router.get("/callback", summary="Handle Zoho Books OAuth 2.0 redirect callback")
async def handle_zoho_books_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
):
    def frontend_callback_redirect(callback_status: str, integration_id: Optional[uuid.UUID] = None) -> RedirectResponse:
        query = {"status": callback_status}
        if integration_id:
            query["integration_id"] = str(integration_id)
        location = (
            f"{settings.FRONTEND_BASE_URL.rstrip('/')}/integrations/zoho/books/callback?"
            f"{urlencode(query)}"
        )
        return RedirectResponse(url=location, status_code=status.HTTP_303_SEE_OTHER)

    if error or not code or not state:
        logger.warning("Zoho Books OAuth callback was denied or missing required parameters")
        return frontend_callback_redirect("error")

    try:
        integration = await zoho_books_integration.handle_oauth_callback(code, state, session)
    except ZohoOAuthError as exc:
        logger.warning("Zoho Books OAuth callback failed: %s", exc)
        return frontend_callback_redirect("error")
    except Exception:
        logger.exception("Unexpected Zoho Books OAuth callback failure")
        return frontend_callback_redirect("error")

    return frontend_callback_redirect("success", integration.id)


@router.get("/{integration_id}/organizations", response_model=List[BooksOrganizationResponse])
async def list_books_organizations(
    integration_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await _list_books_organizations(integration_id, current_user, session, refresh=False)


@router.post("/{integration_id}/organizations/refresh", response_model=List[BooksOrganizationResponse])
async def refresh_books_organizations(
    integration_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await _list_books_organizations(integration_id, current_user, session, refresh=True)


@router.get("/{integration_id}/organizations/selected", response_model=Optional[BooksOrganizationResponse])
async def get_selected_books_organization(
    integration_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    integration = await IntegrationService(session).resolve_books_integration(current_user.id, integration_id)
    if not integration.selected_organization_id:
        return None
    organization = await BooksOrganizationRepository(session).get_for_user(
        current_user.id, integration.id, integration.selected_organization_id
    )
    if not organization:
        return None
    return _organization_response(organization, integration.selected_organization_id)


async def _books_contacts_service(integration_id: uuid.UUID, current_user: User, session: AsyncSession) -> BooksContactsService:
    integration = await IntegrationService(session).resolve_books_integration(current_user.id, integration_id)
    return BooksContactsService(session, integration)


@router.get("/{integration_id}/contacts", response_model=BooksContactsResponse)
async def list_books_contacts(
    integration_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=200),
    contact_type: Optional[str] = Query(None, pattern="^(customer|vendor)$"),
    search: Optional[str] = Query(None, max_length=200),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = await _books_contacts_service(integration_id, current_user, session)
    result = await service.list_local(page, per_page, contact_type, search)
    result["sync"] = await service.status()
    return result


@router.get("/{integration_id}/contacts/stats", response_model=BooksContactStatsResponse)
async def books_contact_stats(
    integration_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await (await _books_contacts_service(integration_id, current_user, session)).stats()


@router.post("/{integration_id}/contacts/refresh", response_model=dict, status_code=status.HTTP_200_OK)
async def refresh_books_contacts(
    integration_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    job = await (await _books_contacts_service(integration_id, current_user, session)).synchronize()
    return {"status": job.status, "sync_id": str(job.id), "records_processed": job.records_processed, "records_inserted": job.records_inserted, "records_updated": job.records_updated, "records_failed": job.records_failed, "last_successful_sync": job.successful_at, "error": job.error_message}


async def _books_invoices_service(integration_id: uuid.UUID, current_user: User, session: AsyncSession) -> BooksInvoicesService:
    integration = await IntegrationService(session).resolve_books_integration(current_user.id, integration_id)
    return BooksInvoicesService(session, integration)


@router.get("/{integration_id}/invoices", response_model=BooksInvoicesResponse)
async def list_books_invoices(
    integration_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=200),
    search: Optional[str] = Query(None, max_length=200),
    invoice_status: Optional[str] = Query(None, max_length=50),
    customer_id: Optional[str] = Query(None, max_length=100),
    sort_by: str = Query("invoice_date", pattern="^(invoice_date|total)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = await _books_invoices_service(integration_id, current_user, session)
    result = await service.list_local(page, per_page, search, invoice_status, customer_id, sort_by, sort_order)
    result["sync"] = await service.sync_status()
    return result


@router.get("/{integration_id}/invoices/stats", response_model=BooksInvoiceStatsResponse)
async def books_invoice_stats(
    integration_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await (await _books_invoices_service(integration_id, current_user, session)).stats()


@router.post("/{integration_id}/invoices/refresh", response_model=dict, status_code=status.HTTP_200_OK)
async def refresh_books_invoices(
    integration_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    job = await (await _books_invoices_service(integration_id, current_user, session)).synchronize()
    return {"status": job.status, "sync_id": str(job.id), "records_processed": job.records_processed, "records_inserted": job.records_inserted, "records_updated": job.records_updated, "records_failed": job.records_failed, "last_successful_sync": job.successful_at, "error": job.error_message}


async def _books_transactions_service(integration_id: uuid.UUID, current_user: User, session: AsyncSession) -> BooksTransactionsService:
    integration = await IntegrationService(session).resolve_books_integration(current_user.id, integration_id)
    return BooksTransactionsService(session, integration)


@router.get("/{integration_id}/transactions", response_model=BooksTransactionsResponse)
async def list_books_transactions(
    integration_id: uuid.UUID, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200),
    start_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"), end_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    transaction_type: Optional[str] = Query(None, max_length=50), search: Optional[str] = Query(None, max_length=200),
    current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db),
):
    service = await _books_transactions_service(integration_id, current_user, session)
    result = await service.list_local(page, page_size, start_date, end_date, transaction_type, search)
    result["sync"] = await service.status()
    return result


@router.get("/{integration_id}/transactions/stats")
async def books_transactions_stats(
    integration_id: uuid.UUID, start_date: Optional[str] = Query(None), end_date: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db),
):
    return await (await _books_transactions_service(integration_id, current_user, session)).stats(start_date, end_date)


@router.post("/{integration_id}/transactions/refresh", response_model=dict, status_code=status.HTTP_200_OK)
async def refresh_books_transactions(
    integration_id: uuid.UUID, start_date: Optional[str] = Query(None), end_date: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db),
):
    job = await (await _books_transactions_service(integration_id, current_user, session)).synchronize(start_date, end_date)
    return {"status": job.status, "sync_id": str(job.id), "records_processed": job.records_processed, "records_inserted": job.records_inserted, "records_updated": job.records_updated, "records_failed": job.records_failed, "last_successful_sync": job.successful_at, "error": job.error_message}


@router.put("/{integration_id}/organizations/{external_organization_id}/select", response_model=BooksOrganizationResponse)
async def select_books_organization(
    integration_id: uuid.UUID,
    external_organization_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    integration = await IntegrationService(session).resolve_books_integration(current_user.id, integration_id)
    organization = await BooksOrganizationRepository(session).get_for_user(
        current_user.id, integration.id, external_organization_id
    )
    if not organization:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Books organization not found for this integration.")
    integration.selected_organization_id = organization.external_organization_id
    await session.commit()
    await session.refresh(integration)
    return _organization_response(organization, integration.selected_organization_id)
