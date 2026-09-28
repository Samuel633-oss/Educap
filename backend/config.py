"""Central configuration. Every secret/setting comes from environment variables."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")


def _csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


class Settings:
    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./educap.db")
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.openrouter_base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self.strong_model = os.getenv("EDUCAP_STRONG_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
        self.fast_model = os.getenv("EDUCAP_FAST_MODEL", self.strong_model)
        self.fallback_models = _csv(os.getenv(
            "EDUCAP_FALLBACK_MODELS",
            "google/gemma-3-27b-it:free,mistralai/mistral-small-3.2-24b-instruct:free"))
        self.embedding_provider = os.getenv("EMBEDDING_PROVIDER", "hashing")
        self.embedding_base_url = os.getenv("EMBEDDING_BASE_URL", "https://api.openai.com/v1")
        self.embedding_api_key = os.getenv("EMBEDDING_API_KEY", "")
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self.cors_origins = _csv(os.getenv("CORS_ORIGINS", "http://localhost:3000"))


settings = Settings()
