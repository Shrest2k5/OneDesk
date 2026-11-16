from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PaginationInfo(BaseModel):
    page: int = 1
    per_page: int = 200
    count: int = 0
    more_records: bool = False


# --- CRM Models ---
class ZohoContact(BaseModel):
    id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    account_name: Optional[str] = None
    owner: Optional[str] = None
    created_time: Optional[str] = None
    modified_time: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class ZohoLead(BaseModel):
    id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    lead_source: Optional[str] = None
    lead_status: Optional[str] = None
    owner: Optional[str] = None
    created_time: Optional[str] = None
    modified_time: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class ZohoDeal(BaseModel):
    id: str
    deal_name: str
    amount: Optional[float] = None
    currency: Optional[str] = None
    stage: Optional[str] = None
    closing_date: Optional[str] = None
    probability: Optional[float] = None
    account_name: Optional[str] = None
    owner: Optional[str] = None
    created_time: Optional[str] = None
    modified_time: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class ZohoAccount(BaseModel):
    id: str
    account_name: str
    phone: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    account_type: Optional[str] = None
    billing_city: Optional[str] = None
    billing_country: Optional[str] = None
    owner: Optional[str] = None
    created_time: Optional[str] = None
    modified_time: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


# --- Paginated Responses ---
class PaginatedContactsResponse(BaseModel):
    data: List[ZohoContact]
    pagination: PaginationInfo


class PaginatedLeadsResponse(BaseModel):
    data: List[ZohoLead]
    pagination: PaginationInfo


class PaginatedDealsResponse(BaseModel):
    data: List[ZohoDeal]
    pagination: PaginationInfo


class PaginatedAccountsResponse(BaseModel):
    data: List[ZohoAccount]
    pagination: PaginationInfo

