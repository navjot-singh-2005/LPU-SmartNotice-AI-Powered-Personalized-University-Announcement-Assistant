# LPU SmartNotice — Bug Tracker

This document records all defects, architectural bottlenecks, edge cases, and vulnerabilities discovered during the comprehensive audit.

---

## Defect Summary by Severity

| Severity | Total Found | Fixed | In Progress | Open |
| :--- | :---: | :---: | :---: | :---: |
| **P0 — Critical** | 0 | 0 | 0 | 0 |
| **P1 — High** | 2 | 2 | 0 | 0 |
| **P2 — Medium** | 8 | 8 | 0 | 0 |
| **P3 — Low** | 3 | 3 | 0 | 0 |
| **Total** | **13** | **13** | **0** | **0** |

---

## Detailed Bug Records

### BUG-001: Missing in-memory dataset caching causing high per-request CPU and I/O latency
- **Bug ID:** BUG-001
- **Affected Feature / File:** `app/services/dataset_service.py`
- **Severity:** P1 — High (Performance & Throughput)
- **Reproduction Steps:**
  1. Call `GET /api/v1/announcements?page=1` or `GET /api/v1/feed/STU-101/feed`.
  2. Profile execution time of `dataset_service.load_dataset()`.
  3. Notice that the entire 11.2 MB JSON file is re-read and parsed on every single HTTP request.
- **Root Cause:** `DatasetService.load_dataset()` lacked an in-memory cache layer, performing cold disk I/O and deserialization of 7,350 dictionary objects on every caller invocation.
- **Proposed Fix:** Introduce thread-safe in-memory caching of the parsed historical announcements list with an explicit `force_reload` option and `reload_cache()` method, merging dynamically with fresh records from SQLite.
- **Fix Status:** Fixed
- **Verification Evidence:** `load_dataset()` execution drops from ~420ms to ~1.2ms on subsequent calls. All dataset and feed tests pass.

---

### BUG-002: Room Impact Service ignores `metadata.exempted_rooms` and textual room exemptions
- **Bug ID:** BUG-002
- **Affected Feature / File:** `app/services/room_impact_service.py`
- **Severity:** P2 — Medium
- **Reproduction Steps:**
  1. Create announcement affecting Block 34 with `metadata.exempted_rooms = ["34-105"]` or text "All classes suspended in Block 34 except Room 34-105".
  2. Pass a student timetable entry located in Room 34-105.
  3. Call `room_impact_service.check_timetable_conflict(entry, ann, metadata)`.
  4. Notice the result returned `affected=True, status="CONFIRMED_MATCH"` instead of being exempted.
- **Root Cause:** `check_timetable_conflict` collected affected rooms but never evaluated `metadata.exempted_rooms` or regex exception patterns ("except", "excluding", "exempted").
- **Proposed Fix:** Check explicit `exempted_rooms` from metadata and text regex patterns. If the student's room matches an exemption, return `affected=False, status="EXEMPTED"` with an explanation.
- **Fix Status:** Fixed
- **Verification Evidence:** Unit test `test_room_impact_exempted_room` confirms that exempted rooms correctly yield `affected=False` and `status="EXEMPTED"`.

---

### BUG-003: Potential `IndexError` and misleading evaluation in `get_affected_classes`
- **Bug ID:** BUG-003
- **Affected Feature / File:** `app/api/routes/feed.py` (lines 95–98)
- **Severity:** P2 — Medium
- **Reproduction Steps:**
  1. Call `GET /api/v1/students/{student_id}/affected-classes` when announcements list is empty.
  2. Route attempts to execute `room_impact_service.check_timetable_conflict(entry, announcements[0], None)`.
  3. Raises `IndexError: list index out of range`. If announcements exist, it evaluates against an arbitrary notice at index 0.
- **Root Cause:** Fallback branch for unimpacted classes evaluated against `announcements[0]` without checking list length.
- **Proposed Fix:** Directly append a clean `ClassImpactResult(entry=entry, affected=False, status="NO_MATCH", explanation="No room or schedule conflicts detected in recent announcements.")` without coupling to index 0. Guard against empty announcements list.
- **Fix Status:** Fixed
- **Verification Evidence:** Endpoint returns valid `NO_MATCH` for unaffected timetable entries and handles empty announcement datasets without crashing.

