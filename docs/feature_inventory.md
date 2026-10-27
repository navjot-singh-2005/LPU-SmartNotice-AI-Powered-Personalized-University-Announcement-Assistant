# LPU SmartNotice — Complete Feature Inventory

**Document Version:** 1.0.0  
**Audit Date:** October 2026  
**System:** LPU SmartNotice (Lovely Professional University Announcement Intelligence Platform)  
**Corpus:** 7,350 Historical Circulars + Live Real-Time Ingested Circulars  

---

## 1. Feature Status Matrix

| ID | Feature Name | Primary Module / Path | API Route | Frontend Element | Status | Verification Evidence |
| :--- | :--- | :--- | :--- | :--- | :---: | :--- |
| **FEAT-001** | Application Startup & Lifecycle | `app/main.py` | `GET /api/v1/health` | Status widget | **VERIFIED** | Lifespan context manager starts DB, in-memory cache, background sync worker without blocking. |
| **FEAT-002** | Historical Dataset Ingestion | `app/services/dataset_service.py` | `GET /api/v1/announcements` | Feed cards, pagination | **VERIFIED** | 7,350 circulars parsed; deterministic IDs (`ANN-YYYYMMDD-hash`); thread-safe memory caching. |
| **FEAT-003** | Live UMS Ingestion & Portal Sync | `app/services/ums_source.py`<br>`app/services/ums_sync_service.py` | `POST /api/v1/ums/sync`<br>`GET /api/v1/ums/status` | UMS Sync Card (`#btnSyncUms`) | **VERIFIED** | Real-time fetch from `happenings.lpu.in` & `lpude.in`; ASP.NET WebMethod parsing; status nuances (`SUCCESS`, `UP_TO_DATE`). |
| **FEAT-004** | 1-Click Browser Console Extractor | `app/static/index.html`<br>`app/api/routes/ums.py` | `POST /api/v1/ums/import-json` | `#consoleSnippet` | **VERIFIED** | Injects into student UMS session; queries ASP.NET endpoints; passes extracted DOM/JSON to backend. |
| **FEAT-005** | Manual Paste Announcement Import | `app/services/ums_sync_service.py` | `POST /api/v1/ums/paste-notice` | `#pasteModal` | **VERIFIED** | Allows raw text notice ingestion; deduplicates, normalizes, extracts metadata, and upserts to ChromaDB. |
| **FEAT-006** | Manual Session Cookie Ingestion | `app/services/ums_sync_service.py` | `POST /api/v1/ums/set-cookie` | `#cookieModal` | **VERIFIED** | Accepts authenticated `ASP.NET_SessionId`; tests connection against `Announcement.aspx`; never logs raw secret. |
| **FEAT-007** | SHA-256 Deduplication & Revisions | `app/services/deduplication_service.py` | SQLite `live_announcements` | None (Backend) | **VERIFIED** | Content hash prevents duplicates; revision counter increments on modified titles/content. |
| **FEAT-008** | Google GenAI Structured Extraction | `app/services/extraction_service.py` | SQLite `extracted_metadata` | Category badges, tags | **VERIFIED** | Extracts category, summary, target audience, deadlines, rooms, urgency, attachment completeness; robust heuristic fallback. |
| **FEAT-009** | Dense Vector Embeddings | `app/services/embedding_service.py` | None (Internal Service) | None (Backend) | **VERIFIED** | `gemini-embedding-2` generating 768-dim normalized vectors; offline hash pseudo-embedding fallback. |
| **FEAT-010** | ChromaDB Semantic Indexing | `app/services/vector_store_service.py` | Collection `lpu_announcements` | None (Storage) | **VERIFIED** | Persistent vector store with metadata filtering (`category`, `urgency`, `attachment_present`, `source`). |
| **FEAT-011** | Hybrid RAG Search (Semantic + BM25) | `app/services/retrieval_service.py` | `POST /api/v1/chat` | Search bar, Chatbot | **VERIFIED** | Reciprocal Rank Fusion (RRF); stopword filtering; polymorphic `attachment_names` handling. |
| **FEAT-012** | Grounded AI Chatbot Assistant | `app/services/chat_service.py` | `POST /api/v1/chat` | `#chatInput`, `#chatMessages` | **VERIFIED** | Grounded in retrieved evidence; bracketed citations `[Source ID: ...]`; conversational greeting filter; honest refusal on lack of evidence. |
| **FEAT-013** | Student Profile Personalization | `app/services/personalization_service.py` | `GET /api/v1/feed/{student_id}/feed` | Profile selector | **VERIFIED** | Multi-factor weighted score (year, dept, interests, urgency, recency); negative student group exclusion matching. |
| **FEAT-014** | Upcoming Deadlines Discovery | `app/services/dataset_service.py` | `GET /api/v1/announcements/deadlines` | Deadlines list/filter | **VERIFIED** | Chronological sorting; status separation (`upcoming`, `expired`, `all`); ISO `YYYY-MM-DD` date parsing. |
| **FEAT-015** | Timetable Room Conflict & Exemptions | `app/services/room_impact_service.py` | `GET /api/v1/students/{id}/affected-classes` | Room Conflict tab | **VERIFIED** | Normalizes room identifiers; expands ranges (`34-101 to 34-105`); recognizes explicit `exempted_rooms` and regex exception phrases. |
| **FEAT-016** | PII Masking & Privacy Guard | `app/services/pii_redaction_service.py` | Pre-LLM filter | None (Internal) | **VERIFIED** | Redacts student phones, email addresses, and registration numbers before external model inference. |
| **FEAT-017** | Interactive Glassmorphism UI | `app/static/index.html`, `app.js`, `index.css` | Static mount `/` | Browser dashboard | **VERIFIED** | Responsive layout, dark glass theme, search, category filters, live notice badges, formatted chat markdown, error handling. |

