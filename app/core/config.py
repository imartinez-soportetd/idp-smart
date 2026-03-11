from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "postgres"
    db_password: str = ""
    db_name: str = "postgres"
    valkey_url: str = "redis://localhost:6379/0" 
    
    # Minio Configuration
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minio_user"
    minio_secret_key: str = "minio_password"
    minio_bucket: str = "idp-documents"
    minio_secure: bool = False

    # LLM Settings
    llm_provider: str = "google" # "google" o "ollama"
    google_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b" 
    
    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

settings = Settings()
