from typing import Optional


class ZohoIntegrationError(Exception):
    """Base exception for all Zoho integration errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[dict] = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class ZohoOAuthError(ZohoIntegrationError):
    """Exception raised during Zoho OAuth authorization or token exchange."""
    pass


class ZohoTokenExpiredError(ZohoIntegrationError):
    """Exception raised when Zoho access token is expired or revoked."""
    pass


class ZohoRateLimitError(ZohoIntegrationError):
    """Exception raised when Zoho API rate limit is exceeded (HTTP 429)."""
    pass


class ZohoAPIError(ZohoIntegrationError):
    """Exception raised when Zoho CRM API returns an error response."""
    pass

