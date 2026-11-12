from typing import Any, Dict, List, Optional
from app.integrations.zoho.client import ZohoClient
from app.integrations.zoho.schemas.crm import (
    PaginatedContactsResponse,
    PaginationInfo,
    ZohoContact,
)


class ZohoContactsService:
    """Service handling Zoho CRM Contacts retrieval, pagination, and data normalization."""

    def __init__(self, client: ZohoClient) -> None:
        self.client = client

    @staticmethod
    def _normalize_contact(item: Dict[str, Any]) -> ZohoContact:
        """Map raw Zoho CRM contact payload to normalized ZohoContact schema."""
        account_info = item.get("Account_Name")
        account_name = None
        if isinstance(account_info, dict):
            account_name = account_info.get("name")
        elif isinstance(account_info, str):
            account_name = account_info

        return ZohoContact(
            id=str(item.get("id")),
            first_name=item.get("First_Name"),
            last_name=item.get("Last_Name") or "Unknown",
            email=item.get("Email"),
            phone=item.get("Phone") or item.get("Mobile"),
            account_name=account_name,
            created_time=item.get("Created_Time"),
            modified_time=item.get("Modified_Time"),
            raw_data=item,
        )

    async def list_contacts(
        self,
        page: int = 1,
        per_page: int = 200,
        fields: Optional[List[str]] = None,
        modified_since: Optional[str] = None,
    ) -> PaginatedContactsResponse:
        """Fetch a paginated list of contacts from Zoho CRM."""
        result = await self.client.fetch_records(
            module="Contacts",
            page=page,
            per_page=per_page,
            fields=fields,
            modified_since=modified_since,
        )

        raw_items = result.get("data", [])
        contacts = [self._normalize_contact(item) for item in raw_items]

        info_dict = result.get("info", {})
        pagination = PaginationInfo(
            page=info_dict.get("page", page),
            per_page=info_dict.get("per_page", per_page),
            count=info_dict.get("count", len(contacts)),
            more_records=info_dict.get("more_records", False),
        )

        return PaginatedContactsResponse(data=contacts, pagination=pagination)

    async def get_contact(
        self,
        contact_id: str,
        fields: Optional[List[str]] = None,
    ) -> ZohoContact:
        """Retrieve a single contact by Zoho record ID."""
        result = await self.client.get_record(
            module="Contacts",
            record_id=contact_id,
            fields=fields,
        )

        data = result.get("data", [])
        if not data:
            from app.integrations.zoho.exceptions import ZohoAPIError
            raise ZohoAPIError(f"Contact with ID '{contact_id}' not found.", status_code=404)

        return self._normalize_contact(data[0])

