from datetime import datetime
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.core.logging import logger
from app.integrations.zoho.exceptions import ZohoOAuthError
from app.integrations.zoho.integration import zoho_integration
from app.models.user import User

router = APIRouter(prefix="/integrations/zoho", tags=["Zoho Integration"])


# --- Schemas ---
class ZohoConnectRequest(BaseModel):
    connection_name: str = Field(
        default="My Zoho CRM",
        min_length=1,
        max_length=100,
        description="Friendly connection label",
    )
    data_center: str = Field(
        default="us",
        pattern="^(us|eu|in|cn|au|ca|jp)$",
        description="Zoho data center: us, eu, in, cn, au, ca, jp",
    )


class ZohoConnectResponse(BaseModel):
    authorization_url: str
    state: str
    data_center: str


class ZohoCallbackResponse(BaseModel):
    message: str
    integration_id: uuid.UUID
    connection_name: str
    provider: str
    status: str
    api_domain: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Endpoints ---
@router.post(
    "/connect",
    response_model=ZohoConnectResponse,
    status_code=status.HTTP_200_OK,
    summary="Initiate Zoho CRM OAuth 2.0 connection",
)
async def initiate_zoho_connect(
    request: ZohoConnectRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Generate Zoho OAuth 2.0 authorization URL and CSRF state parameter.
    Redirect the user to the returned authorization URL to authorize access.
    """
    auth_data = zoho_integration.generate_authorization_url(
        user_id=current_user.id,
        connection_name=request.connection_name,
        data_center=request.data_center,
    )
    return ZohoConnectResponse(
        authorization_url=auth_data["authorization_url"],
        state=auth_data["state"],
        data_center=auth_data["data_center"],
    )


@router.get(
    "/callback",
    response_model=ZohoCallbackResponse,
    status_code=status.HTTP_200_OK,
    summary="Handle Zoho OAuth 2.0 redirect callback",
)
async def handle_zoho_callback(
    code: Optional[str] = Query(None, description="Authorization code from Zoho"),
    state: Optional[str] = Query(None, description="CSRF state parameter"),
    error: Optional[str] = Query(None, description="Error code if user denied authorization"),
    session: AsyncSession = Depends(get_db),
):
    """
    Handle the OAuth redirect callback from Zoho Accounts.
    Validates state parameter, exchanges authorization code for tokens,
    and records the connection.
    """
    if error:
        logger.warning(f"Zoho OAuth callback received error: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Zoho authorization was denied or failed: {error}",
        )

    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required OAuth 'code' or 'state' parameters.",
        )

    try:
        integration = await zoho_integration.handle_oauth_callback(
            code=code,
            state=state,
            session=session,
        )
    except ZohoOAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return ZohoCallbackResponse(
        message="Zoho CRM connection established successfully.",
        integration_id=integration.id,
        connection_name=integration.connection_name,
        provider=integration.provider,
        status=integration.status,
        api_domain=integration.api_domain,
        created_at=integration.created_at,
    )

