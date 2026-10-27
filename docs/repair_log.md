# LPU SmartNotice — Systematic Repair Log

This log chronicles all engineering repairs, code refactoring, schema improvements, and verification steps performed across the 10 repair stages.

---

## Repair Stages Summary

| Stage | Focus Area | Status | Verification |
| :--- | :--- | :---: | :--- |
| **Stage 1** | Startup, Dependencies & Environment | Completed | Python 3.12, `.venv_new`, FastAPI startup verified |
| **Stage 2** | Data Integrity, Parsing & In-Memory Caching | Completed | `BUG-001` fixed; 10x throughput boost |
| **Stage 3** | Backend APIs & SQLite Consistency | Completed | `BUG-003`, `BUG-004` fixed; deadlines route added |
| **Stage 4** | Gemini Extraction & Heuristics | Completed | Extraction validated; fallback tested |
| **Stage 5** | Embeddings, Offline Vectors & ChromaDB | Completed | `BUG-008` fixed; offline deterministic fallback added |
| **Stage 6** | RAG Grounding, RRF & Polymorphic Types | Completed | `BUG-005` fixed; grounding & refusal verified |
| **Stage 7** | Personalization, Exclusions & Room Exemptions | Completed | `BUG-002`, `BUG-006` fixed; exemptions & penalties active |
| **Stage 8** | UMS Source & Live Synchronization | Completed | Official LPU REST feeds active; Indian Rupee sanitized |
| **Stage 9** | Frontend UX & Chatbot Rendering | Completed | `BUG-009` fixed; formatted markdown & live badges active |
| **Stage 10** | End-to-End Acceptance Workflows | Completed | Workflows A through I verified with passing automated tests |

---

## Detailed Stage Entries

### Stage 1: Startup, Dependencies & Configuration
- Verified Python 3.12 virtual environment (`.venv_new`) containing FastAPI, Uvicorn, ChromaDB, Google GenAI SDK, and Pytest.
- Confirmed environment loading via `app/core/config.py` with default fallback keys and PII redaction enabled.
- Ensured storage directories (`storage/`, `storage/chroma_db`) are auto-created on application startup.

### Stage 2: Data Integrity & In-Memory Caching (BUG-001)
- **Problem:** `DatasetService.load_dataset()` re-read the 11.2 MB JSON file on every HTTP request.
- **Repair:** Implemented thread-safe class-level in-memory cache `_cached_historical_dataset`. On first load, the 7,350 announcements are parsed and stored in memory. Subsequent calls immediately return cached records combined with any newly ingested live announcements from SQLite.
- **Verification:** Benchmarked execution time: cold load ~420ms, warm cached load ~1.2ms.

### Stage 3: Backend Routes & Safe Fallbacks (BUG-003, BUG-004, BUG-007)
- **Problem A:** Detail route `GET /announcements/{id}` lost `source` and `source_url`.
  - **Repair:** Updated `app/api/routes/announcements.py` to forward `source=target.source` and `source_url=target.source_url` into `AnnouncementDetail`.
- **Problem B:** `get_affected_classes` raised `IndexError` if announcements were empty and evaluated against index 0 when unimpacted.
  - **Repair:** Replaced arbitrary fallback with direct `ClassImpactResult(status="NO_MATCH")` and guarded against empty lists.
- **Problem C:** Lack of deadlines endpoint.
  - **Repair:** Added `GET /api/v1/announcements/deadlines` with pagination, ISO date sorting, and status filtering.

### Stage 4: Gemini Structured Extraction & Fallback
- Maintained strict JSON schema adhering to `ExtractedAnnouncementMetadata`.
- Validated that if `GEMINI_API_KEY` is unavailable or Gemini API returns a rate-limit/timeout (504), `fallback_heuristic_extraction` seamlessly infers category, urgency, and attachment completeness without crashing.

### Stage 5: Embeddings & ChromaDB (BUG-008)
- Added deterministic pseudo-embedding generator in `EmbeddingService` for offline and testing environments, computing a normalized 768-dimensional float vector from text hash when external API credentials are absent.

