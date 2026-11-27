from typing import Any, Optional


class BusinessCentralOAuthError(Exception):
    """Safe, provider-specific OAuth failure."""

    def __init__(self, message: str, status_code: Optional[int] = None, details: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details or {}


class BusinessCentralTokenExpiredError(BusinessCentralOAuthError):
    """The stored refresh credential cannot be used anymore."""
