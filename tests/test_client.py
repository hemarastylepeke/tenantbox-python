"""
Tenantbox SDK Test Suite.

Run with: pytest tests/ -v

Uses `responses` library to mock HTTP without hitting the real API.
Install dev dependencies: pip install tenantbox[dev]
"""

import io
import pytest
import responses as responses_lib

from tenantbox import TenantboxClient
from tenantbox.exceptions import (
    QuotaExceededError,
    TenantboxAuthError,
    TenantboxConfigError,
    TenantboxNotFoundError,
)
from tenantbox.utils import MB, GB, KB, human_readable_bytes

BASE_URL = "https://api.tenantbox.dev"
API_KEY = "tbx_test_key"


@pytest.fixture
def client():
    return TenantboxClient(api_key=API_KEY, base_url=BASE_URL)


# ------------------------------------------------------------------
# Initialization
# ------------------------------------------------------------------

class TestClientInit:
    def test_raises_without_api_key(self):
        with pytest.raises(TenantboxConfigError, match="No API key"):
            TenantboxClient(api_key=None)

    def test_reads_from_environment(self, monkeypatch):
        monkeypatch.setenv("TENANTBOX_API_KEY", "tbx_from_env")
        c = TenantboxClient()
        assert c is not None

    def test_raises_empty_base_url(self):
        with pytest.raises(TenantboxConfigError):
            TenantboxClient(api_key=API_KEY, base_url="")


# ------------------------------------------------------------------
# get_upload_url
# ------------------------------------------------------------------

class TestGetUploadUrl:
    UPLOAD_RESPONSE = {
        "presigned_url": "https://r2.example.com/upload?sig=abc",
        "file_path": "projects/proj-1/tenants/t-1/abc_avatar.png",
        "expires_in": 3600,
        "tenant_id": "user_123",
        "is_new_tenant": True,
    }

    @responses_lib.activate
    def test_returns_upload_url_result(self, client):
        responses_lib.add(
            responses_lib.POST,
            f"{BASE_URL}/api/storage/upload/",
            json=self.UPLOAD_RESPONSE,
            status=200,
        )
        result = client.get_upload_url(tenant_id="user_123", filename="avatar.png")
        assert result.presigned_url == self.UPLOAD_RESPONSE["presigned_url"]
        assert result.file_path == self.UPLOAD_RESPONSE["file_path"]
        assert result.tenant_id == "user_123"
        assert result.is_new_tenant is True

    @responses_lib.activate
    def test_raises_quota_exceeded(self, client):
        responses_lib.add(
            responses_lib.POST,
            f"{BASE_URL}/api/storage/upload/",
            json={"detail": "Tenant has exceeded storage quota"},
            status=403,
        )
        with pytest.raises(QuotaExceededError):
            client.get_upload_url(tenant_id="user_123", filename="file.txt")

    @responses_lib.activate
    def test_raises_auth_error(self, client):
        responses_lib.add(
            responses_lib.POST,
            f"{BASE_URL}/api/storage/upload/",
            json={"detail": "Unauthorized"},
            status=401,
        )
        with pytest.raises(TenantboxAuthError):
            client.get_upload_url(tenant_id="user_123", filename="file.txt")

    @responses_lib.activate
    def test_auto_detects_content_type(self, client):
        responses_lib.add(
            responses_lib.POST,
            f"{BASE_URL}/api/storage/upload/",
            json=self.UPLOAD_RESPONSE,
            status=200,
        )
        client.get_upload_url(tenant_id="user_123", filename="avatar.png")
        request_body = responses_lib.calls[0].request.body
        if isinstance(request_body, bytes):
            request_body = request_body.decode("utf-8")
        assert "image/png" in request_body


# ------------------------------------------------------------------
# upload_file
# ------------------------------------------------------------------

class TestUploadFile:
    UPLOAD_RESPONSE = {
        "presigned_url": "https://r2.example.com/upload?sig=abc",
        "file_path": "projects/proj-1/tenants/t-1/abc_report.pdf",
        "expires_in": 3600,
        "tenant_id": "user_123",
        "is_new_tenant": False,
    }

    @responses_lib.activate
    def test_uploads_file_object(self, client):
        responses_lib.add(
            responses_lib.POST,
            f"{BASE_URL}/api/storage/upload/",
            json=self.UPLOAD_RESPONSE,
            status=200,
        )
        responses_lib.add(
            responses_lib.PUT,
            "https://r2.example.com/upload",
            status=200,
        )
        buf = io.BytesIO(b"PDF content here")
        buf.name = "report.pdf"
        result = client.upload_file(tenant_id="user_123", file_path_or_obj=buf)
        assert result.uploaded is True
        assert result.file_path == self.UPLOAD_RESPONSE["file_path"]


# ------------------------------------------------------------------
# get_download_url
# ------------------------------------------------------------------

