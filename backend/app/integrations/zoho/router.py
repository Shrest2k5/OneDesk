from typing import Optional
from urllib.parse import urlencode
import uuid
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.core.config import settings
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
    data_center: Optional[str] = Field(
        default=None,
        pattern="^(us|eu|in|cn|au|ca|jp)$",
        description="Zoho data center: us, eu, in, cn, au, ca, jp. Defaults to configured accounts URL or 'in'",
    )


class ZohoConnectResponse(BaseModel):
    authorization_url: str
    state: str
    data_center: str


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
    def frontend_callback_redirect(callback_status: str, integration_id: Optional[uuid.UUID] = None) -> RedirectResponse:
        """Return users to the SPA without forwarding provider credentials or errors."""
        query = {"status": callback_status}
        if integration_id:
            query["integration_id"] = str(integration_id)
        location = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/integrations/zoho/callback?{urlencode(query)}"
        return RedirectResponse(url=location, status_code=status.HTTP_303_SEE_OTHER)

    if error:
        logger.warning(f"Zoho OAuth callback received error: {error}")
        return frontend_callback_redirect("error")

    if not code or not state:
        logger.warning("Zoho OAuth callback missing required code or state parameter")
        return frontend_callback_redirect("error")

    try:
        integration = await zoho_integration.handle_oauth_callback(
            code=code,
            state=state,
            session=session,
        )
    except ZohoOAuthError as exc:
        # Do not reflect token/state validation details to the browser. They can
        # reveal OAuth flow information and are not actionable in the SPA.
        logger.warning(f"Zoho OAuth callback failed: {exc}")
        return frontend_callback_redirect("error")
    except Exception:
        # Token exchange and persistence failures must return the user to the SPA
        # without exposing provider responses, codes, or internal details.
        logger.exception("Unexpected Zoho OAuth callback failure")
        return frontend_callback_redirect("error")

    return frontend_callback_redirect("success", integration.id)

