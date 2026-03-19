"""
Tenantbox SDK — Core Client.

TenantboxClient is the single entry point for all SDK operations.
It is framework-agnostic and works in any Python environment.

Quick start:
    from tenantbox import TenantboxClient

    client = TenantboxClient(api_key="tbx_your_key_here")

    # Get a presigned URL to hand to your frontend
    result = client.get_upload_url(tenant_id="user_123", filename="avatar.png")
    print(result.presigned_url)   # frontend uploads here directly
    print(result.file_path)       # save this to your DB

    # Or upload a file directly from the server (e.g. in a script)
    result = client.upload_file(tenant_id="user_123", file_path_or_obj="/tmp/report.pdf")
    print(result.file_path)

    # Download
    dl = client.get_download_url(file_path="projects/.../report.pdf")
    print(dl.download_url)

    # Usage
    usage = client.get_usage(tenant_id="user_123")
    print(usage.storage_used_mb)

    # Limits
    client.set_limit(tenant_id="user_123", storage_limit_bytes=100 * 1024 * 1024)  # 100 MB
    client.remove_limit(tenant_id="user_123")
"""

import os
from typing import Any, IO, Optional, Union

from .exceptions import TenantboxConfigError
from ._http import (
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    HttpClient,
    resolve_content_type,
    resolve_filename,
)
from .models import (
    DeleteResult,
    DownloadURLResult,
    StorageLimitResult,
    TenantUsage,
    UploadResult,
    UploadURLResult,
)


