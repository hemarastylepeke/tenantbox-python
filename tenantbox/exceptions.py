"""
Tenantbox SDK Exceptions.

All exceptions raised by the SDK inherit from TenantboxError,
so callers can catch the base class or handle specific cases.
"""


class TenantboxError(Exception):
    """Base exception for all Tenantbox SDK errors."""

    def __init__(self, message: str, status_code: int = None, response: dict = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response = response or {}

    def __repr__(self):
        return f"{self.__class__.__name__}(message={self.message!r}, status_code={self.status_code})"


class TenantboxAuthError(TenantboxError):
    """
    Raised when the API key is missing, invalid, or inactive.
    HTTP 401 from the Tenantbox API.
    """
    pass


class QuotaExceededError(TenantboxError):
    """
    Raised when a tenant has exceeded their storage quota.
    HTTP 403 from the Tenantbox API.
    """
    pass


class TenantboxNotFoundError(TenantboxError):
    """
    Raised when a file or tenant is not found.
    HTTP 404 from the Tenantbox API.
    """
    pass


class TenantboxAPIError(TenantboxError):
    """
    Raised for unexpected API errors (5xx, malformed responses, etc.).
    """
    pass


class TenantboxUploadError(TenantboxError):
    """
    Raised when the direct-to-storage/R2 upload step fails after a presigned URL
    has been obtained successfully.
    """
    pass


class TenantboxConfigError(TenantboxError):
    """
    Raised for SDK misconfiguration (e.g. missing API key, bad base URL).
    """
    pass