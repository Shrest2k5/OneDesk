from typing import Any, Dict, List, Optional
from app.integrations.zoho.client import ZohoClient
from app.integrations.zoho.schemas.crm import (
    PaginatedLeadsResponse,
    PaginationInfo,
    ZohoLead,
)


class ZohoLeadsService:
    """Service handling Zoho CRM Leads retrieval, pagination, and data normalization."""

    def __init__(self, client: ZohoClient) -> None:
        self.client = client

    @staticmethod
    def _normalize_lead(item: Dict[str, Any]) -> ZohoLead:
        """Map raw Zoho CRM lead payload to normalized ZohoLead schema."""
        owner_info = item.get("Owner")
        owner = owner_info.get("name") if isinstance(owner_info, dict) else owner_info
        return ZohoLead(
            id=str(item.get("id")),
            first_name=item.get("First_Name"),
            last_name=item.get("Last_Name"),
            company=item.get("Company"),
            email=item.get("Email"),
            phone=item.get("Phone"),
            lead_source=item.get("Lead_Source"),
            lead_status=item.get("Lead_Status"),
            owner=owner,
            created_time=item.get("Created_Time"),
            modified_time=item.get("Modified_Time"),
            raw_data=item,
        )

    async def list_leads(
        self,
        page: int = 1,
        per_page: int = 200,
        fields: Optional[List[str]] = None,
        modified_since: Optional[str] = None,
    ) -> PaginatedLeadsResponse:
        """Fetch a paginated list of leads from Zoho CRM."""
        result = await self.client.fetch_records(
            module="Leads",
            page=page,
            per_page=per_page,
            fields=fields,
            modified_since=modified_since,
        )

        raw_items = result.get("data", [])
        leads = [self._normalize_lead(item) for item in raw_items]

        info_dict = result.get("info", {})
        pagination = PaginationInfo(
            page=info_dict.get("page", page),
            per_page=info_dict.get("per_page", per_page),
            count=info_dict.get("count", len(leads)),
            more_records=info_dict.get("more_records", False),
        )

        return PaginatedLeadsResponse(data=leads, pagination=pagination)

    async def get_lead(
        self,
        lead_id: str,
        fields: Optional[List[str]] = None,
    ) -> ZohoLead:
        """Retrieve an individual lead by Zoho record ID."""
        result = await self.client.get_record(
            module="Leads",
            record_id=lead_id,
            fields=fields,
        )

        data = result.get("data", [])
        if not data:
            from app.integrations.zoho.exceptions import ZohoAPIError
            raise ZohoAPIError(f"Lead with ID '{lead_id}' not found.", status_code=404)

        return self._normalize_lead(data[0])

