# Database Schema (P0-SRE2)

Postgres schema for the six core tables. Defined in
`backend/src/db/models.py` (SQLAlchemy) and created by Alembic migration
`0001_initial_schema.py`.

## ERD

```mermaid
erDiagram
    USERS ||--o{ DOCUMENTS : uploads
    USERS ||--o{ SYLLABUS_TOPICS : owns
    USERS ||--o{ SESSIONS : owns
    USERS ||--o{ QUIZ_RESULTS : owns
    DOCUMENTS ||--o{ SYLLABUS_TOPICS : "extracted from"
    SYLLABUS_TOPICS ||--o{ SYLLABUS_TOPICS : "parent/child"
    SYLLABUS_TOPICS ||--o{ QUIZ_RESULTS : "tested on"
    SYLLABUS_TOPICS ||--o{ CHAT_MESSAGES : "referenced by"
    SESSIONS ||--o{ CHAT_MESSAGES : contains

    USERS {
        uuid id PK
        string email
        string hashed_password
        string name
        datetime created_at
    }
    DOCUMENTS {
        uuid id PK
        uuid user_id FK
        string filename
        string storage_path
        string mime_type
        enum status
        float ocr_confidence
        datetime uploaded_at
    }
    SYLLABUS_TOPICS {
        uuid id PK
        uuid user_id FK
        uuid document_id FK
        uuid parent_id FK
        string name
        enum level
        float mastery
        datetime created_at
        datetime updated_at
    }
    SESSIONS {
        uuid id PK
        uuid user_id FK
        enum type
        text summary
        datetime started_at
        datetime ended_at
    }
    CHAT_MESSAGES {
        uuid id PK
        uuid session_id FK
        enum role
        text content
        uuid topic_reference_id FK
        datetime created_at
    }
    QUIZ_RESULTS {
        uuid id PK
        uuid user_id FK
        uuid topic_id FK
        uuid quiz_id
        text question
        text student_answer
        bool is_correct
        float score
        text rationale
        datetime created_at
    }
```

## Design decisions

- **`syllabus_topics` is one flat, self-referential table**, not four
  separate tables per level (subject/unit/topic/subtopic). Each row has a
  `level` enum and an optional `parent_id`. This is what P2-SHI4/P2-SHI5
  write into after extraction, and what the frozen topic-tree JSON shape
  (below) serializes to/from for the LLM.
- **`sessions` is generic across diagnostic/chat/quiz**, so P5-SHI9's
  memory summarization and P5-SHI10's "reopen a past session" view can
  query one table regardless of session type.
- **`quiz_results` is one row per graded question**, not per quiz attempt,
  so P6-SHI11's per-topic score breakdown is a `GROUP BY topic_id`. Rows
  from the same attempt share a `quiz_id`.
- **`mastery` lives on `syllabus_topics`** (not a separate table) since
  every consumer (scheduling, quiz weighting, results screen) reads it
  keyed by topic, and P4-SHI7/P6-SHR8 both need current-mastery-per-topic
  as their primary input.

## Topic-tree JSON shape (P0-TEAM2 reference)

This is the shape the LLM extraction step (P2-SHI4) must output before it's
flattened into `syllabus_topics` rows:

```json
{
  "subject": "Physics",
  "units": [
    {
      "name": "Mechanics",
      "topics": [
        {
          "name": "Newton's Laws",
          "subtopics": ["First Law", "Second Law", "Third Law"],
          "mastery": null
        }
      ]
    }
  ]
}
```

`mastery` is populated per leaf node once the diagnostic (Phase 3) runs;
until then it's `null` (stored as SQL `NULL`), not `0`, so "not yet
assessed" is distinguishable from "assessed at zero."

## Running the migration

```bash
cd backend
export DATABASE_URL=postgresql://student_ai:student_ai@localhost:5432/student_ai_tool
alembic upgrade head
```

Or via the compose stack: `docker compose up db` then run the same
`alembic upgrade head` from inside the backend container.
