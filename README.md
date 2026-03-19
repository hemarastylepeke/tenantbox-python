# Tenantbox Python SDK

Per-tenant file storage, quota enforcement, and usage tracking for any Python application built on Tenantbox.

```bash
pip install tenantbox
```

---

## What is Tenantbox?

Tenantbox gives your application per-tenant file storage with quota enforcement and usage tracking in two API calls. Files are stored in Tenantbox Bucket and served via presigned URLs, files never pass through your backend server, so uploads are fast and your server doesn't time out.

---

## Quick Start

```python
from tenantbox import TenantboxClient

client = TenantboxClient(api_key="tbx_your_key_here")
```

Or set the `TENANTBOX_API_KEY` environment variable and omit the argument:

```python
client = TenantboxClient()
```

---

## Core Concepts

### The Two-Step Upload Pattern (Recommended)

For web applications, the correct pattern is:

1. **Your backend** calls `client.get_upload_url(...)` and returns the presigned URL to the frontend
2. **Your frontend** uploads directly to that URL - the file goes straight to Tenantbox storage, never through your server

```
Frontend ──── POST /your-api/upload-url ───► Django/Flask backend
                                                    │
                                                    ▼
                                            client.get_upload_url()
                                            (calls Tenantbox API)
                                                    │
                                            presigned_url + file_path
                                                    │
Frontend ◄──────────────────────────────────────────┘
    │
    └──── PUT file directly ────► Tenantbox storage
                                  (never touches your server)
```

This is why Tenantbox is faster than Django Storages + boto3, the file doesn't travel through your server twice.

---

## Upload

### `get_upload_url()` - For web apps (frontend uploads directly)

```python
result = client.get_upload_url(
    tenant_id="user_123",         # Your user/customer ID/email/username
    filename="avatar.png",
    content_type="image/png",     # Optional — auto-detected from filename
    tenant_email="alice@acme.com" # Optional — for dashboard display
)

result.presigned_url  # Give this to your frontend to PUT the file
result.file_path      # Save this to your database — you'll need it later
result.is_new_tenant  # True if this tenant was auto-created
result.expires_in     # Seconds until the URL expires (default 3600)
```

**Django Ninja example:**

```python
from ninja import Router
from tenantbox.django import get_client

router = Router()

@router.post("/upload-url/")
def upload_url(request, filename: str):
    client = get_client()
    result = client.get_upload_url(
        tenant_id=str(request.user.id),
        filename=filename,
        tenant_email=request.user.email,
    )
    return {
        "presigned_url": result.presigned_url,
        "file_path": result.file_path,
    }
```

**Django REST Framework example:**

```python
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from tenantbox.django import get_client

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_url(request):
    client = get_client()
    result = client.get_upload_url(
        tenant_id=str(request.user.id),
        filename=request.data["filename"],
    )
    return Response({
        "presigned_url": result.presigned_url,
        "file_path": result.file_path,
    })
```

**Nuxt 4 / frontend side (after getting the presigned URL):**

```javascript
// After your backend returns { presigned_url, file_path }
const file = event.target.files[0]

await fetch(presignedUrl, {
  method: "PUT",
  body: file,
  headers: { "Content-Type": file.type },
})

// Save file_path to your own backend/database
await $fetch("/api/documents/", {
  method: "POST",
  body: { file_path: filePath, filename: file.name }
})
```

---

### `upload_file()` — For scripts and server-side uploads

When you have the file on disk or in memory and want the SDK to handle everything:

```python
# From a file path
result = client.upload_file(
    tenant_id="user_123",
    file_path_or_obj="/tmp/monthly_report.pdf",
)

# From a file-like object (BytesIO, open file, etc.)
import io
buf = io.BytesIO(report_bytes)
buf.name = "report.pdf"
result = client.upload_file(tenant_id="user_123", file_path_or_obj=buf)

# From a Django InMemoryUploadedFile (management commands, etc.)
result = client.upload_file(
    tenant_id="user_123",
    file_path_or_obj=uploaded_file,  # request.FILES["document"]
)

result.file_path   # Save this to your database
result.uploaded    # Always True (exception raised if upload fails)
```

The file goes **directly to Tenantbox storage** - not through Tenantbox backend - even in this mode.

---

## Download

```python
dl = client.get_download_url(
    file_path="projects/.../file.pdf",  # Saved at upload time
    expires_in=3600,                     # Optional, default 3600
)

dl.download_url   # Presigned R2 URL — redirect your user here
dl.filename       # Original filename
dl.content_type   # MIME type
dl.size_bytes     # File size in bytes
```

**Django redirect example:**

```python
from django.shortcuts import redirect

def download_document(request, doc_id):
    doc = Document.objects.get(id=doc_id, user=request.user)
    client = get_client()
    dl = client.get_download_url(doc.file_path, expires_in=300)
    return redirect(dl.download_url)
```

---

## Delete

```python
result = client.delete_file(file_path="projects/.../file.pdf")
result.success  # True
result.detail   # "File deleted successfully."
```

Storage usage for the tenant is automatically decremented.

---

## Usage & Quotas

### Get tenant usage

```python
usage = client.get_usage("user_123")

usage.storage_used_bytes   # Raw bytes
usage.storage_used_mb      # Megabytes (float)
usage.storage_limit_bytes  # None if unlimited
usage.storage_limit_mb     # None if unlimited
usage.usage_percentage     # 0–100, None if unlimited
usage.total_files          # Number of files
usage.is_unlimited         # True if no limit set
usage.email                # Email if provided at upload
```

### Set a storage limit

```python
from tenantbox.utils import MB, GB

client.set_limit("user_123", MB(500))   # 500 MB
client.set_limit("user_123", GB(10))    # 10 GB
client.set_limit("user_123", 52428800)  # Raw bytes also fine
```

### Remove a storage limit (make unlimited)

```python
client.remove_limit("user_123")
```

## Error Handling

All SDK exceptions inherit from `TenantboxError`:

```python
from tenantbox import (
    QuotaExceededError,
    TenantboxAuthError,
    TenantboxNotFoundError,
    TenantboxAPIError,
    TenantboxUploadError,
)

try:
    result = client.get_upload_url(tenant_id="user_123", filename="file.pdf")
except QuotaExceededError:
    return {"error": "You have exceeded your storage quota."}
except TenantboxAuthError:
    # Bad API key — this is a config issue, not a user error
    raise
except TenantboxNotFoundError:
    return {"error": "File not found."}
except TenantboxAPIError as e:
    logger.error("Tenantbox API error: %s (status %s)", e.message, e.status_code)
    return {"error": "Storage service unavailable."}
```

| Exception | When raised |
|---|---|
| `TenantboxAuthError` | Invalid or inactive API key (401) |
| `QuotaExceededError` | Tenant has exceeded their quota (403) |
| `TenantboxNotFoundError` | File or tenant not found (404) |
| `TenantboxUploadError` | Presigned URL obtained but R2 upload failed |
| `TenantboxAPIError` | Unexpected API error (5xx, malformed response) |
| `TenantboxConfigError` | SDK misconfiguration (missing API key, bad URL) |

---

## Utility Helpers

```python
from tenantbox.utils import KB, MB, GB, TB, human_readable_bytes

MB(100)     # → 104857600  (bytes)
GB(2)       # → 2147483648 (bytes)

human_readable_bytes(5_242_880)     # → "5.0 MB"
human_readable_bytes(1_073_741_824) # → "1.0 GB"
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `TENANTBOX_API_KEY` | Your Tenantbox project API key |

---

## Requirements

- Python 3.9+
- `requests` >= 2.28.0

---

## License

MIT