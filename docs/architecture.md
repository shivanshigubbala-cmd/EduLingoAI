# Architecture

Task ref: `P0-TEAM1`. Related decisions: `P0-SHI1` (auth), `P0-SHR1` (LLM/vector stack).

> ⚠️ Open question before this doc is finalized: the Open Risks sheet in the WBS lists
> an "English-only" constraint, but the LLM section below (and the repo name/README)
> designs for multilingual input (Hindi, Telugu, code-mixed). **Confirm with the team
> which is actually in scope** and update the WBS Open Risks sheet to match before
> sign-off — this changes how `ocr/` and `topic_tree/` need to behave.

## Auth stack

_Owner: Shreya — P0-SHI1_

### Password auth
Email + password. Passwords hashed with `passlib[bcrypt]` — never stored in plaintext.

### OAuth
Google only for v1. Covers the OAuth requirement without adding scope; most students
already have a Google account. Implemented server-side with `authlib`.

### Sessions
Backend issues a JWT (`python-jose`) on successful login or OAuth callback, set as an
**httpOnly, secure cookie**. The frontend never reads or stores the token directly — it
just calls backend auth endpoints and the browser carries the session automatically.
This avoids `localStorage`/XSS exposure and matches the `JWT_SECRET`,
`OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET` fields already defined in `config.py`.

### Protected routes
Backend middleware verifies the JWT cookie on every request to a protected endpoint
(feeds P1-SRE4). Frontend middleware checks a `/me` call and redirects to `/login` on
failure (feeds P1-SHI3).

### Wireframes
Login and signup pages both offer email/password plus "Continue with Google".
See `docs/wireframes/login-signup.svg`.

## Ingestion (upload → text)

_Feeds: `P2-SHR2` (upload endpoint), `P2-SHR3` (PDF extraction), `P2-SHR4` (OCR) — owner Shreya_

- **Upload endpoint** accepts pdf/png/jpg, stores the file, returns a `document_id`.
- **Typed-PDF extraction** preserves page numbers so later citations (RAG) can point back to a specific page.
- **Handwriting OCR** transcribes handwritten notes; scans below a confidence threshold get a `confidence_flag` so the student can review/correct before the topic tree is built on top of it, rather than silently producing a wrong tree.
- **Language handling** — *depends on the multilingual question above.* If English-only: detect language early, reject non-English input with a clear message. If multilingual: OCR/extraction must preserve the source language so `topic_tree/` extraction (which uses Claude, already multilingual-capable per the LLM section) doesn't need a translation step.

## Topic-tree extraction

_Feeds: `P2-SHI4`, `P2-SHI5` — owner Shivanshi_

LLM prompt (Claude) turns parsed text into the topic-tree JSON defined in
`docs/schema.md` (`subject → unit → topic → subtopic`, `mastery` field). Persisted per
`user_id` + `document_id`. This is the single most load-bearing artifact in the
system — everything downstream (diagnostic, scheduling, RAG, quiz) reads it.

## Diagnostic + mastery scoring

_Feeds: `P3-SRE6`/`P3-SRE7` (Sreehitha), `P3-SHI6` (Shivanshi)_

- Capped, adaptive question generator — question *n+1* is chosen based on the answer to question *n*, not a fixed static list (default ~8 questions spanning the topic tree).
- Every topic in the tree gets a 0–1 `mastery` score once the diagnostic completes, written back onto the topic-tree structure.

## Scheduling

_Feeds: `P4-SHI7`/`P4-SHI8` (Shivanshi), `P4-SHR6` (Shreya)_

Priority algorithm takes `mastery` scores + hours/day + exam date → an ordered daily
topic plan, front-loading weak topics. Regenerating a schedule versions the previous
plan rather than overwriting it, so a student can see how the plan changed.

## RAG (doubt-answering chat)

_Feeds: `P5-SRE9`/`P5-SRE10` (Sreehitha), `P5-SHR7` (Shreya), `P5-SHI9`/`P5-SHI10` (Shivanshi)_

- **Embeddings:** syllabus chunks and chat turns are embedded per user with OpenAI `text-embedding-3-small` (see LLM section for known Telugu-quality caveat if multilingual is confirmed in scope) and stored in Qdrant.
- **Retrieval:** given a doubt, pulls the relevant syllabus topic + related past turns.
- **Answering:** Claude generates a grounded answer that cites the specific syllabus topic/unit it drew from — not generic model knowledge.
- **Memory:** once history exceeds the token budget, older sessions are summarized (`P5-SHI9`) so context never silently drops syllabus material the student still needs.
- **UI:** responses stream token-by-token; user can scroll back and reopen a past session (`P5-SHI10`).

## Quiz + feedback loop

_Feeds: `P6-SHR8`/`P6-SHR9` (Shreya), `P6-SRE11` (Sreehitha), `P6-SHI11` (Shivanshi), `P7-TEAM3`/`P7-SHI12`_

