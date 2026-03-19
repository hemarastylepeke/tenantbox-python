"""
Tenantbox SDK — HTTP Layer.

Wraps requests with auth, error mapping, and response parsing.
All API communication goes through this module.
"""

import mimetypes
import os
from typing import Any, Dict, Optional

import requests
from requests import Response

from .exceptions import (
    QuotaExceededError,
    TenantboxAPIError,
    TenantboxAuthError,
    TenantboxNotFoundError,
    TenantboxUploadError,
)

DEFAULT_BASE_URL = "https://api.tenantbox.dev"
DEFAULT_TIMEOUT = 30  # seconds


class HttpClient:
    """
    Thin HTTP client used internally by TenantboxClient.
    Handles auth headers, response parsing, and error mapping.
    """

    def __init__(self, api_key: str, base_url: str, timeout: int):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "tenantbox-python-sdk/0.1.0",
        })

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _handle_response(self, response: Response) -> Dict[str, Any]:
        """Parse response and raise typed exceptions for error status codes."""
        if response.status_code == 401:
            raise TenantboxAuthError(
                "Invalid or inactive API key. Check your TENANTBOX_API_KEY.",
                status_code=401,
            )

        if response.status_code == 403:
            try:
                detail = response.json().get("detail", "Quota exceeded.")
            except Exception:
                detail = "Tenant has exceeded storage quota."
            raise QuotaExceededError(detail, status_code=403)

        if response.status_code == 404:
            try:
                detail = response.json().get("detail", "Resource not found.")
            except Exception:
                detail = "Resource not found."
            raise TenantboxNotFoundError(detail, status_code=404)

        if response.status_code >= 400:
            try:
                body = response.json()
                detail = body.get("detail", str(body))
            except Exception:
                detail = response.text or "Unknown error."
            raise TenantboxAPIError(
                f"API error {response.status_code}: {detail}",
                status_code=response.status_code,
                response={"detail": detail},
            )

        try:
            return response.json()
        except Exception:
            # Some endpoints (e.g. 204 No Content) may return no body
            return {}

    def get(self, path: str, **kwargs) -> Dict[str, Any]:
        response = self._session.get(
            self._url(path), timeout=self.timeout, **kwargs
        )
        return self._handle_response(response)

    def post(self, path: str, json: Dict = None, **kwargs) -> Dict[str, Any]:
        response = self._session.post(
            self._url(path), json=json, timeout=self.timeout, **kwargs
        )
        return self._handle_response(response)

    def delete(self, path: str, json: Dict = None, **kwargs) -> Dict[str, Any]:
        response = self._session.delete(
            self._url(path), json=json, timeout=self.timeout, **kwargs
        )
        return self._handle_response(response)

    def patch(self, path: str, json: Dict = None, **kwargs) -> Dict[str, Any]:
        response = self._session.patch(
            self._url(path), json=json, timeout=self.timeout, **kwargs
        )
        return self._handle_response(response)

    def put_to_presigned_url(
        self,
        presigned_url: str,
        data: Any,
        content_type: str,
        timeout: int = None,
    ) -> None:
        """
        Upload file bytes directly to Storage/R2 via presigned URL.
        This request does NOT go through Tenantbox — it goes straight to Storage/R2.
        """
        headers = {"Content-Type": content_type}
        response = requests.put(
            presigned_url,
            data=data,
            headers=headers,
            timeout=timeout or self.timeout,
        )
        if response.status_code not in (200, 204):
            raise TenantboxUploadError(
                f"Direct upload to storage failed with status {response.status_code}: {response.text}",
                status_code=response.status_code,
            )


def resolve_content_type(filename: str, provided: Optional[str] = None) -> str:
    """Resolve MIME type from provided value or filename extension."""
    if provided:
        return provided
    content_type, _ = mimetypes.guess_type(filename)
    return content_type or "application/octet-stream"


def resolve_filename(file_path_or_obj: Any, provided: Optional[str] = None) -> str:
    """Derive filename from a path string, file object, or explicit override."""
    if provided:
        return provided
    if isinstance(file_path_or_obj, str):
        return os.path.basename(file_path_or_obj)
    if hasattr(file_path_or_obj, "name"):
        return os.path.basename(file_path_or_obj.name)
    return "upload"