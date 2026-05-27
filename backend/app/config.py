"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings
from pathlib import Path
import os


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # API Keys
    gemini_api_key: str = ""
    groq_api_key: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:3000,http://localhost:3001"

    # Storage paths
    data_dir: str = "./data"
    upload_dir: str = "./data/uploads"
    index_dir: str = "./data/indices"
    db_path: str = "./data/policylens.db"

    # Models
    embedding_model: str = "gemini-embedding-2"
    embedding_dimension: int = 768
    gemini_model: str = "gemini-2.5-flash"
    groq_model: str = "llama-3.3-70b-versatile"

    # LLM & Retrieval Parameters
    temperature: float = 0.1
    top_p: float = 0.8
    top_k_retrieval: int = 5
    chunk_size: int = 900
    chunk_overlap: int = 150

    # Rate limiting
    gemini_rpm: int = 15
    groq_rpm: int = 30
    max_upload_size_mb: int = 20

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def ensure_dirs(self):
        """Create required directories."""
        for d in [self.data_dir, self.upload_dir, self.index_dir]:
            Path(d).mkdir(parents=True, exist_ok=True)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


settings = Settings()
settings.ensure_dirs()
