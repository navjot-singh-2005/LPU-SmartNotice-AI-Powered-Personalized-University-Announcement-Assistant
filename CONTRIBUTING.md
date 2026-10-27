# Contributing to LPU SmartNotice

Thank you for contributing to **LPU SmartNotice**!

## 1. Repository Structure Guidelines

Maintain clean modular architecture across all contributions:
- `app/core/`: Configuration, database initialization, security, logging.
- `app/models/`: Pydantic data schemas.
- `app/services/`: Core logic (extraction, embedding, vector store, retrieval, personalization, room impact).
- `app/api/routes/`: FastAPI endpoints.
- `app/scripts/`: Command-line tools for validation, dry-runs, indexing, and evaluation.
- `app/static/`: Vanilla HTML, CSS, JavaScript frontend.
- `docs/`: Technical documentation.
- `tests/`: Automated unit and integration tests.

## 2. Coding Standards
- Follow PEP 8 guidelines for Python code style.
- Use explicit type annotations for function signatures.
- Keep dependencies minimal and modular.
- Add clear docstrings to all functions and classes.
- Ensure all new features include corresponding unit tests in `tests/`.

## 3. Safe Handling of Datasets & API Keys
- Never hardcode API keys or secrets in source code.
- Always use environment variables loaded via `.env`.
- Do NOT modify or overwrite the original source dataset `data/all_announcements_with_attachment_flag.json`.
- Do NOT commit `.env`, `storage/`, or dataset JSON files to version control.

## 4. Running Tests Before Submission
Before opening a pull request, run:
```powershell
pytest
```
Ensure all non-billable automated tests pass cleanly.
