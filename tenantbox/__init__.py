"""
Tenantbox Python SDK.

Per-tenant file storage, quota enforcement, and usage tracking
for any Python application.

Quick start:
    from tenantbox import TenantboxClient

    client = TenantboxClient(api_key="tbx_your_key_here")

    # Or set TENANTBOX_API_KEY in your environment and omit api_key:
    client = TenantboxClient()

    # Always, __version__ must be similar to version = "0.1.0" in the pyproject.toml
    # To build for pipy, pip install build twine and then python -m build. Creates a dist folder with the distributables.
    # Test in a new environment twine upload --repository testpypi dist/*, then run python -c "from tenantbox import TenantboxClient; print('OK')"
    # If it prints ok, we are good to proceed.
    # Upload to pypi twine upload dist/*
"""

from .client import TenantboxClient
from .exceptions import (
    QuotaExceededError,
    TenantboxAPIError,
    TenantboxAuthError,
    TenantboxConfigError,
    TenantboxError,
    TenantboxNotFoundError,
    TenantboxUploadError,
)
from .models import (
    DeleteResult,
    DownloadURLResult,
    StorageLimitResult,
    TenantUsage,
    UploadResult,
    UploadURLResult,
)
from .utils import GB, KB, MB, TB, human_readable_bytes

__version__ = "0.1.0"
__author__ = "Tenantbox"
__all__ = [
    # Client
    "TenantboxClient",
    # Exceptions
    "TenantboxError",
    "TenantboxAuthError",
    "TenantboxConfigError",
    "TenantboxAPIError",
    "TenantboxNotFoundError",
    "TenantboxUploadError",
    "QuotaExceededError",
    # Models
    "UploadURLResult",
    "UploadResult",
    "DownloadURLResult",
    "TenantUsage",
    "StorageLimitResult",
    "DeleteResult",
    # Utils
    "KB",
    "MB",
    "GB",
    "TB",
    "human_readable_bytes",
]