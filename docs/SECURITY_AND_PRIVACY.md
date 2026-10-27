# Security & Privacy Safeguards — LPU SmartNotice

## 1. API Key Protection
- The Gemini API key is managed exclusively via local `.env` files loaded by `python-dotenv`.
- The key is NEVER printed in logs, API responses, terminal output, or committed to Git (`.gitignore` protects `.env`).
- Helper function `mask_api_key(...)` masks keys for diagnostic output (e.g. `AQ.A...Eg`).

## 2. PII Redaction Before External LLM Transmission
Before sending announcement text to external LLM APIs (Gemini), the `PIIRedactionService` redacts sensitive personal data:
- **Email addresses:** Matched via regex $\rightarrow$ `[REDACTED_EMAIL]`
- **Phone numbers:** Matched via 10-digit Indian phone patterns $\rightarrow$ `[REDACTED_PHONE]`
- **Student Registration Numbers:** Matched via 8-digit LPU registration patterns $\rightarrow$ `[REDACTED_REG_NO]`

The local raw dataset remains intact and unaltered.

## 3. Local Dataset & Storage Isolation
- Storage databases (`smartnotice.db` and ChromaDB vector store) remain on the local filesystem inside `storage/`.
- No sensitive university data or student feedback is exposed through public cloud endpoints.

---
*Return to [Root README](../README.md)*
