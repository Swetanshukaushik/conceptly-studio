import os
import shutil
from abc import ABC, abstractmethod
from typing import Optional
import mimetypes
from src.core.config import settings

class StorageService(ABC):
    @abstractmethod
    def upload_file(self, local_path: str, destination_name: str) -> str:
        """Uploads a file and returns its accessible URL."""
        pass
    
    @abstractmethod
    def get_file_path(self, destination_name: str) -> str:
        """Returns the local path or resolved location."""
        pass

class LocalStorageService(StorageService):
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = os.path.abspath(base_dir or settings.LOCAL_STORAGE_DIR)
        os.makedirs(self.base_dir, exist_ok=True)
    
    def upload_file(self, local_path: str, destination_name: str) -> str:
        target_path = os.path.join(self.base_dir, destination_name)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        if os.path.abspath(local_path) != target_path:
            shutil.copy2(local_path, target_path)
            
        # Returns API media endpoint URL for local streaming
        return f"/media/{destination_name}"
    
    def get_file_path(self, destination_name: str) -> str:
        return os.path.join(self.base_dir, destination_name)

class R2StorageService(StorageService):
    def __init__(self):
        import boto3
        from botocore.config import Config
        
        self.endpoint_url = f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
        self.bucket_name = settings.R2_BUCKET_NAME
        self.public_url = settings.R2_PUBLIC_URL.rstrip("/")
        
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            config=Config(signature_version="s3v4"),
            region_name="auto"
        )
        
        # Local mirror cache
        self.local_mirror = LocalStorageService()
    
    def upload_file(self, local_path: str, destination_name: str) -> str:
        # Save local copy first
        self.local_mirror.upload_file(local_path, destination_name)
        
        content_type, _ = mimetypes.guess_type(local_path)
        content_type = content_type or "application/octet-stream"
        
        with open(local_path, "rb") as f:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=destination_name,
                Body=f,
                ContentType=content_type
            )
            
        return f"{self.public_url}/{destination_name}"
    
    def get_file_path(self, destination_name: str) -> str:
        return self.local_mirror.get_file_path(destination_name)

def get_storage_service() -> StorageService:
    if settings.STORAGE_PROVIDER == "r2" and settings.R2_ACCOUNT_ID and settings.R2_ACCESS_KEY_ID:
        try:
            return R2StorageService()
        except Exception:
            return LocalStorageService()
    return LocalStorageService()
