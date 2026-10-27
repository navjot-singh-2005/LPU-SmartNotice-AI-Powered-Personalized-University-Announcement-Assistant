# Testing & System Evaluation — LPU SmartNotice

## 1. Automated Test Suite
The project includes a comprehensive test suite in `tests/` powered by `pytest`.

Run all automated unit tests:
```powershell
pytest
```

### Test Coverage
- **Dataset Parsing:** `tests/test_dataset.py` verifies loading, quality metric generation, and stable ID computation.
- **Deduplication:** `tests/test_deduplication.py` checks content hashing and revision preservation.
- **PII Redaction:** `tests/test_pii.py` tests email, phone, and registration ID masking.
- **Extraction Schema:** `tests/test_extraction_schema.py` validates Pydantic model serialization and enum bounds.
- **Vector Store & Retrieval:** `tests/test_vector_store.py` and `tests/test_retrieval.py` verify ChromaDB persistent storage and RRF hybrid scoring.
- **Personalization:** `tests/test_personalization.py` verifies student scoring formulas and global safety overrides.
- **Room Impact:** `tests/test_room_impact.py` tests room string normalization (`34-105`) and timetable collision logic.

## 2. Mocking Policy for API Tests
All standard automated unit tests mock Gemini API calls to prevent incursions on API quotas. Live integration tests can be run separately when explicitly requested.

## 3. System Evaluation Script
To evaluate RAG retrieval quality and timetable conflict detection on sample data:
```powershell
python -m app.scripts.evaluate_system
```

---
*Return to [Root README](../README.md)*
