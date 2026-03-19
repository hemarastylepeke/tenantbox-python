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

This is why Tenantbox is faster, the file doesn't travel through your server twice.

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

---

### `upload_file()` - For scripts and server-side uploads

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

result.file_path   # Save this to your database
result.uploaded    # Always True (exception raised if upload fails)
```

The file goes **directly to Tenantbox storage**

---

## Framework Examples

### Django Templating Engine

The classic Django setup - a form-based upload using Django's templating engine. The view gets the presigned URL, passes it to the template, and the browser uploads directly to Tenantbox storage without touching your server.

**views.py**

```python
import os
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from tenantbox import TenantboxClient

client = TenantboxClient(api_key=os.environ["TENANTBOX_API_KEY"])


@login_required
def upload_page(request):
    """Render the upload form with a fresh presigned URL."""
    result = client.get_upload_url(
        tenant_id=str(request.user.id),
        filename=request.GET.get("filename", "upload"),
        tenant_email=request.user.email,
    )
    return render(request, "upload.html", {
        "presigned_url": result.presigned_url,
        "file_path": result.file_path,
    })


@login_required
def save_file(request):
    """Called by the template after the browser finishes uploading."""
    if request.method == "POST":
        file_path = request.POST.get("file_path")
        filename = request.POST.get("filename")
        # Save file_path to your model
        request.user.profile.avatar_path = file_path
        request.user.profile.save()
        return redirect("dashboard")


@login_required
def download_file(request, file_path):
    """Redirect the user to a short-lived download URL."""
    from django.shortcuts import redirect
    dl = client.get_download_url(file_path=file_path, expires_in=300)
    return redirect(dl.download_url)
```

**templates/upload.html**

```html
<!DOCTYPE html>
<html>
<head><title>Upload File</title></head>
<body>

<h2>Upload a File</h2>

<input type="file" id="fileInput" />
<button onclick="startUpload()">Upload</button>
<p id="status"></p>

<script>
  // These values are injected by Django's template engine
  const presignedUrl = "{{ presigned_url }}";
  const filePath = "{{ file_path }}";

  async function startUpload() {
    const file = document.getElementById("fileInput").files[0];
    if (!file) return;

    document.getElementById("status").textContent = "Uploading...";

    // Upload directly to Tenantbox storage — never touches your Django server
    const response = await fetch(presignedUrl, {
      method: "PUT",
      body: file,
      headers: { "Content-Type": file.type },
    });

    if (response.ok) {
      document.getElementById("status").textContent = "Upload complete!";

      // Tell your Django backend to save the file_path
      const form = document.createElement("form");
      form.method = "POST";
      form.action = "/save-file/";

      const csrfInput = document.createElement("input");
      csrfInput.type = "hidden";
      csrfInput.name = "csrfmiddlewaretoken";
      csrfInput.value = "{{ csrf_token }}";

      const pathInput = document.createElement("input");
      pathInput.type = "hidden";
      pathInput.name = "file_path";
      pathInput.value = filePath;

      const nameInput = document.createElement("input");
      nameInput.type = "hidden";
      nameInput.name = "filename";
      nameInput.value = file.name;

      form.appendChild(csrfInput);
      form.appendChild(pathInput);
      form.appendChild(nameInput);
      document.body.appendChild(form);
      form.submit();
    } else {
      document.getElementById("status").textContent = "Upload failed. Please try again.";
    }
  }
</script>

</body>
</html>
```

**urls.py**

```python
from django.urls import path
from . import views

urlpatterns = [
    path("upload/", views.upload_page, name="upload"),
    path("save-file/", views.save_file, name="save_file"),
    path("download/<path:file_path>/", views.download_file, name="download_file"),
]
```

---

### Django Ninja

```python
from ninja import Router
from tenantbox import TenantboxClient
import os

router = Router()
client = TenantboxClient(api_key=os.environ["TENANTBOX_API_KEY"])


@router.post("/upload-url/")
def upload_url(request, filename: str):
    result = client.get_upload_url(
        tenant_id=str(request.user.id),
        filename=filename,
        tenant_email=request.user.email,
    )
    return {
        "presigned_url": result.presigned_url,
        "file_path": result.file_path,
    }


@router.get("/download/")
def download_url(request, file_path: str):
    dl = client.get_download_url(file_path=file_path, expires_in=300)
    return {"download_url": dl.download_url}


@router.delete("/files/")
def delete_file(request, file_path: str):
    result = client.delete_file(file_path=file_path)
    return {"detail": result.detail}
```

---

### Django REST Framework

```python
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from tenantbox import TenantboxClient
import os