---

### BUG-004: Announcement detail endpoint omits live notice `source` and `source_url`
- **Bug ID:** BUG-004
- **Affected Feature / File:** `app/api/routes/announcements.py` (line 82)
- **Severity:** P2 — Medium
- **Reproduction Steps:**
  1. Ingest a live UMS announcement (e.g. ID `ANN-UMS-46437`, source `ums_official`).
  2. Query `GET /api/v1/announcements/ANN-UMS-46437`.
  3. Inspect JSON response. `source` is reset to default `"historical"` and `source_url` is `None`.
- **Root Cause:** Instantiation of `AnnouncementDetail` omitted passing `source=target.source` and `source_url=target.source_url`.
- **Proposed Fix:** Pass `source=target.source` and `source_url=target.source_url` to `AnnouncementDetail`.
- **Fix Status:** Fixed
- **Verification Evidence:** `GET /api/v1/announcements/{id}` returns correct `source="ums_official"` and canonical external portal URL.

---

### BUG-005: Inconsistent `attachment_names` type handling in `RetrievalService`
- **Bug ID:** BUG-005
- **Affected Feature / File:** `app/services/retrieval_service.py` (line 154)
- **Severity:** P2 — Medium
- **Reproduction Steps:**
  1. Ingest an announcement where metadata or candidate contains `attachment_names` as a Python `list`.
  2. Execute hybrid search query.
  3. Line 154 executes `meta.get("attachment_names", "").split(",")`.
  4. Raises `AttributeError: 'list' object has no attribute 'split'`.
- **Root Cause:** Assumed `attachment_names` in metadata is always a comma-separated string rather than checking if it is already a list.
- **Proposed Fix:** Use safe polymorphic normalization:
  `raw_names = meta.get("attachment_names", [])`
  `names_list = raw_names if isinstance(raw_names, list) else [x.strip() for x in str(raw_names).split(",") if x.strip()]`
- **Fix Status:** Fixed
- **Verification Evidence:** Hybrid search handles both list and string metadata gracefully without exceptions.

---

### BUG-006: Personalization scoring ignores explicit student group exclusions
- **Bug ID:** BUG-006
- **Affected Feature / File:** `app/services/personalization_service.py`
- **Severity:** P2 — Medium
- **Reproduction Steps:**
  1. Student is in Year 1 B.Tech Mechanical Engineering.
  2. Announcement contains `metadata.exclusions = "First year students are strictly not eligible"` or `"Excludes Mechanical Engineering"`.
  3. Calculate score using `score_announcement(student, ann, metadata)`.
  4. Notice the score was not penalized and explanation did not report exclusion.
- **Root Cause:** `score_announcement` only checked positive matches (`target_year`, `target_program`, `target_dept`), ignoring negative exclusion rules.
- **Proposed Fix:** Inspect `metadata.exclusions`. If student's program, department, or year is explicitly excluded, apply an exclusion penalty (`year_score = 0.05` or `dept_score = 0.05`) and append an explicit exclusion notice to the explanation.
- **Fix Status:** Fixed
- **Verification Evidence:** Unit test confirms excluded student receives heavily penalized priority score and clear explanation banner.

---

### BUG-007: Lack of dedicated deadlines and upcoming dates API endpoint
- **Bug ID:** BUG-007
- **Affected Feature / File:** `app/api/routes/announcements.py`
- **Severity:** P3 — Low
- **Reproduction Steps:**
  1. A student wants to see all upcoming deadlines across the university.
  2. No API endpoint exists to query or sort notices by extracted deadlines.
- **Root Cause:** Feature was only partially implemented in the data model without a dedicated API route.
- **Proposed Fix:** Add `GET /api/v1/announcements/deadlines` returning announcements that contain deadlines, sorted chronologically and distinguishing upcoming vs expired notices.
- **Fix Status:** Fixed
- **Verification Evidence:** Endpoint returns sorted deadlines list with ISO dates and urgency ratings.

---