- Quiz generator (Claude) weights questions toward topics with lower `mastery` scores.
- Auto-grading: MCQs graded exactly; short answers scored via an LLM rubric with a written score + rationale.
- Results screen shows a per-topic score bar and flags topics below a mastery threshold.
- **Feedback loop:** quiz results update `mastery` scores and trigger schedule regeneration with no manual intervention — low-scoring topics reappear earlier in the regenerated plan. After a milestone or quiz, the assistant proactively suggests the next check-in (`P7-SHI12`).

## LLM + vector-DB stack

_Owner: Shivanshi — P0-SHR1_

### Chosen LLM API: Anthropic Claude

**Models:** `claude-sonnet-4-20250514` (primary, complex reasoning) / `claude-haiku-3` (fast, cost-sensitive tasks like RAG chat turns and quiz generation).

**Why Claude over OpenAI GPT:**
Claude models exhibit strong multilingual performance across English, Hindi, Telugu, and code-mixed inputs (Hinglish, Tenglish) without requiring a separate translation layer. Anthropic's models handle code-mixed text natively — users can type "Mughal Empire ke baare mein batao yaar" or "రామాయణం story meaning enti" and get accurate, in-language responses. Claude also has a larger context window (200k tokens) which helps when stuffing multiple retrieved chunks into RAG prompts. Anthropic's API is straightforward and well-documented.

### Embedding model: OpenAI `text-embedding-3-small`

**Why:** Best price/performance multilingual embedding model available via API. Supports 50+ languages including Hindi. Uses a separate provider from the LLM, so `EMBEDDING_API_KEY` is independent of `LLM_API_KEY`.

**Known multilingual weaknesses:** Telugu (and other lower-resource Dravidian languages) have noticeably lower embedding quality compared to Hindi or English. Retrieval accuracy for Telugu-only queries may be lower — this is a known limitation of the model's training data distribution. Mitigation: if Telugu retrieval quality proves insufficient in testing, consider fine-tuning embeddings or adding a retrieval reranker as a follow-up in a later phase.

### Vector store: Qdrant (self-hosted)

**Why:** Already provisioned in `docker-compose.yml` as the `vector-store` service. Qdrant is open-source, self-hosted (no per-query vector DB costs), supports payload filtering for multi-tenant collections, and has a mature Python client (`qdrant-client`). Running inside Docker alongside the app keeps data local and avoids vendor lock-in.

### Cost / rate-limit notes

- **Main cost driver:** RAG chat (retrieval-augmented conversation with long-term memory) and quiz generation — these make the most LLM API calls with potentially long prompt+completion token counts. Ingestion (PDF processing, topic-tree extraction) runs infrequently and is not the primary cost concern.
- **Anthropic pricing:** Check current pricing at https://www.anthropic.com/pricing — rates change; do not hardcode prices in the codebase.
- **OpenAI embedding pricing:** Check current pricing at https://openai.com/pricing — `text-embedding-3-small` is the cheapest tier. Embedding costs are negligible compared to LLM costs.
- **Rate limits:** Anthropic enforces per-API-key rate limits (requests/min, tokens/min) that vary by plan tier. Implement exponential backoff and queueing in the RAG pipeline. OpenAI embedding limits are similarly tier-based.
- **Cost mitigation strategies:** Use `claude-haiku-3` (the smaller/faster model) for high-volume, low-complexity tasks like RAG chat turns and quiz question generation. Reserve `claude-sonnet-4-20250514` for complex reasoning tasks. Cache frequently-retrieved embeddings and LLM responses where appropriate.

## End-to-end flow

```
Signup/Login (Auth)
   │
   ▼
Upload (PDF/image) ──► Ingestion (extraction/OCR) ──► Topic-tree extraction (Claude)
   │                                                          │
   │                                                          ▼
   │                                            Topic tree persisted (per user)
   │                                                          │
   │                                                          ▼
   │                                            Diagnostic (adaptive, capped)
   │                                                          │
   │                                                          ▼
   │                                            Mastery scoring (per topic, 0–1)
   │                                                          │
   │                                                          ▼
   │                                            Study schedule (weak topics first)
   │                                                          │
   ├────────────────► RAG doubt-answering chat ◄──────────────┤
   │           (Qdrant retrieval + Claude, grounded answers)   │
   │                                                          ▼
   │                                            Quiz generation (weighted to weak areas)
   │                                                          │
   │                                                          ▼
   │                                            Auto-grading + score analysis
   │                                                          │
   │                                                          ▼
   └─────────────────────────────────────────► Feedback loop: mastery update
                                                 → schedule regenerated
```

## System diagram

_Add a visual diagram (e.g. Mermaid or an image in this folder) once the architecture is agreed — the ASCII flow above can serve as the source for it._

## Open items before sign-off

- [ ] **Multilingual vs English-only** — resolve the contradiction above, update Open Risks sheet.
- [ ] Backend framework — confirm Node/Express vs FastAPI (repo currently shows Python test/config files under `backend/`, suggesting FastAPI/Python — update this doc once confirmed).
- [ ] Replace the ASCII flow with a proper diagram once the team is happy with the shape.