client = TenantboxClient(api_key=os.environ["TENANTBOX_API_KEY"])


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_url(request):
    result = client.get_upload_url(
        tenant_id=str(request.user.id),
        filename=request.data["filename"],
        tenant_email=request.user.email,
    )
    return Response({
        "presigned_url": result.presigned_url,
        "file_path": result.file_path,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def download_url(request):
    dl = client.get_download_url(
        file_path=request.query_params["file_path"],
        expires_in=300,
    )
    return Response({"download_url": dl.download_url})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_file(request):
    result = client.delete_file(file_path=request.data["file_path"])
    return Response({"detail": result.detail})
```

---

### Nuxt 4

**Server route - `server/api/upload-url.post.ts`**

```typescript
export default defineEventHandler(async (event) => {
  const body = await readBody(event)

  const response = await $fetch("/api/storage/upload/", {
    baseURL: process.env.TENANTBOX_BASE_URL,
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.TENANTBOX_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: {
      tenant_id: body.tenantId,
      filename: body.filename,
      content_type: body.contentType,
    },
  })

  return response  // { presigned_url, file_path }
})
```

**Component - `components/FileUpload.vue`**

```vue
<template>
  <div>
    <input type="file" @change="handleFileChange" />
    <button @click="upload" :disabled="!file || uploading">
      {{ uploading ? "Uploading..." : "Upload" }}
    </button>
    <p v-if="message">{{ message }}</p>
  </div>
</template>

<script setup lang="ts">
const file = ref<File | null>(null)
const uploading = ref(false)
const message = ref("")

function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  file.value = input.files?.[0] ?? null
}

async function upload() {
  if (!file.value) return
  uploading.value = true
  message.value = ""

  try {
    // Step 1: Get presigned URL from your Nuxt server route
    const { presigned_url, file_path } = await $fetch("/api/upload-url", {
      method: "POST",
      body: {
        tenantId: useAuth().user.id,   // your auth composable
        filename: file.value.name,
        contentType: file.value.type,
      },
    })

    // Step 2: Upload directly to Tenantbox storage
    await $fetch(presigned_url, {
      method: "PUT",
      body: file.value,
      headers: { "Content-Type": file.value.type },
    })

    // Step 3: Save file_path to your own database
    await $fetch("/api/documents", {
      method: "POST",
      body: { file_path, filename: file.value.name },
    })

    message.value = "Upload complete!"
  } catch (err) {
    message.value = "Upload failed. Please try again."
  } finally {
    uploading.value = false
  }
}
</script>
```

---

### Next.js

**API route - `app/api/upload-url/route.ts`**

```typescript
import { NextRequest, NextResponse } from "next/server"

export async function POST(req: NextRequest) {
  const { tenantId, filename, contentType } = await req.json()

  const response = await fetch(
    `${process.env.TENANTBOX_BASE_URL}/api/storage/upload/`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${process.env.TENANTBOX_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        tenant_id: tenantId,
        filename,
        content_type: contentType,
      }),
    }
  )

  if (!response.ok) {
    return NextResponse.json({ error: "Failed to get upload URL" }, { status: 500 })
  }

  const data = await response.json()
  return NextResponse.json(data)  // { presigned_url, file_path }
}
```

**Component - `components/FileUpload.tsx`**

```tsx
"use client"

import { useState } from "react"

export default function FileUpload({ tenantId }: { tenantId: string }) {
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState("")

  async function handleUpload() {
    if (!file) return
    setUploading(true)
    setMessage("")

    try {
      // Step 1: Get presigned URL from your Next.js API route
      const res = await fetch("/api/upload-url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tenantId,
          filename: file.name,
          contentType: file.type,
        }),
      })
      const { presigned_url, file_path } = await res.json()

      // Step 2: Upload directly to Tenantbox storage
      await fetch(presigned_url, {
        method: "PUT",
        body: file,
        headers: { "Content-Type": file.type },
      })

      // Step 3: Save file_path to your own database
      await fetch("/api/documents", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path, filename: file.name }),
      })

      setMessage("Upload complete!")
    } catch (err) {
      setMessage("Upload failed. Please try again.")
    } finally {
      setUploading(false)
    }
  }

  return (
    <div>
      <input
        type="file"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
      />
      <button onClick={handleUpload} disabled={!file || uploading}>
        {uploading ? "Uploading..." : "Upload"}
      </button>
      {message && <p>{message}</p>}
    </div>
  )
}
```

**`.env.local`**

```env
TENANTBOX_API_KEY=your_key_here
TENANTBOX_BASE_URL=https://api.tenantbox.dev
```

---

## Download

```python
dl = client.get_download_url(
    file_path="projects/.../file.pdf",  # Saved at upload time
    expires_in=3600,                     # Optional, default 3600
)

dl.download_url   # Presigned URL — redirect your user here
dl.filename       # Original filename
dl.content_type   # MIME type
dl.size_bytes     # File size in bytes
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

---

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
| `TENANTBOX_BASE_URL` | Override the API base URL (optional) |

---

## Requirements

- Python 3.9+
- `requests` >= 2.28.0

---

## License

MIT