### BUG-008: Embedding service lacks offline fallback mode for local testing
- **Bug ID:** BUG-008
- **Affected Feature / File:** `app/services/embedding_service.py`
- **Severity:** P3 — Low
- **Reproduction Steps:**
  1. Run embedding or vector store tests in an offline environment without `GEMINI_API_KEY`.
  2. Service raises `ValueError("Gemini API key missing")`, blocking deterministic local testing.
- **Root Cause:** No offline deterministic pseudo-embedding fallback was available when uncredentialed.
- **Proposed Fix:** Provide an offline deterministic embedding generator (hashing text into a normalized 768-dim float vector) when `settings.GEMINI_API_KEY` is empty or offline mode is requested.
- **Fix Status:** Fixed
- **Verification Evidence:** Vector store operations succeed deterministically even without an active internet connection or paid API key.

---

### BUG-009: Frontend chatbot assistant does not render multi-line markdown or line breaks
- **Bug ID:** BUG-009
- **Affected Feature / File:** `app/static/app.js`
- **Severity:** P3 — Low
- **Reproduction Steps:**
  1. Open chatbot tab at `http://127.0.0.1:8000`.
  2. Ask a question returning multi-bullet evidence.
  3. Bullets and citations were displayed without proper line wrapping or formatted source chips.
- **Root Cause:** Plain `element.textContent` or raw innerHTML assignment without newline conversion.
- **Proposed Fix:** Format chatbot messages with line-break conversion, bold tags, and distinct source chip badges.
- **Fix Status:** Fixed
- **Verification Evidence:** Assistant answers display formatted bullet points and highlighted citations.

---

### BUG-010: Missing automated test coverage for RAG grounding, deadlines, and room exemptions
- **Bug ID:** BUG-010
- **Affected Feature / File:** `tests/`
- **Severity:** P2 — Medium
- **Reproduction Steps:**
  1. Review existing test suite.
  2. There were no unit tests verifying that RAG says "insufficient evidence" when no match is found, no tests for room exemptions, and no tests for deadline filtering.
- **Root Cause:** Test suite only covered historical baseline modules.
- **Proposed Fix:** Create comprehensive new test suites (`tests/test_rag_grounding.py`, `tests/test_room_exemptions.py`, `tests/test_deadlines.py`, `tests/test_acceptance_workflows.py`).
- **Fix Status:** Fixed
- **Verification Evidence:** Test suite expanded from 33 to 55 passing automated tests.

---

### BUG-011: Chatbot frontend input loss, missing request debouncing, and unhandled non-200 responses
- **Bug ID:** BUG-011
- **Affected Feature / File:** `app/static/app.js`, `app/static/styles.css`
- **Severity:** P2 — Medium
- **Reproduction Steps:**
  1. Submit a query in `#chatInput` when backend is busy or returns an error.
  2. Notice `input.value = ""` was executed immediately before fetch, wiping user input.
  3. Notice clicking Send repeatedly while request was loading fired duplicate concurrent API requests.
  4. Non-200 API responses (e.g. 400 or 500) caused `data.answer.replace(...)` to crash with `TypeError: Cannot read properties of undefined (reading 'replace')`.
- **Root Cause:** Missing submission debouncing, early input clearing, and missing `!res.ok` status validation before parsing response.
- **Proposed Fix:** Disable input and button with "Thinking... ⏳" indicator; preserve input on failure with retry button; validate `res.ok` and display structured error message.
- **Fix Status:** Fixed
- **Verification Evidence:** Send button disables during loading; non-200 errors render clear error card with retry button; input restores on failure.

---

### BUG-012: Conversational greetings matched irrelevant announcements and lacked multi-turn conversation context
- **Bug ID:** BUG-012
- **Affected Feature / File:** `app/services/chat_service.py`, `app/services/retrieval_service.py`, `app/models/chat.py`
- **Severity:** P2 — Medium
- **Reproduction Steps:**
  1. User typed "Hello" in the chatbot.
  2. System performed lexical search for "hello" across 7,370+ announcements, finding "From Hello to Hired: A Workshop on Interview Skills", returning 5 irrelevant sources and attachment warnings.
  3. Follow-up questions (e.g. "What is the deadline for this?") failed because previous conversation history was never passed into the Gemini prompt.
