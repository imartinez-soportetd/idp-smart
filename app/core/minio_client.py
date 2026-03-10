from minio import Minio
from minio.error import S3Error
from core.config import settings
import io

def get_minio_client():
    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure
    )
    
    # Ensure bucket exists
    try:
        if not client.bucket_exists(settings.minio_bucket):
            client.make_bucket(settings.minio_bucket)
    except S3Error as err:
        print(f"Minio Error: {err}")
        
    return client

def upload_file_to_minio(client: Minio, object_name: str, file_data: bytes, content_type: str = "application/pdf"):
    client.put_object(
        settings.minio_bucket,
        object_name,
        io.BytesIO(file_data),
        length=len(file_data),
        content_type=content_type
    )
    return f"{settings.minio_bucket}/{object_name}"
