import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application Settings loaded from environment variables or defaults."""

    GEMINI_API_KEY: str = ""
    GEMINI_GENERATION_MODEL: str = "gemini-3.1-flash-lite"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-2"

    DATASET_PATH: str = "data/all_announcements_with_attachment_flag.json"
    SQLITE_PATH: str = "storage/smartnotice.db"
    CHROMA_PATH: str = "storage/chroma_db"

    EMBEDDING_DIMENSION: int = 768
    INITIAL_INDEX_LIMIT: int = 25
    REDACT_PII_BEFORE_LLM: bool = True
    LOG_LEVEL: str = "INFO"

    # UMS Source Configuration
    UMS_BASE_URL: str = "https://ums.lpu.in/lpuums/"
    UMS_ANNOUNCEMENTS_ENDPOINT: str = "https://ums.lpu.in/lpuums/StudentDashboard.aspx/AnnouncementDetails"
    LPU_HAPPENINGS_FEED_URL: str = "https://happenings.lpu.in/wp-json/wp/v2/posts"
    UMS_CONNECTOR_MODE: str = "live"  # "live" for real-time university announcements, "mock" for offline tests
    UMS_SESSION_COOKIE: str = ""      # Optional authenticated portal cookie (ASP.NET_SessionId / cf_clearance)
    SYNC_ADMIN_KEY: str = "smartnotice-admin-key"
    AUTO_EMBED_NEW_NOTICES: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def ensure_directories(self) -> None:
        """Ensure storage directory exists."""
        sqlite_dir = Path(self.SQLITE_PATH).parent
        chroma_dir = Path(self.CHROMA_PATH)
        sqlite_dir.mkdir(parents=True, exist_ok=True)
        chroma_dir.mkdir(parents=True, exist_ok=True)

settings = Settings()
settings.ensure_directories()