class TenantboxClient:
    """
    The Tenantbox Python SDK client.

    All methods map 1-to-1 to Tenantbox API endpoints, but return
    typed dataclasses instead of raw dicts, and raise typed exceptions
    instead of raw HTTP errors.

    Args:
        api_key:    Your Tenantbox project API key. If not provided, the
                    SDK will look for the TENANTBOX_API_KEY environment variable.
        base_url:   Override the API base URL (useful for self-hosted or testing).
        timeout:    HTTP request timeout in seconds. Default is 30.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        resolved_key = api_key or os.environ.get("TENANTBOX_API_KEY")
        if not resolved_key:
            raise TenantboxConfigError(
                "No API key provided. Pass api_key= to TenantboxClient() "
                "or set the TENANTBOX_API_KEY environment variable."
            )

        if not base_url:
            raise TenantboxConfigError("base_url cannot be empty.")

        self._http = HttpClient(
            api_key=resolved_key,
            base_url=base_url,
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def get_upload_url(
        self,
        tenant_id: str,
        filename: str,
        content_type: Optional[str] = None,
        tenant_email: Optional[str] = None,
    ) -> UploadURLResult:
        """
        Request a presigned upload URL from Tenantbox.

        Use this when your frontend will upload the file directly to Storage.
        The file never touches your server — only the URL request does.

        Args:
            tenant_id:     Your user/customer ID. Tenantbox auto-creates the
                           tenant on first upload if they don't exist yet.
            filename:      Original filename including extension (e.g. "avatar.png").
            content_type:  MIME type (e.g. "image/png"). Auto-detected from
                           filename if not provided.
            tenant_email:  Optional. Stored for display in the Tenantbox dashboard.

        Returns:
            UploadURLResult with presigned_url and file_path.
            Save file_path to your database — it's how you reference this file later.

        Raises:
            QuotaExceededError:    Tenant has exceeded their storage limit.
            TenantboxAuthError:    Invalid API key.
            TenantboxAPIError:     Unexpected API error.

        Example:
            result = client.get_upload_url(
                tenant_id="user_123",
                filename="contract.pdf",
                tenant_email="alice@example.com",
            )
            # Return result.presigned_url and result.file_path to your frontend
        """
        resolved_ct = resolve_content_type(filename, content_type)

        payload = {
            "tenant_id": tenant_id,
            "filename": filename,
            "content_type": resolved_ct,
        }
        if tenant_email:
            payload["tenant_email"] = tenant_email

        data = self._http.post("/api/storage/upload/", json=payload)

        return UploadURLResult(
            presigned_url=data["presigned_url"],
            file_path=data["file_path"],
            expires_in=data["expires_in"],
            tenant_id=data["tenant_id"],
            is_new_tenant=data["is_new_tenant"],
        )

    def upload_file(
        self,
        tenant_id: str,
        file_path_or_obj: Union[str, IO],
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
        tenant_email: Optional[str] = None,
        upload_timeout: int = 120,
    ) -> UploadResult:
        """
        Get a presigned URL AND upload the file to Storage in one call.

        Use this in server-side scripts, management commands, data pipelines,
        or anywhere your Python process has the file locally. The file still
        goes directly to Storage i.e R2 (not via Tenantbox backend), but the SDK handles
        the two-step flow for you.

        Args:
            tenant_id:      Your user/customer ID.
            file_path_or_obj: Either a file path string ("/tmp/report.pdf")
                              or any file-like object (open file, BytesIO, etc.).
            filename:       Override the filename. Auto-detected from path/object if omitted.
            content_type:   MIME type. Auto-detected from filename if omitted.
            tenant_email:   Optional. Stored in the Tenantbox dashboard.
            upload_timeout: Timeout in seconds for the direct R2 upload. Default 120.
                            Increase this for large files.

        Returns:
            UploadResult — same as UploadURLResult plus uploaded=True.
            Save file_path to your database.

        Raises:
            QuotaExceededError:    Tenant has exceeded their storage limit.
            TenantboxUploadError:  The presigned URL was obtained but the R2 upload failed.
            TenantboxAuthError:    Invalid API key.
            TenantboxAPIError:     Unexpected API error.
            FileNotFoundError:     file_path_or_obj string path does not exist.

        Example:
            # With a file path
            result = client.upload_file("user_123", "/tmp/exports/report.pdf")

            # With a file object (e.g. from a Django request)
            result = client.upload_file("user_123", request.FILES["document"])

            # With BytesIO
            import io
            buf = io.BytesIO(b"hello world")
            buf.name = "hello.txt"
            result = client.upload_file("user_123", buf)
        """
        resolved_filename = resolve_filename(file_path_or_obj, filename)
        resolved_ct = resolve_content_type(resolved_filename, content_type)

        # Step 1: Get presigned URL from Tenantbox
        url_result = self.get_upload_url(
            tenant_id=tenant_id,
            filename=resolved_filename,
            content_type=resolved_ct,
            tenant_email=tenant_email,
        )

        # Step 2: Upload directly to Storage
        if isinstance(file_path_or_obj, str):
            with open(file_path_or_obj, "rb") as f:
                self._http.put_to_presigned_url(
                    presigned_url=url_result.presigned_url,
                    data=f,
                    content_type=resolved_ct,
                    timeout=upload_timeout,
                )
        else:
            self._http.put_to_presigned_url(
                presigned_url=url_result.presigned_url,
                data=file_path_or_obj,
                content_type=resolved_ct,
                timeout=upload_timeout,
            )

        return UploadResult(
            presigned_url=url_result.presigned_url,
            file_path=url_result.file_path,
            expires_in=url_result.expires_in,
            tenant_id=url_result.tenant_id,
            is_new_tenant=url_result.is_new_tenant,
            uploaded=True,
        )

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def get_download_url(
        self,
        file_path: str,
        expires_in: int = 3600,
    ) -> DownloadURLResult:
        """
        Get a presigned download URL for a file.

        The file is served directly from Storage i.e R2 — it never passes through
        your server or Tenantbox.

        Args:
            file_path:  The file path returned at upload time (save this to your DB).
            expires_in: Seconds the download URL stays valid. Default 3600 (1 hour).

        Returns:
            DownloadURLResult with download_url, filename, content_type, size_bytes.

        Raises:
            TenantboxNotFoundError: File not found or upload was never confirmed.
            TenantboxAuthError:     Invalid API key.
            TenantboxAPIError:      Unexpected API error.

        Example:
            dl = client.get_download_url(file_path=document.file_path, expires_in=300)
            return redirect(dl.download_url)
        """
        payload = {"file_path": file_path, "expires_in": expires_in}
        data = self._http.post("/api/storage/download/", json=payload)

        return DownloadURLResult(
            download_url=data["download_url"],
            filename=data["filename"],
            content_type=data["content_type"],
            size_bytes=data["size_bytes"],
            expires_in=data["expires_in"],
        )

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_file(self, file_path: str) -> DeleteResult:
        """
        Delete a file from Storage and remove it from Tenantbox records.

        Storage usage for the tenant is automatically decremented.

        Args:
            file_path: The file path returned at upload time.

        Returns:
            DeleteResult with success=True and a detail message.

        Raises:
            TenantboxNotFoundError: File not found in this project.
            TenantboxAuthError:     Invalid API key.
            TenantboxAPIError:      Unexpected API error.

        Example:
            client.delete_file(file_path=document.file_path)
        """
        payload = {"file_path": file_path}
        data = self._http.delete("/api/storage/files/", json=payload)

        return DeleteResult(
            detail=data.get("detail", "File deleted successfully."),
            success=True,
        )

    # ------------------------------------------------------------------
    # Usage & Limits
    # ------------------------------------------------------------------

    def get_usage(self, tenant_id: str) -> TenantUsage:
        """
        Get current storage usage for a tenant.

        Args:
            tenant_id: Your user/customer ID.

        Returns:
            TenantUsage with storage_used_bytes, storage_limit_bytes,
            total_files, and convenience properties like storage_used_mb
            and usage_percentage.

        Raises:
            TenantboxNotFoundError: Tenant not found in this project.
            TenantboxAuthError:     Invalid API key.
            TenantboxAPIError:      Unexpected API error.

        Example:
            usage = client.get_usage("user_123")
            print(f"{usage.storage_used_mb} MB used of {usage.storage_limit_mb} MB")
            print(f"{usage.usage_percentage}% full")
        """
        data = self._http.get(f"/api/storage/tenants/{tenant_id}/usage/")

        return TenantUsage(
            tenant_id=data["tenant_id"],
            email=data.get("email"),
            storage_used_bytes=data["storage_used_bytes"],
            storage_limit_bytes=data.get("storage_limit_bytes"),
            total_files=data["total_files"],
        )

    def set_limit(
        self,
        tenant_id: str,
        storage_limit_bytes: int,
    ) -> StorageLimitResult:
        """
        Set a storage quota for a tenant.

        Args:
            tenant_id:            Your user/customer ID.
            storage_limit_bytes:  Maximum storage in bytes.
                                  Tip: use helper constants from tenantbox.utils
                                  e.g. MB(100) for 100 MB.

        Returns:
            StorageLimitResult confirming the new limit.

        Raises:
            TenantboxNotFoundError: Tenant not found.
            TenantboxAuthError:     Invalid API key.
            TenantboxAPIError:      Unexpected API error.

        Example:
            from tenantbox.utils import MB, GB
            client.set_limit("user_123", GB(1))   # 1 GB quota
            client.set_limit("user_123", MB(500))  # 500 MB quota
        """
        payload = {"storage_limit_bytes": storage_limit_bytes}
        data = self._http.patch(
            f"/api/storage/tenants/{tenant_id}/limit/", json=payload
        )

        return StorageLimitResult(
            tenant_id=data["tenant_id"],
            storage_limit_bytes=data["storage_limit_bytes"],
            detail=data.get("detail", "Storage limit updated."),
        )

    def remove_limit(self, tenant_id: str) -> StorageLimitResult:
        """
        Remove the storage quota for a tenant (makes storage unlimited).

        Args:
            tenant_id: Your user/customer ID.

        Returns:
            StorageLimitResult with storage_limit_bytes=None.

        Raises:
            TenantboxNotFoundError: Tenant not found.
            TenantboxAuthError:     Invalid API key.
            TenantboxAPIError:      Unexpected API error.
        Example:
            client.remove_limit("user_123")
        """
        payload = {"storage_limit_bytes": None}
        data = self._http.patch(
            f"/api/storage/tenants/{tenant_id}/limit/", json=payload
        )

        return StorageLimitResult(
            tenant_id=data["tenant_id"],
            storage_limit_bytes=data.get("storage_limit_bytes"),
            detail=data.get("detail", "Storage limit removed."),
        )