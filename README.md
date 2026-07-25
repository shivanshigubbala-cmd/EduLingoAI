# Student AI Tool

An AI-powered study assistant: students upload their syllabus/notes, get a topic
tree extracted automatically, take an adaptive diagnostic, receive a
mastery-based study schedule, ask grounded doubts in a RAG-backed chat, take
generated quizzes, and have their schedule auto-replan based on quiz results.

## Core loop

upload → syllabus/topic-tree extraction → diagnostic → mastery scoring →
study schedule → RAG doubt-answering chat → quiz → feedback loop (replan)

## Repo structure

```
frontend/          Next.js app (auth pages, dashboard, chat, schedule, quiz, upload)
backend/
  src/
    auth/           login/session handling
    documents/      file upload + storage
    ocr/            PDF text extraction + handwriting OCR
    topic_tree/     LLM syllabus/topic extraction + persistence
    diagnostic/     adaptive question generation + mastery scoring
    scheduling/      priority scheduling + persistence
    rag/            vector store, retrieval, doubt-answering, memory summarization
    quiz/           quiz generation, auto-grading, score analysis
    feedback_loop/  quiz results -> mastery update -> schedule regeneration
    db/             models + migrations
  tests/
docs/
  architecture.md   system architecture (auth, ingestion, RAG, scheduling, quiz flow)
  schema.md         frozen topic-tree JSON schema (subject -> unit -> topic -> subtopic, mastery)
.github/workflows/  CI (lint/test on push)
docker-compose.yml  full stack: frontend, backend, DB, vector store
```

## Getting started

## Getting started

### 1. Environment
```bash
cp .env.example .env
```
Fill in real values for `JWT_SECRET`, `LLM_API_KEY`, `EMBEDDING_API_KEY` as needed.

### 2. Database (Docker)
```bash
docker compose up -d db
```

### 3. Backend

**Windows (PowerShell):**
```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**macOS/Linux:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run migrations:
```bash
alembic upgrade head
```

Start the API:
```bash
uvicorn src.main:app --reload
```

Backend runs at `http://localhost:8000`. Interactive API docs (Swagger):
`http://localhost:8000/docs`

Run tests:
```bash
pytest
```

### 4. Frontend
```bash
cd frontend
npm install
npm run dev
```
Frontend runs at `http://localhost:3000`.

### Full stack via Docker (alternative)
```bash
docker compose up
```

## Team

| Assignee  | Focus areas |
|---|---|
| Shivanshi | Auth, topic-tree extraction, mastery scoring, scheduling algorithm, RAG memory/chat polish |
| Sreehitha | Repo/infra scaffold, DB schema, app shell, backend API, diagnostic flow, RAG retrieval, quiz UI, CI |
| Shreya    | Auth wireframes, file upload/OCR, diagnostic chat UI, schedule UI, doubt-answering endpoint, quiz grading, deployment |
| Team      | Requirements/architecture, schema freeze, feedback loop, Dockerization, e2e testing, demo |

See `docs/architecture.md` and `docs/schema.md` for the specs referenced throughout
the task list. Task IDs (e.g. `P2-SHI4`) correspond to the project WBS.

## Status

## Status
Phase 0 (scaffold, DB schema, auth stack, LLM/vector-DB decisions, architecture
doc) and early Phase 1 (login/signup, session middleware, app shell, backend
API + auth token verification) are complete. See the WBS for full task
breakdown, critical path, and open risks.