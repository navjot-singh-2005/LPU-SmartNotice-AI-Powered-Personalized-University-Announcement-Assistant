# REST API Reference — LPU SmartNotice

Base URL: `http://127.0.0.1:8000/api/v1`

## 1. System & Health Endpoints

### `GET /health`
Returns system status, active models, dataset quality report, and vector index summary.

**Response Example:**
```json
{
  "status": "healthy",
  "app_name": "LPU SmartNotice",
  "version": "1.0.0",
  "api_key_configured": true,
  "generation_model": "gemini-3.1-flash-lite",
  "embedding_model": "gemini-embedding-2",
  "dataset_summary": {
    "total_records": 7350,
    "with_attachments": 3108
  },
  "vector_index_summary": {
    "total_indexed_documents": 25
  }
}
```

### `GET /index/status`
Returns status of persistent ChromaDB vector store.

---

## 2. Announcements Endpoints

### `GET /announcements`
Paginated listing of announcements.
- **Query Params:** `page` (int), `page_size` (int), `search` (string), `attachment_only` (bool).

### `GET /announcements/search`
Hybrid semantic and lexical search.
- **Query Params:** `q` (string, required), `top_k` (int, default 5), `category` (string, optional).

### `GET /announcements/{announcement_id}`
Retrieve announcement by ID with extracted structured metadata.

---

## 3. Grounded RAG Chatbot Endpoint

### `POST /chat`
Submits a query to the grounded AI assistant.

**Request Payload:**
```json
{
  "query": "When are 3rd year B.Tech exams starting?",
  "student_id": "STU-101",
  "top_k": 5
}
```

**Response Example:**
```json
{
  "answer": "Mid-Term examinations for 3rd Year B.Tech CSE students will start on 15th October 2026 [Source ID: ANN-20261001-a1b2c3d4]. Exam rooms are allocated in Block 34 (Rooms 34-101 to 34-110).",
  "sources": [
    {
      "announcement_id": "ANN-20261001-a1b2c3d4",
      "title": "Mid-Term Examination Schedule",
      "similarity_score": 0.892,
      "attachment_present": true,
      "decision_completeness": "ATTACHMENT_MISSING"
    }
  ],
  "attachment_warning": "Notice 'Mid-Term Examination Schedule' references attachment (Seating_Plan.pdf), but attachment contents are unavailable."
}
```

---

## 4. Personalization & Timetable Endpoints

### `GET /students/{student_id}/feed`
Returns personalized announcement feed ranked for specified student profile.

### `GET /students/{student_id}/affected-classes`
Evaluates student timetable entries against announcements for room and schedule collisions.

---

## 5. Feedback Endpoint

### `POST /feedback`
Records student relevance feedback (`is_relevant: true/false`).

---
*Return to [Root README](../README.md)*