---

## 2. API Contract Inventory

| Route | Method | Request Body / Params | Response Model | Description |
| :--- | :---: | :--- | :--- | :--- |
| `/api/v1/health` | `GET` | None | `HealthResponse` | Operational status, dataset metrics, vector DB statistics. |
| `/api/v1/announcements` | `GET` | `page`, `limit`, `category`, `urgency`, `search`, `has_attachment`, `source` | `PaginatedAnnouncements` | Paginated announcements with dynamic filtering and search. |
| `/api/v1/announcements/{id}` | `GET` | `id: str` | `AnnouncementDetail` | Complete notice content, extracted metadata, attachments, provenance. |
| `/api/v1/announcements/deadlines` | `GET` | `page`, `limit`, `status` (`upcoming`, `expired`, `all`) | `PaginatedDeadlines` | Chronologically sorted university deadlines. |
| `/api/v1/chat` | `POST` | `ChatRequest` (`query`, `student_id`, `history`, `top_k`) | `ChatResponse` | Grounded AI answer, cited sources, attachment completeness warnings. |
| `/api/v1/chat/feedback` | `POST` | `FeedbackRequest` (`student_id`, `announcement_id`, `is_relevant`, `comments`) | `FeedbackResponse` | Persists user relevance feedback into SQLite. |
| `/api/v1/feed/{student_id}/feed` | `GET` | `student_id: str`, `limit: int` | `PersonalizedFeedResponse` | Ranked personalized announcements with transparent scoring factors. |
| `/api/v1/students/{student_id}/affected-classes` | `GET` | `student_id: str` | `ClassImpactListResponse` | Timetable room conflict and suspension analysis with exemption support. |
| `/api/v1/ums/status` | `GET` | None | `UMSStatusResponse` | Current connector status, session health check, last sync telemetry. |
| `/api/v1/ums/sync` | `POST` | `limit: int` (default 25) | `SyncResponse` | Triggers real-time ingestion from official feeds with truthful counts. |
| `/api/v1/ums/set-cookie` | `POST` | `CookieRequest` (`cookie_header`) | `CookieResponse` | Sets and verifies authenticated ASP.NET session cookie. |
| `/api/v1/ums/paste-notice` | `POST` | `PastedNoticeRequest` (`title`, `full_content`, `publication_date`, ...) | `SyncResponse` | Ingests a raw announcement directly into SQLite and ChromaDB. |
| `/api/v1/ums/import-json` | `POST` | `BrowserImportRequest` (`announcements: List[Dict]`) | `SyncResponse` | Bulk imports notices extracted via browser console snippet. |
| `/api/v1/ums/history` | `GET` | `limit: int` | `List[SyncHistoryItem]` | Historical audit log of all synchronization operations. |

---

## 3. Storage & Schema Inventory

### SQLite Database (`storage/smartnotice.db`)
- `live_announcements`: Persists live notices (`announcement_id`, `title`, `full_content`, `content_hash`, `revision_count`, `source`, `source_url`, `created_at`).
- `extracted_metadata`: Persists structured AI inferences (`category`, `summary`, `target_audience`, `deadlines`, `affected_rooms`, `urgency_level`, etc.).
- `student_profiles`: Seed profiles for evaluation (e.g. `STU-101` CSE 4th Year, `STU-102` ME 1st Year, `STU-103` MBA 2nd Year).
- `student_feedback`: User relevance ratings (`is_relevant`, `feedback_type`, `comments`).
- `ums_sync_history`: Synchronization run telemetry (`sync_id`, `status`, `message`, `fetched_count`, `candidate_count`, `inserted_count`, `updated_count`, `skipped_count`, `failed_count`, `indexed_count`).

### Vector Database (`storage/chroma_db`)
- **Collection:** `lpu_announcements`
- **Embedding Dimensions:** 768 float values (normalized).
- **Metadata Filters:** `category`, `urgency`, `attachment_present`, `source`, `publication_date`.
