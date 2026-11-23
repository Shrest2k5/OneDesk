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
    """External Odoo 20 JSON-2 connection lifecycle; no resource synchronization."""

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

    async def fetch_records(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        integration: Integration = kwargs["integration"]
        resource_type = kwargs.get("resource_type", "contacts")
        page = max(1, int(kwargs.get("page", 1)))
        per_page = max(1, min(int(kwargs.get("per_page", 200)), 500))
        if resource_type not in {"contacts", "customers", "vendors"}:
            raise ValueError(f"Odoo synchronization does not support resource '{resource_type}'")

        domain = []
        if resource_type == "customers":
            domain = [["customer_rank", ">", 0]]
        elif resource_type == "vendors":
            domain = [["supplier_rank", ">", 0]]
        fields = [
            "id", "name", "display_name", "active", "is_company", "type", "parent_id",
            "commercial_partner_id", "email", "phone", "mobile", "street", "street2",
            "city", "zip", "state_id", "country_id", "customer_rank", "supplier_rank",
            "company_type", "comment", "create_date", "write_date",
        ]
        client = OdooClient(integration.api_domain or "", integration.access_token or "", integration.external_database)
        items = await client.search_read_partners(domain, (page - 1) * per_page, per_page, fields)
        normalized = [self.normalize_partner(item) for item in items]
        return {
            "data": normalized,
            "info": {"more_records": len(items) == per_page},
        }

    @staticmethod
    def _many2one(value: Any) -> Optional[Dict[str, Any]]:
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return {"id": value[0], "name": value[1]}
        return None

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

    async def get_record(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        raise NotImplementedError("Odoo resource synchronization is not implemented in Milestone 2.")


odoo_integration = OdooIntegration()
integration_registry.register(odoo_integration)
