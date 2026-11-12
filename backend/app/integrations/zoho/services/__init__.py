"""Zoho CRM resource services."""
from app.integrations.zoho.services.accounts import ZohoAccountsService
from app.integrations.zoho.services.contacts import ZohoContactsService
from app.integrations.zoho.services.deals import ZohoDealsService
from app.integrations.zoho.services.leads import ZohoLeadsService

__all__ = [
    "ZohoContactsService",
    "ZohoLeadsService",
    "ZohoDealsService",
    "ZohoAccountsService",
]

