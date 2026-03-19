from tenantbox import TenantboxClient
from decouple import config

# Get the API Key from your environment
api_key = config('TENANTBOX_API_KEY')
client = TenantboxClient(api_key=api_key)

# 1. Get an upload URL
result = client.get_upload_url(
    tenant_id="test_user_001",
    filename="hello.txt",
    tenant_email="test@example.com",
)
print("presigned_url:", result.presigned_url)
print("file_path:", result.file_path)
print("is_new_tenant:", result.is_new_tenant)

# 2. Upload a file directly (SDK handles both steps)
import io
buf = io.BytesIO(b"Hello from Tenantbox SDK!")
buf.name = "hello.txt"
upload = client.upload_file(tenant_id="test_user_001", file_path_or_obj=buf)
print("uploaded:", upload.uploaded)
print("file_path:", upload.file_path)

# 3. Check usage
usage = client.get_usage("test_user_001")
print("used:", usage.storage_used_mb, "MB")
print("files:", usage.total_files)

# 4. Get a download URL
dl = client.get_download_url(upload.file_path)
print("download_url:", dl.download_url)

# 5. Delete the file
deleted = client.delete_file(upload.file_path)
print("deleted:", deleted.detail)

# 6. Set a limit
from tenantbox import MB
client.set_limit("test_user_001", MB(100))
print("limit set to 100MB")

# 7. Remove the limit
client.remove_limit("test_user_001")
print("limit removed")