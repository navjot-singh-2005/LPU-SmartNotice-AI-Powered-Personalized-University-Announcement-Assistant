# LPU SmartNotice — Five Sidebar Features Enhancements

**Date:** October 2026  
**Auditor / Engineer:** Principal Full-Stack Software Architect, Senior Python/FastAPI Engineer, AI/RAG Specialist  
**System:** LPU SmartNotice (Lovely Professional University Announcement Intelligence Platform)  
**Corpus:** 7,350 Historical University Circulars + Live Ingested Announcements  
**Test Suite Status:** 73/73 Tests Passing (100% Pass Rate across 12 test modules)  

---

## 1. Feature 1: Personalized Feed Enhancements

### Original Gaps & Deficiencies
- Scoring returned a single raw float priority score without structured categorization of applicability.
- Lacked explicit UI filter pills for students to filter by applicability tier or active deadlines.
- Circular deadlines were not calculated or evaluated for expiration.

### Implemented Improvements
1. **Applicability Tier Classification:**
   - Categorizes every notice into one of five mutually exclusive tiers:
     - `DEFINITELY_APPLICABLE`: Explicit year, degree program, or department positive match.
     - `POTENTIALLY_RELEVANT`: Partial match or strong student interest keyword overlap.
     - `GENERAL_NOTICE`: University-wide notice applicable across all student groups.
     - `NOT_APPLICABLE`: Explicit group exclusion or targeted year/department mismatch.
     - `UNCERTAIN`: Decision completeness is `ATTACHMENT_MISSING` or metadata is ambiguous.
2. **Deadline & Expiration Tracking:**
   - Extracted deadlines are normalized to ISO `YYYY-MM-DD`.
   - Days remaining are calculated dynamically (`days_remaining = (deadline_date - today).days`).
   - Expired notices are explicitly marked (`is_deadline_expired: True`) and visually flagged as `⛔ Deadline Expired`.
   - Active deadlines show remaining time (e.g. `⏳ Due: 2026-10-30 (4d left)`).
3. **Interactive Filter Pills in UI:**
   - Added filter pill buttons with real-time counts: `All Notices`, `🎯 Applicable`, `💡 Relevant`, `⚡ Urgent`, `⏳ Active Deadlines`, `📢 General`.
   - Clicking any pill filters the feed instantly without reloading.

---

## 2. Feature 2: AI Assistant (RAG) Enhancements

### Original Gaps & Deficiencies
- Clicking citation badges in chat answers did not open the announcement modal.
- Chat lacked a "Clear Chat" control to reset conversation memory.

### Implemented Improvements
1. **Interactive Clickable Citations:**
   - Bracketed source references `[Source ID: ANN-...]` are parsed into interactive buttons `<button class="inline-citation" onclick="viewAnnouncement('ANN-...')">`.
   - Clicking any citation immediately opens the full official announcement modal showing complete content, dates, and attachment details.
2. **Clear Chat History:**
   - Added `clearChatHistory()` handler and button in `#chatTab` header to reset multi-turn conversation memory.
3. **Grounding Prompt Enforcement:**
   - Clear delineation between university circular evidence and general knowledge; honest refusals when evidence is missing.

---

## 3. Feature 3: Search & Browse Enhancements

### Original Gaps & Deficiencies
- The search tab featured only a single text input and lacked category, urgency, attachment, or sorting options.
- The backend `/announcements/search` endpoint lacked pagination and sorting parameters.

### Implemented Improvements
1. **Rich Search & Browse Toolbar:**
   - Added Category dropdown (`ACADEMIC`, `PLACEMENT`, `EXAMINATION`, `EVENT`, `ADMINISTRATIVE`, `HOSTEL`).
   - Added Urgency dropdown (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
   - Added Has Attachments checkbox (`📎 With Attachments Only`).
   - Added Sorting dropdown (`Relevance (RRF)`, `Newest Date`, `Oldest Date`).
   - Added "Reset Filters" action button.
2. **Backend Search Route Upgrade:**
   - Upgraded `GET /api/v1/announcements/search` with parameters `category`, `urgency`, `attachment_only`, `sort_by`, `page`, `page_size`.
   - Returns paginated results with `total`, `page`, `page_size`, and `total_pages`.
   - Supported frontend search pagination via `#searchPagination`.

---

## 4. Feature 4: Room & Timetable Impact Enhancements

### Original Gaps & Deficiencies
- Lacked classification of impact types (`SUSPENSION`, `VENUE_CHANGE`, `EXAM_DUTY`, `RESCHEDULED`).
- Notices stating "refer to attached room list" did not flag attachment dependency.
- Frontend lacked filtering by impact status.

### Implemented Improvements
1. **Structured Impact Type Classification:**
   - Added `impact_type` classification to `ClassImpactResult`:
     - `SUSPENSION`: Class suspension, holiday, closure.
     - `VENUE_CHANGE`: Class relocated to another room.
     - `EXAM_DUTY`: Seating allocation for examinations.
     - `RESCHEDULED`: Timing adjusted.
     - `GENERAL_ALERT`: General block or maintenance notice.
2. **Attachment Dependency Flag:**
   - When announcements indicate room details are in an unretrieved attachment, returns `status="ATTACHMENT_DEPENDENT"` with clear advisory.
3. **Evidence Snippets:**
   - Added `evidence_text` field explaining exactly why the class was matched.
4. **Interactive Timetable Filter Pills:**
   - Added filter pills: `All Classes`, `🚨 Conflicts Only`, `🛡️ Exempted`, `📎 Attachment Dependent`, `✅ No Conflict`.

---

## 5. Feature 5: System Dashboard Enhancements

### Original Gaps & Deficiencies
- Health report only dumped raw JSON in `<pre>` tags.
- Lacked active subsystem status badges or a one-click in-memory cache refresh action.

### Implemented Improvements
1. **Subsystem Health Strip:**
   - Added top status bar monitoring `FastAPI: Running 🟢`, `SQLite: Connected 🟢`, `ChromaDB: Ready 🟢`, and `Google GenAI SDK: Configured 🟢`.
2. **Subsystem Diagnostic API:**
   - Upgraded `GET /api/v1/health` to return `subsystems` status and `sqlite_stats` (counts for live announcements, extracted metadata, student profiles, and sync runs).
3. **One-Click In-Memory Cache Reload:**
   - Implemented `POST /api/v1/health/cache-refresh` and dashboard button `⚡ Reload Cache` to force reload dataset and SQLite records on demand.