class TestGetDownloadUrl:
    @responses_lib.activate
    def test_returns_download_url(self, client):
        responses_lib.add(
            responses_lib.POST,
            f"{BASE_URL}/api/storage/download/",
            json={
                "download_url": "https://r2.example.com/dl?sig=xyz",
                "filename": "report.pdf",
                "content_type": "application/pdf",
                "size_bytes": 204800,
                "expires_in": 3600,
            },
            status=200,
        )
        result = client.get_download_url("projects/proj-1/.../report.pdf")
        assert "r2.example.com" in result.download_url
        assert result.filename == "report.pdf"

    @responses_lib.activate
    def test_raises_not_found(self, client):
        responses_lib.add(
            responses_lib.POST,
            f"{BASE_URL}/api/storage/download/",
            json={"detail": "File not found"},
            status=404,
        )
        with pytest.raises(TenantboxNotFoundError):
            client.get_download_url("nonexistent/path.pdf")


# ------------------------------------------------------------------
# delete_file
# ------------------------------------------------------------------

class TestDeleteFile:
    @responses_lib.activate
    def test_deletes_file(self, client):
        responses_lib.add(
            responses_lib.DELETE,
            f"{BASE_URL}/api/storage/files/",
            json={"detail": "File deleted successfully"},
            status=200,
        )
        result = client.delete_file("projects/proj-1/.../file.pdf")
        assert result.success is True

    @responses_lib.activate
    def test_raises_not_found(self, client):
        responses_lib.add(
            responses_lib.DELETE,
            f"{BASE_URL}/api/storage/files/",
            json={"detail": "File not found"},
            status=404,
        )
        with pytest.raises(TenantboxNotFoundError):
            client.delete_file("nonexistent/path.pdf")


# ------------------------------------------------------------------
# get_usage
# ------------------------------------------------------------------

class TestGetUsage:
    @responses_lib.activate
    def test_returns_usage(self, client):
        responses_lib.add(
            responses_lib.GET,
            f"{BASE_URL}/api/storage/tenants/user_123/usage/",
            json={
                "tenant_id": "user_123",
                "email": "alice@example.com",
                "storage_used_bytes": MB(50),
                "storage_limit_bytes": MB(100),
                "total_files": 12,
            },
            status=200,
        )
        usage = client.get_usage("user_123")
        assert usage.storage_used_mb == 50.0
        assert usage.storage_limit_mb == 100.0
        assert usage.usage_percentage == 50.0
        assert usage.is_unlimited is False
        assert usage.total_files == 12

    @responses_lib.activate
    def test_unlimited_tenant(self, client):
        responses_lib.add(
            responses_lib.GET,
            f"{BASE_URL}/api/storage/tenants/user_456/usage/",
            json={
                "tenant_id": "user_456",
                "email": None,
                "storage_used_bytes": MB(10),
                "storage_limit_bytes": None,
                "total_files": 3,
            },
            status=200,
        )
        usage = client.get_usage("user_456")
        assert usage.is_unlimited is True
        assert usage.usage_percentage is None
        assert usage.storage_limit_mb is None


# ------------------------------------------------------------------
# set_limit / remove_limit
# ------------------------------------------------------------------

class TestStorageLimits:
    @responses_lib.activate
    def test_set_limit(self, client):
        responses_lib.add(
            responses_lib.PATCH,
            f"{BASE_URL}/api/storage/tenants/user_123/limit/",
            json={
                "tenant_id": "user_123",
                "storage_limit_bytes": GB(1),
                "detail": "Storage limit updated",
            },
            status=200,
        )
        result = client.set_limit("user_123", GB(1))
        assert result.storage_limit_bytes == GB(1)
        assert result.is_unlimited is False

    @responses_lib.activate
    def test_remove_limit(self, client):
        responses_lib.add(
            responses_lib.PATCH,
            f"{BASE_URL}/api/storage/tenants/user_123/limit/",
            json={
                "tenant_id": "user_123",
                "storage_limit_bytes": None,
                "detail": "Storage limit removed",
            },
            status=200,
        )
        result = client.remove_limit("user_123")
        assert result.storage_limit_bytes is None
        assert result.is_unlimited is True


# ------------------------------------------------------------------
# Utils
# ------------------------------------------------------------------

class TestUtils:
    def test_kb(self):
        assert KB(1) == 1024

    def test_mb(self):
        assert MB(1) == 1024 * 1024

    def test_gb(self):
        assert GB(1) == 1024 * 1024 * 1024

    def test_human_readable(self):
        assert human_readable_bytes(1024) == "1.0 KB"
        assert human_readable_bytes(MB(5)) == "5.0 MB"
        assert human_readable_bytes(GB(2)) == "2.0 GB"
        assert human_readable_bytes(500) == "500.0 B"