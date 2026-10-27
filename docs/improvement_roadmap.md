# LPU SmartNotice — Architectural Improvement Roadmap

This roadmap documents the architectural enhancements, reliability upgrades, and engineering improvements implemented across all subsystems of the LPU SmartNotice platform.

---

## 1. System Improvement Pillars

```
+---------------------------------------------------------------------------------+
|                                LPU SmartNotice                                  |
+---------------------------------------------------------------------------------+
        |                        |                        |               |
        v                        v                        v               v
 [Data Ingestion]         [AI & RAG Engine]      [Personalization]    [Frontend & API]
 - Thread-safe Caching    - Grounded Citations   - Exclusion Rules   - Honest Sync UI
 - SHA-256 Deduplication  - Multi-turn Memory    - Exemption Checks  - Loading Debounce
 - ASP.NET WebMethods     - PII Redaction        - ISO Deadlines     - Retry Handling
 - Status Nuances         - Heuristic Fallback   - Range Parsers     - Source Badges
```

---

## 2. Detailed Improvement Specifications

### Pillar 1: Announcement Ingestion & Provenance
- **In-Memory Caching:** Thread-safe singleton cache (`_cached_historical_dataset`) avoids re-reading 11.2 MB JSON on every HTTP request, reducing latency from ~420ms to ~1.2ms.
- **Deduplication & Revision Tracking:** SHA-256 hash tracking detects identical circulars across runs. When an existing announcement's title or content changes, its `revision_count` increments and the record is updated in place without duplicate records.
- **Normalization & Sanitization:** Indian Rupee symbols (`₹`) are safely mapped to `Rs.` to prevent Windows `cp1252` encoding errors. Unicode quotes are normalized to ASCII.

### Pillar 2: LPU UMS Portal & Feed Synchronization
- **Truthful Status Codes:** Upgraded from monolithic `SUCCESS` to granular statuses:
  - `SUCCESS`: New or revised notices imported and indexed into ChromaDB.
  - `UP_TO_DATE`: Upstream returned notices that are already present and verified in SQLite.
  - `EMPTY_SOURCE`: Upstream source returned 0 candidates.
  - `AUTH_REQUIRED`: Active session cookie required for protected student portal pages.
  - `FAILED`: Unhandled network error or schema mismatch.
- **ASP.NET Response Decoding:** Added support for stringified JSON payloads (`{"d": "..."}`), list wrappers (`{"d": [...]}`), and ADO.NET DataSets (`{"d": {"Table": [...]}}`).
- **Safe Diagnostic Logging:** Phase 3 structured logging records HTTP method, URL, status code, byte length, redirects, and top keys without logging sensitive cookies, tokens, or PII.

### Pillar 3: Grounded AI Assistant & RAG Pipeline
- **Conversational Filter:** Filter greetings ("Hello", "Hi", "Hey") so they return a friendly assistant introduction with 0 sources instead of matching irrelevant circulars (e.g. "From Hello to Hired").
- **Multi-Turn Context:** Inject recent user and assistant turns (`history: List[ChatMessage]`) into the grounded Gemini prompt so follow-up questions work smoothly.
- **Strict Grounding & Refusal:** Explicit instruction requires citing bracketed source identifiers `[Source ID: ...]` and returning an honest refusal when evidence is absent from the circular dataset.
- **BM25 Stopwords Filtering:** Stripped common English stopwords from lexical queries to prevent false positive matches on common terms.

### Pillar 4: Personalization, Deadlines & Room Impact
- **Negative Exclusion Matching:** Explicit student group exclusions (`metadata.exclusions`) are checked; students belonging to excluded branches or years receive a score penalty (0.05) and an explicit banner.
- **Room Conflict Exemptions:** Regex patterns for exception keywords (`except`, `excluding`, `exempted`) and `metadata.exempted_rooms` ensure exempted classes are correctly flagged as `affected=False, status="EXEMPTED"`.
- **Upcoming Deadlines Route:** Built `GET /api/v1/announcements/deadlines` with ISO date parsing and status categorization (`upcoming`, `expired`, `all`).

### Pillar 5: Frontend Experience & Usability
- **Debounced Submissions:** Disabled `#chatSubmit` during active queries with a visual "Thinking... ⏳" indicator to prevent duplicate concurrent API requests.
- **Input Preservation & Retry:** Preserves input value on failure and presents an interactive Retry button.
- **Markdown & Citation Rendering:** Built lightweight markdown parser converting line breaks, bold headers, and bullet lists into clean HTML with clickable source reference badges.

### Pillar 6: Security, Privacy & Reliability
- **PII Redaction:** Automated regex masking of phone numbers, student email addresses, and 8-digit registration numbers before model dispatch.
- **Zero-Secret Logging:** Session cookies are masked (e.g. `ASP.NET_SessionId=ab12***`), and API keys are strictly read from `.env` without exposure in code or logs.
- **Offline Vectors:** Added normalized pseudo-embedding generator ensuring all test suites and local environments operate deterministically even without active internet or API credits.