- **Root Cause:** Missing conversational greeting filter, lack of stopwords filtering in lexical scoring, and omitted multi-turn history context in Gemini prompt.
- **Proposed Fix:** Add conversational greeting detector returning a polite assistant introduction without citations; filter English stopwords in lexical scoring; inject previous conversation history (up to 6 turns) into the grounded Gemini prompt.
- **Fix Status:** Fixed
- **Verification Evidence:** Querying "Hello" returns polite assistant greeting with 0 sources (`sources=[]`); multi-turn test passes in `test_rag_grounding.py`.

---

### BUG-013: UMS Sync False Success Reporting and Missing Up-To-Date Nuance ("Synced 0 notices")
- **Bug ID:** BUG-013
- **Affected Feature / File:** `app/services/ums_sync_service.py`, `app/services/ums_source.py`, `app/api/routes/ums.py`, `app/static/index.html`, `app/static/app.js`
- **Severity:** P1 — High (Core Data Ingestion Pipeline & Reporting)
- **Reproduction Steps:**
  1. Start application or trigger UMS sync via button or 1-click browser extractor snippet.
  2. Background/startup worker or initial sync already ingested the active notices.
  3. On subsequent sync or import, UI displayed: `"🎉 Synced 0 notices into LPU SmartNotice!"` or `"Synced (0 new, 0 rev)"`.
  4. User assumed zero notices were retrieved from the university source, or that the pipeline was failing.
- **Root Cause:**
  1. **Misleading Success Metric in UI:** The frontend and snippet evaluated only `resJson.inserted_count`. When identical notices were fetched, SQLite content-hash deduplication appropriately skipped them (`skipped_count > 0`), but `inserted_count` was `0`. The UI unconditionally displayed a celebration message with `0`, masking that records were fetched and up to date.
  2. **Coarse Status Classification:** `UMSSyncService.ingest_announcements()` returned `status = "SUCCESS"` unconditionally even when `fetched_count == 0` or when all records were unchanged.
  3. **ASP.NET WebMethod & DOM Parsing Gaps:** Slicing non-list dictionary responses (e.g., `d: {"Table": [...]}`) caused unhandled `TypeError` exceptions in `_fetch_from_ums_portal`. HTTP 302 redirects to login were unhandled, leading to JSON decode failures. Missing safe Phase 3 diagnostic logging prevented visibility into the upstream HTTP response.
- **Proposed Fix:**
  1. Implement granular sync status codes: `SUCCESS` (new/revised records), `UP_TO_DATE` (all fetched notices already present in DB), `EMPTY_SOURCE` (upstream returned 0 notices), `AUTH_REQUIRED` / `AUTH_EXPIRED`, and `FAILED`.
  2. Return descriptive messages and full metrics: `status`, `message`, `fetched_count`, `candidate_count`, `inserted_count`, `updated_count`, `skipped_count`, `failed_count`, `indexed_count`.
  3. Add safe Phase 3 diagnostic logging (method, URL, status code, content-type, byte size, redirect detection, top-level keys, candidate count) without exposing cookies, passwords, or PII.
  4. Upgrade `_fetch_from_ums_portal` to handle ASP.NET stringified JSON, DataSets (`Table`), nested dicts, and redirects to login.
  5. Upgrade browser console snippet and HTML parser to extract from ASP.NET PageMethods, table rows, cards, panels, and accordion containers with attachment URL preservation.
  6. Update UI buttons and alerts to show truthful feedback (e.g., `"⚡ All 25 announcements are already up to date in SmartNotice! (0 new, 25 current)"`).
- **Fix Status:** Fixed
- **Verification Evidence:** All 25 UMS unit/integration tests pass. Live test on server returns `HTTP 200`, `status: "UP_TO_DATE"`, `message: "All 25 announcements are already up to date in SmartNotice."`, `fetched_count: 25`, `skipped_count: 25`, `inserted_count: 0`. Initial import returns `status: "SUCCESS"`, `message: "Successfully synced: 20 new, 5 unchanged."`, `inserted_count: 20`.

