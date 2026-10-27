"""Security utilities for API key validation and safe development controls."""
import os
from app.core.config import settings

def validate_api_key_configured() -> bool:
    """Check if Gemini API key is configured without exposing it."""
    key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
    return bool(key and key.strip() and key != "your_gemini_api_key_here")

def mask_api_key(key: str) -> str:
    """Return a masked representation of an API key for logs/debug."""
    if not key or len(key) < 8:
        return "********"
    return f"{key[:4]}...{key[-4:]}"
