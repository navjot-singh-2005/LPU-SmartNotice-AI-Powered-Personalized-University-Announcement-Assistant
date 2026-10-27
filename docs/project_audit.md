# LPU SmartNotice — Comprehensive Project Audit Report

**Date:** October 2026  
**Auditor:** Senior Software Architect, QA Automation & AI Engineer  
**Project:** LPU SmartNotice (Lovely Professional University Announcement Intelligence System)  
**Baseline Test Status:** 33/33 Tests Passing (Initial Audit)  
**Current Post-Repair Test Status:** 64/64 Tests Passing (100% Pass Rate across all 11 test modules)  
**Runtime Environment:** Python 3.12.6, Windows 10/11, FastAPI, ChromaDB, SQLite, Google GenAI SDK

---

## 1. Executive Summary

LPU SmartNotice is an AI-powered personalized university announcement intelligence platform designed for students of Lovely Professional University. The platform digests a historical corpus of ~7,350 official university circulars (~11.2 MB JSON), ingests real-time announcements from official LPU feeds, stores structured metadata in SQLite (`storage/smartnotice.db`), vector embeddings in ChromaDB (`storage/chroma_db`), and serves a rich responsive frontend dashboard.

This audit report establishes the architectural baseline, catalogues every discovered feature, evaluates security and performance profiles, records all identified defects, and maps out a systematic 10-stage repair and verification plan.

---

## 2. Architecture & Component Inventory

| Component | Technology | Primary Files | Role |
| :--- | :--- | :--- | :--- |
| **Backend Framework** | FastAPI (ASGI) | `app/main.py`, `app/api/routes/` | RESTful API endpoints with Swagger docs |
| **Configuration** | Pydantic BaseSettings | `app/core/config.py` | Environment loading from `.env` |
| **Database** | SQLite3 | `app/core/database.py`, `storage/smartnotice.db` | Relational store for live notices, extracted metadata, profiles, feedback, sync history |
| **Vector Store** | ChromaDB PersistentClient | `app/services/vector_store_service.py`, `storage/chroma_db` | Dense semantic vector indexing for RAG retrieval |
| **AI / LLM** | Google GenAI SDK | `app/services/extraction_service.py`, `app/services/chat_service.py` | Structured metadata extraction and grounded RAG assistant |
| **Embedding** | Google GenAI Embedding | `app/services/embedding_service.py` | 768-dim vector embeddings |
| **Deduplication** | SHA-256 Content Hash | `app/services/deduplication_service.py` | Exact duplicate elimination & revision detection |
| **Personalization** | Weighted Multi-Factor Scoring | `app/services/personalization_service.py` | Student profile matching (year, program, interests, urgency) |
| **Room Impact** | Regex & Range Parser | `app/services/room_impact_service.py` | Timetable conflict analysis for venue shifts and class suspensions |
| **UMS Connector** | REST Adapter | `app/services/ums_source.py`, `app/services/ums_sync_service.py` | Ingestion from official LPU feeds & UMS portal |
| **Frontend** | Vanilla HTML5/CSS3/ES6 | `app/static/index.html`, `app/static/app.js`, `app/static/index.css` | Interactive web dashboard |

---

## 3. Discovered Feature Inventory

### A. Application Startup & Configuration
- **Status:** PASS
- **Details:** FastAPI application initialized in `app/main.py` with lifespan context manager. SQLite database auto-initialized on startup. Static files served at `/static` and root `/`. Background auto-sync worker ingests live announcements non-blockingly upon startup.

### B. Announcement Data Pipeline
- **Status:** PASS with Optimization Opportunity
- **Details:** Historical dataset (`data/all_announcements_with_attachment_flag.json`) contains 7,350 valid announcements with publication dates ranging from 2020 through 2026. Deterministic IDs (`ANN-YYYYMMDD-hash`) prevent ID collisions.
- **Defect Identified (BUG-001):** Dataset was re-read and parsed from disk on every single request. Caching in memory is necessary to improve throughput.

### C. AI & Gemini Integration
- **Status:** PASS
- **Details:** Uses modern `google-genai` SDK (`genai.Client`) with model `gemini-3.1-flash-lite` and `gemini-embedding-2`. Keys are safely stored in `.env` and never logged or exposed to the client. PII redaction (`app/services/pii_redaction_service.py`) masks phone numbers, emails, and student registration numbers prior to LLM submission.

### D. Announcement Classification & Structured Extraction
- **Status:** PASS
- **Details:** `ExtractionService` extracts category, summary, target audience, year, program, department, deadlines, rooms, urgency, and attachment completeness adhering to `ExtractedAnnouncementMetadata` schema. Robust heuristic fallback ensures graceful operation when offline or uncredentialed.

### E. Embedding & ChromaDB
- **Status:** PASS
- **Details:** ChromaDB collection `lpu_announcements` stores dense vectors with rich metadata filters (`category`, `urgency`, `attachment_present`, `source`). Dimensionality check prevents index corruption.

### F. RAG & Grounded Question Answering
- **Status:** PASS
- **Details:** Hybrid retrieval combining semantic search (ChromaDB) and lexical term matching merged via Reciprocal Rank Fusion (RRF). Strict grounding prompt requires bracketed citations `[Source ID: ...]`. Insufficient evidence returns honest refusal without hallucination.

### G. Personalization & Feed Ranking
- **Status:** PASS with Enhancement Needed
- **Details:** Multi-criteria weighted scoring formula:
  $$\text{Score} = 0.25(\text{Year}) + 0.20(\text{Dept}) + 0.25(\text{Interests}) + 0.15(\text{Urgency}) + 0.15(\text{Global})$$
  Live real-time notices receive an explicit recency boost.
- **Defect Identified (BUG-006):** Explicit student exclusions (`metadata.exclusions`) were not factored into scoring.

### H. Deadlines & Urgency
- **Status:** PASS with Enhancement Needed
- **Details:** Dates normalized to ISO `YYYY-MM-DD`. Separation between publication date and deadline date.
- **Defect Identified (BUG-007):** Lacked a dedicated upcoming deadlines retrieval endpoint.

### I. Room Impact & Timetable Conflict
- **Status:** PASS with Defect
- **Details:** Normalizes room strings (`34-105`), expands ranges (`34-101 to 34-105`), and matches student timetable entries.
- **Defect Identified (BUG-002):** Ignored `metadata.exempted_rooms` and textual room exemptions, incorrectly flagging exempted rooms as affected.
- **Defect Identified (BUG-003):** Potential `IndexError` in route if announcements list is empty.

### J. LPU UMS & Live Feed Ingestion
- **Status:** PASS
- **Details:** Modular adapter queries official LPU public REST feeds (`happenings.lpu.in` and `lpude.in`) and supports authenticated ASP.NET portal session cookies when provided. Ingests without Cloudflare blocks, deduplicates by content hash, detects revisions, and embeds into ChromaDB.

### K. Backend APIs
- **Status:** PASS
- **Details:** Full OpenAPI/Swagger documentation available at `/docs`. Endpoints cover health, announcements, feed, timetable impact, chat, student profiles, feedback, and UMS sync management.
- **Defect Identified (BUG-004):** `get_announcement_by_id` lost `source` and `source_url` metadata.

### L. Frontend & User Experience
- **Status:** PASS
- **Details:** Premium dark glassmorphism UI with live UMS sync status badge (`Official Live Feed Active 🟢`), live notice cards with `🏛️ UMS Live` badge, interactive RAG chatbot, search & browse, and timetable conflict analyzer.
