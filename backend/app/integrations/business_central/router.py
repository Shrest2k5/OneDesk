from typing import Optional
from urllib.parse import urlencode
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.core.config import settings
from app.core.logging import logger
from app.integrations.business_central.exceptions import BusinessCentralOAuthError
from app.integrations.business_central.client import BusinessCentralAPIError
from app.integrations.business_central.integration import business_central_integration
from app.models.user import User
from app.services.integration_service import IntegrationService
from app.repositories.integration_repository import IntegrationRepository


router = APIRouter(prefix="/integrations/business-central", tags=["Business Central Integration"])


class BusinessCentralConnectRequest(BaseModel):
    connection_name: str = Field(default="My Business Central", min_length=1, max_length=100)
    integration_id: Optional[uuid.UUID] = None


class BusinessCentralConnectResponse(BaseModel):
    authorization_url: str
    state: str


class BusinessCentralEnvironmentResponse(BaseModel):
    name: str
    type: Optional[str] = None
    status: Optional[str] = None
    application_version: Optional[str] = None
    raw: dict = {}


class BusinessCentralEnvironmentsResponse(BaseModel):
    data: list[BusinessCentralEnvironmentResponse]
    source: str
    warning: Optional[str] = None


class BusinessCentralCompanyResponse(BaseModel):
    id: str
    display_name: str
    name: Optional[str] = None
    raw: dict = {}


@router.post("/connect", response_model=BusinessCentralConnectResponse)
async def initiate_business_central_connect(
    request: BusinessCentralConnectRequest,
    current_user: User = Depends(get_current_user),
):
    auth_data = business_central_integration.generate_authorization_url(
        user_id=current_user.id,
        connection_name=request.connection_name,
        integration_id=request.integration_id,
    )
    return auth_data


@router.get("/callback", summary="Handle Microsoft Entra Business Central OAuth callback")
async def handle_business_central_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
):
    def frontend_redirect(callback_status: str, integration_id: Optional[uuid.UUID] = None) -> RedirectResponse:
        query = {"status": callback_status}
        if integration_id:
            query["integration_id"] = str(integration_id)
        location = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/integrations/business-central/callback?{urlencode(query)}"
        return RedirectResponse(url=location, status_code=status.HTTP_303_SEE_OTHER)

    if error or not code or not state:
        logger.warning("Business Central OAuth callback was denied or missing required parameters")
        return frontend_redirect("error")
    try:
        integration = await business_central_integration.handle_oauth_callback(code, state, session)
    except BusinessCentralOAuthError as exc:
        logger.warning("Business Central OAuth callback failed: %s", exc)
        return frontend_redirect("error")
    except Exception:
        logger.exception("Unexpected Business Central OAuth callback failure")
        return frontend_redirect("error")
    return frontend_redirect("success", integration.id)


async def _owned_business_central_integration(
    integration_id: uuid.UUID, current_user: User, session: AsyncSession
):
    integration = await IntegrationService(session).get_user_integration(current_user.id, integration_id)
    if integration.provider != "business_central" or integration.product != "erp":
        raise HTTPException(status_code=400, detail="This is not a Business Central integration.")
    return integration


def _bc_api_error(exc: BusinessCentralAPIError) -> HTTPException:
    if exc.status_code in {401, 403}:
        return HTTPException(status_code=exc.status_code, detail="Business Central denied access to this resource.")
    return HTTPException(status_code=502 if exc.status_code >= 500 else exc.status_code, detail=str(exc))


@router.get("/{integration_id}/environments", response_model=BusinessCentralEnvironmentsResponse)
async def list_business_central_environments(
    integration_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    integration = await _owned_business_central_integration(integration_id, current_user, session)
    try:
        return await business_central_integration.discover_environments(integration, session)
    except BusinessCentralAPIError as exc:
        raise _bc_api_error(exc) from exc


@router.get("/{integration_id}/companies", response_model=list[BusinessCentralCompanyResponse])
async def list_business_central_companies(
    integration_id: uuid.UUID,
    environment_name: str = Query(..., min_length=1, max_length=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    integration = await _owned_business_central_integration(integration_id, current_user, session)
    try:
        return await business_central_integration.discover_companies(integration, environment_name, session)
    except BusinessCentralAPIError as exc:
        raise _bc_api_error(exc) from exc


@router.put("/{integration_id}/companies/{company_id}/select", response_model=BusinessCentralCompanyResponse)
async def select_business_central_company(
    integration_id: uuid.UUID,
    company_id: str,
    environment_name: str = Query(..., min_length=1, max_length=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    integration = await _owned_business_central_integration(integration_id, current_user, session)
    try:
        companies = await business_central_integration.discover_companies(integration, environment_name, session)
    except BusinessCentralAPIError as exc:
        raise _bc_api_error(exc) from exc
    company = next((item for item in companies if item["id"] == str(company_id).strip()), None)
    if not company:
        raise HTTPException(status_code=404, detail="Business Central company was not found in the selected environment.")
    tenant_id = integration.business_central_tenant_id
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Business Central tenant identity is unavailable. Reauthorize this connection before selecting a company.",
        )
    existing = await IntegrationRepository(session).get_business_central_connection(
        current_user.id, tenant_id, environment_name.strip(), company["id"]
    )
    if existing and existing.id != integration.id:
        raise HTTPException(status_code=409, detail="This Business Central company is already connected.")
    integration.business_central_tenant_id = tenant_id
    integration.business_central_environment_name = environment_name.strip()
    integration.business_central_company_id = company["id"]
    integration.business_central_company_name = company["display_name"]
    integration.status = "active"
    await session.commit()
    await session.refresh(integration)
    return company
