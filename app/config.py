from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Scenarius"
    app_env: str = "development"
    app_debug: bool = True
    app_secret_key: str = "change-me-in-production"

    postgres_target: str = "docker"
    postgres_host: str = "localhost"
    postgres_port: int = 5435
    postgres_user: str = "scenarius"
    postgres_password: str = "scenarius"
    postgres_db: str = "scenarius"
    database_url: str | None = None

    redis_url: str = "redis://localhost:6379/0"

    search_default_language: str = "ru"
    search_default_tier: int = 1

    embedding_enabled: bool = True
    embedding_model: str = (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    embedding_dimensions: int = 384

    scraper_user_agent: str = (
        "Scenarius/0.2 (https://github.com/scenarius/scenarius; "
        "mailto:scenarius@local) Python-httpx"
    )
    scraper_contact_url: str = "https://github.com/scenarius/scenarius"
    scraper_contact_email: str = "scenarius@local"
    scraper_delay_seconds: float = 1.0
    scraper_timeout_seconds: float = 120.0

    llm_provider: str = "auto"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    llm_max_tokens: int = 800

    opensubtitles_api_key: str = ""
    ruscorpora_api_key: str = ""

    @model_validator(mode="after")
    def build_database_url(self) -> "Settings":
        """Build DATABASE_URL from parts when not set explicitly."""
        if self.database_url:
            return self
        self.database_url = (
            f"postgresql+psycopg://{self.postgres_user}:"
            f"{self.postgres_password}@{self.postgres_host}:"
            f"{self.postgres_port}/{self.postgres_db}"
        )
        return self


settings = Settings()
