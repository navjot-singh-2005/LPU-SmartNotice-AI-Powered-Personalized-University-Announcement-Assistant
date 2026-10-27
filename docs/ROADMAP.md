# Project Roadmap — LPU SmartNotice

## Version 1.0 (Completed Baseline)
- [x] Dataset validation and quality report script.
- [x] Stable ID generation and duplicate detection preserving notice revisions.
- [x] PII redaction service for emails, phone numbers, and student IDs.
- [x] Gemini structured information extraction with Pydantic schemas and SQLite caching.
- [x] Persistent ChromaDB vector index with 768-dimensional embeddings.
- [x] Hybrid retrieval (Semantic + Lexical + RRF).
- [x] Grounded RAG chatbot with source citations and attachment warnings.
- [x] Attachment presence vs content availability tracking (`decision_completeness`).
- [x] Rule-based personalized feed ranking with urgency/global safety overrides.
- [x] Room number normalization and timetable impact conflict checking.
- [x] FastAPI REST API with Swagger documentation (`/docs`).
- [x] Interactive web interface with dark-mode aesthetic.
- [x] Automated unit and integration testing suite.

## Version 2.0 (Future Enhancements)
- [ ] OCR and parsing for attached PDF / image documents when files are uploaded.
- [ ] Supervised Learning to rank (LTR) model using student feedback data.
- [ ] Live browser extension connector for real-time incremental notice ingestion.
- [ ] Push notification alerts for critical timetable room changes.

---
*Return to [Root README](../README.md)*
