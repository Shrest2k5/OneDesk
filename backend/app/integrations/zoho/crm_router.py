from typing import Optional
import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.integrations.zoho.client import ZohoClient
from app.integrations.zoho.schemas.crm import (
    PaginatedAccountsResponse,
    PaginatedContactsResponse,
    PaginatedDealsResponse,
    PaginatedLeadsResponse,
    ZohoAccount,
    ZohoContact,
    ZohoDeal,
    ZohoLead,
)
from app.integrations.zoho.services.accounts import ZohoAccountsService
from app.integrations.zoho.services.contacts import ZohoContactsService
from app.integrations.zoho.services.deals import ZohoDealsService
from app.integrations.zoho.services.leads import ZohoLeadsService
from app.models.user import User
from app.services.integration_service import IntegrationService

router = APIRouter(prefix="/zoho", tags=["Zoho CRM Data Retrieval"])


# --- Contacts Endpoints ---
@router.get(
    "/contacts",
    response_model=PaginatedContactsResponse,
    status_code=status.HTTP_200_OK,
    summary="Fetch contacts from connected Zoho CRM",
)
async def list_contacts(
    integration_id: Optional[uuid.UUID] = Query(None, description="Zoho integration UUID"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    per_page: int = Query(200, ge=1, le=200, description="Records per page (max 200)"),
    fields: Optional[str] = Query(None, description="Comma-separated field projection"),
    modified_since: Optional[str] = Query(None, description="ISO-8601 modified since timestamp"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve paginated contacts from user's connected Zoho CRM account."""
    int_service = IntegrationService(session)
    integration = await int_service.resolve_active_integration(current_user.id, integration_id, "zoho")

    client = ZohoClient(integration, session)
    contacts_service = ZohoContactsService(client)
    field_list = [f.strip() for f in fields.split(",") if f.strip()] if fields else None

    return await contacts_service.list_contacts(
        page=page,
        per_page=per_page,
        fields=field_list,
        modified_since=modified_since,
    )


@router.get(
    "/contacts/{contact_id}",
    response_model=ZohoContact,
    status_code=status.HTTP_200_OK,
    summary="Get single contact by Zoho record ID",
)
async def get_contact(
    contact_id: str,
    integration_id: Optional[uuid.UUID] = Query(None, description="Zoho integration UUID"),
    fields: Optional[str] = Query(None, description="Comma-separated field projection"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve an individual contact by record ID."""
    int_service = IntegrationService(session)
    integration = await int_service.resolve_active_integration(current_user.id, integration_id, "zoho")

    client = ZohoClient(integration, session)
    contacts_service = ZohoContactsService(client)
    field_list = [f.strip() for f in fields.split(",") if f.strip()] if fields else None

    return await contacts_service.get_contact(contact_id=contact_id, fields=field_list)


# --- Leads Endpoints ---
@router.get(
    "/leads",
    response_model=PaginatedLeadsResponse,
    status_code=status.HTTP_200_OK,
    summary="Fetch leads from connected Zoho CRM",
)
async def list_leads(
    integration_id: Optional[uuid.UUID] = Query(None, description="Zoho integration UUID"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(200, ge=1, le=200, description="Records per page"),
    fields: Optional[str] = Query(None, description="Comma-separated field projection"),
    modified_since: Optional[str] = Query(None, description="ISO-8601 modified since timestamp"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve paginated leads from user's connected Zoho CRM account."""
    int_service = IntegrationService(session)
    integration = await int_service.resolve_active_integration(current_user.id, integration_id, "zoho")

    client = ZohoClient(integration, session)
    leads_service = ZohoLeadsService(client)
    field_list = [f.strip() for f in fields.split(",") if f.strip()] if fields else None

    return await leads_service.list_leads(
        page=page,
        per_page=per_page,
        fields=field_list,
        modified_since=modified_since,
    )


@router.get(
    "/leads/{lead_id}",
    response_model=ZohoLead,
    status_code=status.HTTP_200_OK,
    summary="Get single lead by Zoho record ID",
)
async def get_lead(
    lead_id: str,
    integration_id: Optional[uuid.UUID] = Query(None, description="Zoho integration UUID"),
    fields: Optional[str] = Query(None, description="Comma-separated field projection"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve an individual lead by record ID."""
    int_service = IntegrationService(session)
    integration = await int_service.resolve_active_integration(current_user.id, integration_id, "zoho")

    client = ZohoClient(integration, session)
    leads_service = ZohoLeadsService(client)
    field_list = [f.strip() for f in fields.split(",") if f.strip()] if fields else None

    return await leads_service.get_lead(lead_id=lead_id, fields=field_list)


# --- Deals Endpoints ---
@router.get(
    "/deals",
    response_model=PaginatedDealsResponse,
    status_code=status.HTTP_200_OK,
    summary="Fetch deals from connected Zoho CRM",
)
async def list_deals(
    integration_id: Optional[uuid.UUID] = Query(None, description="Zoho integration UUID"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(200, ge=1, le=200, description="Records per page"),
    fields: Optional[str] = Query(None, description="Comma-separated field projection"),
    modified_since: Optional[str] = Query(None, description="ISO-8601 modified since timestamp"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve paginated deals from user's connected Zoho CRM account."""
    int_service = IntegrationService(session)
    integration = await int_service.resolve_active_integration(current_user.id, integration_id, "zoho")

    client = ZohoClient(integration, session)
    deals_service = ZohoDealsService(client)
    field_list = [f.strip() for f in fields.split(",") if f.strip()] if fields else None

    return await deals_service.list_deals(
        page=page,
        per_page=per_page,
        fields=field_list,
        modified_since=modified_since,
    )


@router.get(
    "/deals/{deal_id}",
    response_model=ZohoDeal,
    status_code=status.HTTP_200_OK,
    summary="Get single deal by Zoho record ID",
)
async def get_deal(
    deal_id: str,
    integration_id: Optional[uuid.UUID] = Query(None, description="Zoho integration UUID"),
    fields: Optional[str] = Query(None, description="Comma-separated field projection"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve an individual deal by record ID."""
    int_service = IntegrationService(session)
    integration = await int_service.resolve_active_integration(current_user.id, integration_id, "zoho")

    client = ZohoClient(integration, session)
    deals_service = ZohoDealsService(client)
    field_list = [f.strip() for f in fields.split(",") if f.strip()] if fields else None

    return await deals_service.get_deal(deal_id=deal_id, fields=field_list)


# --- Accounts Endpoints ---
@router.get(
    "/accounts",
    response_model=PaginatedAccountsResponse,
    status_code=status.HTTP_200_OK,
    summary="Fetch accounts from connected Zoho CRM",
)
async def list_accounts(
    integration_id: Optional[uuid.UUID] = Query(None, description="Zoho integration UUID"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(200, ge=1, le=200, description="Records per page"),
    fields: Optional[str] = Query(None, description="Comma-separated field projection"),
    modified_since: Optional[str] = Query(None, description="ISO-8601 modified since timestamp"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve paginated accounts from user's connected Zoho CRM account."""
    int_service = IntegrationService(session)
    integration = await int_service.resolve_active_integration(current_user.id, integration_id, "zoho")

    client = ZohoClient(integration, session)
    accounts_service = ZohoAccountsService(client)
    field_list = [f.strip() for f in fields.split(",") if f.strip()] if fields else None

    return await accounts_service.list_accounts(
        page=page,
        per_page=per_page,
        fields=field_list,
        modified_since=modified_since,
    )


@router.get(
    "/accounts/{account_id}",
    response_model=ZohoAccount,
    status_code=status.HTTP_200_OK,
    summary="Get single account by Zoho record ID",
)
async def get_account(
    account_id: str,
    integration_id: Optional[uuid.UUID] = Query(None, description="Zoho integration UUID"),
    fields: Optional[str] = Query(None, description="Comma-separated field projection"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve an individual account by record ID."""
    int_service = IntegrationService(session)
    integration = await int_service.resolve_active_integration(current_user.id, integration_id, "zoho")

    client = ZohoClient(integration, session)
    accounts_service = ZohoAccountsService(client)
    field_list = [f.strip() for f in fields.split(",") if f.strip()] if fields else None

    return await accounts_service.get_account(account_id=account_id, fields=field_list)

