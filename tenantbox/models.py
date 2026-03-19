"""
Tenantbox SDK Response Models.

Simple dataclasses that represent API responses. These give developers
IDE autocompletion and make responses predictable instead of raw dicts.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class UploadURLResult:
    """
    Returned by client.get_upload_url().

    presigned_url: The URL your frontend/client should PUT the file to directly.
    file_path:     The Storage/R2 path — save this to your database to reference the file later.
    expires_in:    Seconds until the presigned URL expires (default 3600).
    tenant_id:     The external tenant ID provided in the request.
    is_new_tenant: True if Tenantbox auto-created this tenant on first upload.
    """
    presigned_url: str
    file_path: str
    expires_in: int
    tenant_id: str
    is_new_tenant: bool


@dataclass
class UploadResult:
    """
    Returned by client.upload_file().

    Same fields as UploadURLResult, plus confirmation that the upload succeeded.
    file_path is what you must save to your database.
    """
    presigned_url: str
    file_path: str
    expires_in: int
    tenant_id: str
    is_new_tenant: bool
    uploaded: bool = True  # Always True — exception raised if upload fails


@dataclass
class DownloadURLResult:
    """
    Returned by client.get_download_url().

    download_url: Presigned URL the client uses to download the file directly from Storage/R2.
    filename:     Original filename.
    content_type: MIME type of the file.
    size_bytes:   File size in bytes.
    expires_in:   Seconds until the download URL expires.
    """
    download_url: str
    filename: str
    content_type: str
    size_bytes: int
    expires_in: int


@dataclass
class TenantUsage:
    """
    Returned by client.get_usage().

    tenant_id:            The external tenant ID.
    email:                Optional email if provided at upload time.
    storage_used_bytes:   Total bytes used by this tenant.
    storage_limit_bytes:  Quota ceiling in bytes. None means unlimited.
    total_files:          Number of files stored for this tenant.
    storage_used_mb:      Convenience property — usage in megabytes.
    storage_limit_mb:     Convenience property — limit in megabytes. None if unlimited.
    """
    tenant_id: str
    storage_used_bytes: int
    total_files: int
    email: Optional[str] = None
    storage_limit_bytes: Optional[int] = None

    @property
    def storage_used_mb(self) -> float:
        return round(self.storage_used_bytes / (1024 * 1024), 3)

    @property
    def storage_limit_mb(self) -> Optional[float]:
        if self.storage_limit_bytes is None:
            return None
        return round(self.storage_limit_bytes / (1024 * 1024), 3)

    @property
    def is_unlimited(self) -> bool:
        return self.storage_limit_bytes is None

    @property
    def usage_percentage(self) -> Optional[float]:
        """Returns 0–100 percentage of quota used, or None if unlimited."""
        if self.storage_limit_bytes is None or self.storage_limit_bytes == 0:
            return None
        return round((self.storage_used_bytes / self.storage_limit_bytes) * 100, 2)


@dataclass
class StorageLimitResult:
    """
    Returned by client.set_limit() and client.remove_limit().

    tenant_id:            The external tenant ID that was updated.
    storage_limit_bytes:  The new limit. None means unlimited (limit was removed).
    detail:               Human-readable confirmation message from the API.
    """
    tenant_id: str
    storage_limit_bytes: Optional[int]
    detail: str

    @property
    def is_unlimited(self) -> bool:
        return self.storage_limit_bytes is None


@dataclass
class DeleteResult:
    """
    Returned by client.delete_file().

    detail: Confirmation message from the API.
    """
    detail: str
    success: bool = True