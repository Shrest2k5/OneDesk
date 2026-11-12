from typing import Any, Dict, List, Optional
from app.integrations.zoho.client import ZohoClient
from app.integrations.zoho.schemas.crm import (
    PaginatedAccountsResponse,
    PaginationInfo,
    ZohoAccount,
)


class ZohoAccountsService:
    """Service handling Zoho CRM Accounts (Companies) retrieval, pagination, and data normalization."""

    def __init__(self, client: ZohoClient) -> None:
        self.client = client

    @staticmethod
    def _normalize_account(item: Dict[str, Any]) -> ZohoAccount:
        """Map raw Zoho CRM account payload to normalized ZohoAccount schema."""
        return ZohoAccount(
            id=str(item.get("id")),
            account_name=item.get("Account_Name") or "Unnamed Account",
            phone=item.get("Phone"),
            website=item.get("Website"),
            industry=item.get("Industry"),
            billing_city=item.get("Billing_City"),
            created_time=item.get("Created_Time"),
            modified_time=item.get("Modified_Time"),
            raw_data=item,
        )

    async def list_accounts(
        self,
        page: int = 1,
        per_page: int = 200,
        fields: Optional[List[str]] = None,
        modified_since: Optional[str] = None,
    ) -> PaginatedAccountsResponse:
        """Fetch a paginated list of accounts from Zoho CRM."""
        result = await self.client.fetch_records(
            module="Accounts",
            page=page,
            per_page=per_page,
            fields=fields,
            modified_since=modified_since,
        )

        raw_items = result.get("data", [])
        accounts = [self._normalize_account(item) for item in raw_items]

        info_dict = result.get("info", {})
        pagination = PaginationInfo(
            page=info_dict.get("page", page),
            per_page=info_dict.get("per_page", per_page),
            count=info_dict.get("count", len(accounts)),
            more_records=info_dict.get("more_records", False),
        )

        return PaginatedAccountsResponse(data=accounts, pagination=pagination)

    async def get_account(
        self,
        account_id: str,
        fields: Optional[List[str]] = None,
    ) -> ZohoAccount:
        """Retrieve an individual account by Zoho record ID."""
        result = await self.client.get_record(
            module="Accounts",
            record_id=account_id,
            fields=fields,
        )

        data = result.get("data", [])
        if not data:
            from app.integrations.zoho.exceptions import ZohoAPIError
            raise ZohoAPIError(f"Account with ID '{account_id}' not found.", status_code=404)

        return self._normalize_account(data[0])

