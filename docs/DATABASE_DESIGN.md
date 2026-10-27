# Database Design — LPU SmartNotice

## 1. Overview
LPU SmartNotice uses a dual-database architecture:
1. **SQLite (`storage/smartnotice.db`):** Relational database for AI extraction caching, student profiles, user feedback, and indexing run metadata.
2. **ChromaDB (`storage/chroma_db`):** Vector database for 768-dimensional document embeddings and metadata filters.

```mermaid
erDiagram
    EXTRACTED_METADATA ||--o{ STUDENT_FEEDBACK : receives
    STUDENT_PROFILES ||--o{ STUDENT_FEEDBACK : submits

    EXTRACTED_METADATA {
        string announcement_id PK
        string content_hash
        string category
        string summary
        string urgency
        float confidence
        string decision_completeness
        string raw_json
    }

    STUDENT_PROFILES {
        string student_id PK
        string name
        string program
        int year
        string interests
    }

    STUDENT_FEEDBACK {
        int id PK
        string student_id FK
        string announcement_id FK
        boolean is_relevant
        string comments
    }

    INDEX_METADATA {
        string key PK
        string value
    }
```

## 2. Table Definitions

### `extracted_metadata`
Stores structured metadata extracted by Gemini to prevent repeating paid API calls.
- `announcement_id` TEXT PRIMARY KEY
- `content_hash` TEXT INDEXED
- `category` TEXT, `summary` TEXT, `urgency` TEXT
- `confidence` REAL, `decision_completeness` TEXT
- `raw_json` TEXT (Full JSON model dump)

### `student_profiles`
Pre-populated synthetic demo profiles for feed personalization.
- `student_id` TEXT PRIMARY KEY
- `name` TEXT, `program` TEXT, `year` INTEGER, `interests` TEXT

### `student_feedback`
Stores user feedback on recommendations to support future supervised ML training.
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `student_id` TEXT, `announcement_id` TEXT, `is_relevant` BOOLEAN

---
*Return to [Root README](../README.md)*