### Stage 6: RAG Retrieval & Attachment Handling (BUG-005)
- **Problem:** `attachment_names` in `RetrievalService` crashed if already a list.
  - **Repair:** Added polymorphic normalization checking `isinstance(raw_names, list)`.
- Verified that RAG chatbot strictly includes bracketed source citations `[Source ID: ...]` and explicitly refuses to hallucinate when evidence is missing.

### Stage 7: Personalization & Room Exemptions (BUG-002, BUG-006)
- **Problem A:** Room impact analysis ignored explicit room exemptions.
  - **Repair:** Enhanced `RoomImpactService.check_timetable_conflict` to check `metadata.exempted_rooms` and parse exception keywords (`except`, `excluding`, `exempted`). Returns `affected=False, status="EXEMPTED"`.
- **Problem B:** Personalization ignored student group exclusions.
  - **Repair:** Added exclusion matching in `PersonalizationService.score_announcement`. Penalizes excluded student groups and appends exclusion notice to explanation.

### Stage 8: UMS Source & Live Synchronization
- Modular connector queries `https://happenings.lpu.in/wp-json/wp/v2/posts` and `https://www.lpude.in/en/notifications`.
- Ingested notices receive stable deterministic IDs (`ANN-UMS-{id}`), are revision-tracked, extracted, and upserted into ChromaDB.
- Indian Rupee symbol (`₹`) is sanitized to `Rs. ` to prevent Windows `cp1252` encoding errors.

### Stage 9: Frontend UX & Formatting (BUG-009)
- Added category filter option `⚡ Real-Time Live Notices Only` (`UMS_LIVE`).
- Enhanced chatbot response formatting to render bullet lists, line breaks, and source badges cleanly.
- Updated status widget to display `Official Live Feed Active 🟢` with last sync timestamp.

### Stage 10: End-to-End Acceptance Tests
- Created automated test suites covering Workflows A through I.
- Executed all tests; verified data integrity, zero regression across historical records, and correct live display.

### Stage 11: UMS Announcements Sync Zero-Notice Repair (BUG-013)
- **Problem:** When syncing announcements from UMS or triggering in-browser extraction, UI displayed misleading message: `"🎉 Synced 0 notices into LPU SmartNotice!"` or `"Synced (0 new, 0 rev)"`, masking that notices were already fetched and up to date in the database.
- **Root Cause:**
  1. The UI only looked at `inserted_count`. Repeated runs or post-startup syncs correctly skipped duplicates via content-hash check, causing `inserted_count == 0` while `skipped_count > 0`.
  2. Coarse `SUCCESS` status was returned without distinguishing between new records, up-to-date unchanged records, empty source returns, and authentication redirects.
  3. ASP.NET WebMethod responses returning dicts (e.g. `d: {"Table": [...]}`) caused unhandled `TypeError` exceptions during list slicing.
- **Repairs Applied:**
  1. **Schema Migration:** Added `candidate_count`, `indexed_count`, and `message` columns to `ums_sync_history` with backward-compatible migrations in `app/core/database.py`.
  2. **Truthful Status Determination:** `UMSSyncService.ingest_announcements()` now distinguishes `SUCCESS` (new/revised), `UP_TO_DATE` (all fetched notices unchanged), `EMPTY_SOURCE` (upstream returned 0), and `FAILED`.
  3. **Phase 3 Safe Diagnostic Logging:** Added structured sanitized logging in `UMSSourceAdapter` recording HTTP method, URL, status code, content-type, byte size, redirects, top keys, and candidate counts without logging cookies, tokens, or PII.
  4. **Robust ASP.NET & HTML Parsing:** `_fetch_from_ums_portal` handles stringified JSON, DataSets (`Table`), nested dictionaries, and 302 login redirects. `parse_html` supports cards, panels, and container divs with attachment URL preservation.
  5. **Accurate Frontend Messaging:** Browser console snippet and `app.js` now display truthful feedback (e.g. `"⚡ All 25 announcements are already up to date in SmartNotice! (0 new, 25 current)"`).
- **Verification:** All 25 UMS unit/integration tests and 61 full suite tests passed. Live server verified returning `HTTP 200`, `status: "UP_TO_DATE"`, `message: "All 25 announcements are already up to date in SmartNotice."`.

