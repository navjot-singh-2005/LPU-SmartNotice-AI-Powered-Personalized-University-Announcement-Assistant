# LPU SmartNotice — Five Sidebar Features Audit Report

**Date:** October 2026  
**Auditor:** Principal Software Architect, Senior Full-Stack & AI Engineer  
**System:** LPU SmartNotice (Lovely Professional University Announcement Intelligence Platform)  
**Corpus:** 7,350 Historical Announcements + Live University Ingestion  

---

## 1. Feature 1: Personalized Feed Audit

### Implementation Files
- **Backend:** `app/api/routes/feed.py`, `app/services/personalization_service.py`
- **Data Model:** `app/models/student.py` (`StudentProfile`), `app/models/announcement.py`
- **Frontend UI:** `app/static/index.html` (`#feedTab`, `#feedList`), `app/static/app.js` (`loadPersonalizedFeed()`, `renderNoticeCard()`)

### Current State & Baseline Findings
- **Positive:**
  - Multi-criteria weighted scoring algorithm: Year (25%), Department (20%), Interests (25%), Urgency (15%), Global (15%).
  - Negative student group exclusions (`metadata.exclusions`) penalize excluded groups down to 0.05.
  - Live real-time notices receive a +0.20 recency prominence boost.
  - Student selector (`#studentSelector`) triggers dynamic feed recalculation upon selection change.
- **Identified Gaps & Enhancement Opportunities:**
  - Lacked structured applicability tier categorization (`DEFINITELY_APPLICABLE`, `POTENTIALLY_RELEVANT`, `GENERAL_NOTICE`, `NOT_APPLICABLE`, `UNCERTAIN`).
  - Lacked explicit UI filter pills for applicability (e.g. `🎯 Applicable`, `⚡ Urgent`, `⏳ Upcoming Deadlines`, `📢 General`).
  - Feed items did not calculate days remaining until deadline or distinguish upcoming vs expired notices.

---

## 2. Feature 2: AI Assistant (RAG) Audit

### Implementation Files
- **Backend:** `app/api/routes/chat.py`, `app/services/chat_service.py`, `app/services/retrieval_service.py`
- **Data Model:** `app/models/chat.py` (`ChatRequest`, `ChatResponse`, `AnnouncementSourceReference`)
- **Frontend UI:** `app/static/index.html` (`#chatTab`, `#chatMessages`, `#chatInput`), `app/static/app.js` (`handleChatSubmit()`)

### Current State & Baseline Findings
- **Positive:**
  - Conversational greeting detector returns polite assistant message with 0 sources.
  - Multi-turn conversation history (`history: List[ChatMessage]`) preserves context across up to 6 turns.
  - Strict grounding prompt enforces citations `[Source ID: ANN-...]` and honest refusal when evidence is missing.
  - Debounced send button with loading indicator and graceful retry on API failure.
- **Identified Gaps & Enhancement Opportunities:**
  - Citation badges in the chatbot did not have click-to-open handlers to view full announcement details in the modal.
  - Lacked a "Clear Chat" button to reset multi-turn history.
  - LLM system prompt can be further reinforced to explicitly delineate verified announcement facts from general knowledge.

---

## 3. Feature 3: Search & Browse Audit

### Implementation Files
- **Backend:** `app/api/routes/announcements.py` (`GET /announcements`, `GET /announcements/search`), `app/services/dataset_service.py`
- **Frontend UI:** `app/static/index.html` (`#searchTab`, `#searchInput`, `#searchResults`), `app/static/app.js` (`executeSearch()`)

### Current State & Baseline Findings
- **Positive:**
  - Hybrid search combines dense vector retrieval (ChromaDB) and lexical keyword matching via Reciprocal Rank Fusion.
  - Basic title, content, and reference number search supported.
- **Identified Gaps & Enhancement Opportunities:**
  - The UI search tab only had a plain text input without category, urgency, attachment, or sorting dropdowns.
  - `/announcements/search` endpoint lacked pagination (`page`, `page_size`), urgency filtering, and sorting parameters (`relevance`, `newest`, `oldest`).
  - Missing filter reset and search pagination in `#searchResults`.

---

## 4. Feature 4: Room & Timetable Impact Audit

### Implementation Files
- **Backend:** `app/api/routes/feed.py` (`GET /students/{id}/affected-classes`), `app/services/room_impact_service.py`
- **Data Model:** `app/models/student.py` (`TimetableEntry`, `ClassImpactResult`)
- **Frontend UI:** `app/static/index.html` (`#timetableTab`, `#timetableList`), `app/static/app.js` (`loadAffectedClasses()`)

### Current State & Baseline Findings
- **Positive:**
  - Normalizes block-room formats (e.g. `34-105`) and expands ranges (`34-101 to 34-105`).
  - Correctly evaluates `metadata.exempted_rooms` and regex exception phrases ("except Room 34-105"), returning `affected=False, status="EXEMPTED"`.
  - Guarded against empty datasets without `IndexError`.
- **Identified Gaps & Enhancement Opportunities:**
  - Lacked explicit handling for notices referencing unavailable attachments ("refer to attached room list"), which should yield `ATTACHMENT_DEPENDENT` or `UNCERTAIN_DATA`.
  - Frontend lacked filtering pills (`All`, `Affected Only`, `Exempted`, `No Conflict`) to isolate impacted classes.
  - Lacked structured classification of impact type (`SUSPENSION`, `VENUE_CHANGE`, `EXAM_DUTY`, `RESCHEDULED`, `GENERAL_ALERT`).

---

## 5. Feature 5: System Dashboard Audit

### Implementation Files
- **Backend:** `app/api/routes/health.py`, `app/api/routes/ums.py`
- **Frontend UI:** `app/static/index.html` (`#healthTab`, `#metricsGrid`, `#umsSyncHistoryContent`), `app/static/app.js` (`loadHealthDashboard()`)

### Current State & Baseline Findings
- **Positive:**
  - Live metric cards: Total raw records (7,375), with attachments (3,108), indexed in ChromaDB (154), active Gemini model.
  - Real-time UMS synchronization audit log with status badges and candidate counts.
  - Live API status indicator in sidebar footer (`System Ready 🟢`).
- **Identified Gaps & Enhancement Opportunities:**
  - Health report dumped raw JSON in `<pre>` blocks rather than presenting an intuitive, visually structured diagnostic layout.
  - Lacked a breakdown of historical notices vs live UMS notices.
  - Lacked a one-click in-memory cache refresh / database synchronization trigger.
