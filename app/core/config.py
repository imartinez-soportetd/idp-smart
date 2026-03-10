from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "admin_user"
    db_password: str = "Ad54=Tx91.Vm+23_Qr78"
    db_name: str = "rpp_qa"
    valkey_url: str = "redis://localhost:6379/0" 
    
    # Minio Configuration
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "admin"
    minio_secret_key: str = "minio_password123"
    minio_bucket: str = "idp-documents"
    minio_secure: bool = False

    # LLM Settings
    llm_provider: str = "google" # "google" o "ollama"
    google_api_key: str = "AIzaSyAnilUrCDdCD-kP0doz5fgpFHNsJ45sigw"
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "qwen2.5:7b" 
    
    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

settings = Settings()
