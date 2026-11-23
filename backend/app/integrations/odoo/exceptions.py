from typing import Optional


class OdooIntegrationError(Exception):
    """Base error for Odoo connection and JSON-2 API failures."""

    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[dict] = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class OdooConfigurationError(OdooIntegrationError):
    """Invalid instance URL or connection configuration."""


class OdooAuthenticationError(OdooIntegrationError):
    """Invalid or unauthorized Odoo API key."""


class OdooPermissionError(OdooIntegrationError):
    """The authenticated Odoo user lacks access to the validation method."""


class OdooUnsupportedError(OdooIntegrationError):
    """The external deployment does not expose the required JSON-2 endpoint."""


class OdooConnectionError(OdooIntegrationError):
    """Network, timeout, or malformed-response failure."""
