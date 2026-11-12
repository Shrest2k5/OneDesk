from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import Integration


class BaseERPIntegration(ABC):
    """
    Abstract Base Class defining the unified interface for all external ERP integrations
    (Zoho, Odoo, SAP, etc.).
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider identifier (e.g. 'zoho', 'odoo', 'sap')."""
        pass

    @abstractmethod
    def generate_authorization_url(
        self,
        user_id: uuid.UUID,
        connection_name: str,
        data_center: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, str]:
        """
        Generate OAuth authorization URL and secure state for external authentication.
        Returns a dict containing 'authorization_url' and 'state'.
        """
        pass

    @abstractmethod
    async def handle_oauth_callback(
        self,
        code: str,
        state: str,
        session: AsyncSession,
    ) -> Integration:
        """
        Handle OAuth callback by validating state, exchanging auth code for tokens,
        and persisting or updating the Integration record.
        """
        pass

    @abstractmethod
    async def refresh_access_token(
        self,
        integration: Integration,
        session: AsyncSession,
    ) -> Integration:
        """
        Refresh expired access token using the stored refresh token.
        Updates the integration instance and database.
        """
        pass

    @abstractmethod
    async def get_connection_status(
        self,
        integration: Integration,
        session: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Validate active connection status against the remote ERP API.
        """
        pass

    @abstractmethod
    async def fetch_records(
        self,
        integration: Integration,
        resource_type: str,
        page: int = 1,
        per_page: int = 200,
        fields: Optional[List[str]] = None,
        modified_since: Optional[str] = None,
        session: Optional[AsyncSession] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Fetch a paginated list of CRM/ERP records (contacts, leads, deals, accounts).
        """
        pass

    @abstractmethod
    async def get_record(
        self,
        integration: Integration,
        resource_type: str,
        record_id: str,
        fields: Optional[List[str]] = None,
        session: Optional[AsyncSession] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Retrieve a single ERP record by external identifier.
        """
        pass

