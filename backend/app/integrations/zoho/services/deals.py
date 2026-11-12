from typing import Any, Dict, List, Optional
from app.integrations.zoho.client import ZohoClient
from app.integrations.zoho.schemas.crm import (
    PaginatedDealsResponse,
    PaginationInfo,
    ZohoDeal,
)


class ZohoDealsService:
    """Service handling Zoho CRM Deals (Potentials) retrieval, pagination, and data normalization."""

    def __init__(self, client: ZohoClient) -> None:
        self.client = client

    @staticmethod
    def _normalize_deal(item: Dict[str, Any]) -> ZohoDeal:
        """Map raw Zoho CRM deal payload to normalized ZohoDeal schema."""
        account_info = item.get("Account_Name")
        account_name = None
        if isinstance(account_info, dict):
            account_name = account_info.get("name")
        elif isinstance(account_info, str):
            account_name = account_info

        amount = item.get("Amount")
        parsed_amount = None
        if amount is not None:
            try:
                parsed_amount = float(amount)
            except (ValueError, TypeError):
                pass

        return ZohoDeal(
            id=str(item.get("id")),
            deal_name=item.get("Deal_Name") or "Unnamed Deal",
            amount=parsed_amount,
            stage=item.get("Stage"),
            closing_date=item.get("Closing_Date"),
            account_name=account_name,
            created_time=item.get("Created_Time"),
            modified_time=item.get("Modified_Time"),
            raw_data=item,
        )

    async def list_deals(
        self,
        page: int = 1,
        per_page: int = 200,
        fields: Optional[List[str]] = None,
        modified_since: Optional[str] = None,
    ) -> PaginatedDealsResponse:
        """Fetch a paginated list of deals from Zoho CRM."""
        result = await self.client.fetch_records(
            module="Deals",
            page=page,
            per_page=per_page,
            fields=fields,
            modified_since=modified_since,
        )

        raw_items = result.get("data", [])
        deals = [self._normalize_deal(item) for item in raw_items]

        info_dict = result.get("info", {})
        pagination = PaginationInfo(
            page=info_dict.get("page", page),
            per_page=info_dict.get("per_page", per_page),
            count=info_dict.get("count", len(deals)),
            more_records=info_dict.get("more_records", False),
        )

        return PaginatedDealsResponse(data=deals, pagination=pagination)

    async def get_deal(
        self,
        deal_id: str,
        fields: Optional[List[str]] = None,
    ) -> ZohoDeal:
        """Retrieve an individual deal by Zoho record ID."""
        result = await self.client.get_record(
            module="Deals",
            record_id=deal_id,
            fields=fields,
        )

        data = result.get("data", [])
        if not data:
            from app.integrations.zoho.exceptions import ZohoAPIError
            raise ZohoAPIError(f"Deal with ID '{deal_id}' not found.", status_code=404)

        return self._normalize_deal(data[0])

