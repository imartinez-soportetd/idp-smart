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
    llm_provider: str = "localai"  # "google", "ollama", o "localai"
    google_api_key: str = ""
    
    # Ollama Configuration (Legacy/Alternative)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    
    # LocalAI Configuration (OpenAI Compatible API)
    localai_base_url: str = "http://localhost:8080/v1"
    localai_model: str = "granite-vision"
    localai_temperature: float = 0.1  # Baja para extracciones precisas
    localai_context_size: int = 8192  # Mayor para documentos grandes
    localai_max_tokens: int = 2048
    localai_timeout: int = 300  # 5 minutos 
    
    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

settings = Settings()
