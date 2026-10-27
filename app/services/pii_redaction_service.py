import re
from typing import Tuple
from app.core.config import settings

class PIIRedactionService:
    """Service to redact PII (phone numbers, personal emails, student registration IDs) before LLM submission."""

    # Patterns
    EMAIL_PATTERN = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    PHONE_PATTERN = r"(?:\+?91[\-\s]?)?[6-9]\d{9}\b"
    REG_NO_PATTERN = r"\b1[0-9]{7}\b" # LPU Student registration numbers often 8-digit starting with 1

    def redact_pii(self, text: str) -> Tuple[str, int]:
        """Redact PII patterns from text and return (redacted_text, count_of_redactions)."""
        if not settings.REDACT_PII_BEFORE_LLM:
            return text, 0

        redactions = 0
        redacted = text

        # Redact emails
        redacted, count_email = re.subn(self.EMAIL_PATTERN, "[REDACTED_EMAIL]", redacted)
        redactions += count_email

        # Redact phone numbers
        redacted, count_phone = re.subn(self.PHONE_PATTERN, "[REDACTED_PHONE]", redacted)
        redactions += count_phone

        # Redact registration numbers
        redacted, count_reg = re.subn(self.REG_NO_PATTERN, "[REDACTED_REG_NO]", redacted)
        redactions += count_reg

        return redacted, redactions
