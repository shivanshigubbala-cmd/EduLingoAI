
```markdown
# Architecture

Task ref: `P0-TEAM1`. Related decisions: `P0-SHI1` (auth), `P0-SHR1` (LLM/vector stack).

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
- **Language handling** — Multilingual input (Hindi, Telugu, code-mixed) is confirmed in scope. OCR/extraction preserves the source language so `topic_tree/` extraction doesn't need a translation step.

## Topic-tree extraction

_Feeds: `P2-SHI4`, `P2-SHI5` — owner Shivanshi_

LLM prompt (Ollama) turns parsed text into the topic-tree JSON defined in
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
- **Answering:** Ollama generates a grounded answer that cites the specific syllabus topic/unit it drew from — not generic model knowledge.
- **Memory:** once history exceeds the token budget, older sessions are summarized (`P5-SHI9`) so context never silently drops syllabus material the student still needs.
- **UI:** responses stream token-by-token; user can scroll back and reopen a past session (`P5-SHI10`).

## Quiz + feedback loop

_Feeds: `P6-SHR8`/`P6-SHR9` (Shreya), `P6-SRE11` (Sreehitha), `P6-SHI11` (Shivanshi), `P7-TEAM3`/`P7-SHI12`_

- Quiz generator (Ollama) weights questions toward topics with lower `mastery` scores.
- Auto-grading: MCQs graded exactly; short answers scored via an LLM rubric with a written score + rationale.
- Results screen shows a per-topic score bar and flags topics below a mastery threshold.
- **Feedback loop:** quiz results update `mastery` scores and trigger schedule regeneration with no manual intervention — low-scoring topics reappear earlier in the regenerated plan. After a milestone or quiz, the assistant proactively suggests the next check-in (`P7-SHI12`).

## LLM + vector-DB stack

_Owner: Shivanshi — P0-SHR1_

### Chosen LLM API: Ollama (self-hosted, local)

**Models:** `llama3.2:3b` (used for topic-tree extraction; may need a larger model for
higher-complexity tasks like RAG answering or quiz generation — see Open items below).

**Why Ollama over Anthropic Claude:**
Switched from the original Claude decision (see git history / PR discussion) primarily
for cost — Ollama runs entirely locally with no per-token API charges, which matters for
a student project without a production budget. Runs via `ollama.Client` against a local
Ollama server (default `http://localhost:11434`, configurable via `OLLAMA_HOST`).

**Known tradeoff — multilingual quality:** the original Claude decision was made
specifically for its multilingual performance across English, Hindi, Telugu, and
code-mixed input (Hinglish, Tenglish), which the project's repo name and design commit
to supporting. Small local Llama models are generally weaker at this than Claude,
particularly for lower-resource languages like Telugu. **This is an accepted, open
tradeoff** — not yet validated with real multilingual test cases. Flagging as a risk to
revisit before RAG/quiz generation ship, since a quality regression there is more
user-visible than in one-time topic-tree extraction.

### Embedding model: OpenAI `text-embedding-3-small`

**Why:** Best price/performance multilingual embedding model available via API. Supports 50+ languages including Hindi. Uses a separate provider from the LLM, so `EMBEDDING_API_KEY` is independent of `LLM_API_KEY`.

**Open question:** the LLM provider switched to Ollama for cost reasons — worth confirming
whether the embedding model (OpenAI, billed separately) is also moving to a local/free
alternative, or staying as-is since embedding costs were already noted as negligible.

**Known multilingual weaknesses:** Telugu (and other lower-resource Dravidian languages) have noticeably lower embedding quality compared to Hindi or English. Retrieval accuracy for Telugu-only queries may be lower — this is a known limitation of the model's training data distribution. Mitigation: if Telugu retrieval quality proves insufficient in testing, consider fine-tuning embeddings or adding a retrieval reranker as a follow-up in a later phase.

### Vector store: Qdrant (self-hosted)

**Why:** Already provisioned in `docker-compose.yml` as the `vector-store` service. Qdrant is open-source, self-hosted (no per-query vector DB costs), supports payload filtering for multi-tenant collections, and has a mature Python client (`qdrant-client`). Running inside Docker alongside the app keeps data local and avoids vendor lock-in.

### Cost / rate-limit notes

- **Main cost driver:** with the LLM now self-hosted via Ollama, the primary remaining external cost is the OpenAI embedding API — RAG chat and quiz generation no longer incur per-token LLM charges.
- **Ollama hosting note:** running larger models locally requires adequate RAM/GPU on whatever machine serves inference — worth confirming `llama3.2:3b` is sufficient for RAG/quiz quality, or whether a larger local model (with correspondingly higher hardware needs) will be required.
- **OpenAI embedding pricing:** Check current pricing at https://openai.com/pricing — `text-embedding-3-small` is the cheapest tier. Embedding costs are negligible compared to what LLM costs would have been.
- **Cost mitigation strategies:** since Ollama removes per-token cost entirely, the main remaining lever is embedding call volume — cache frequently-retrieved embeddings where appropriate.

## End-to-end flow

```
Signup/Login (Auth)
   │
   ▼
Upload (PDF/image) ──► Ingestion (extraction/OCR) ──► Topic-tree extraction (Ollama)
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
   │           (Qdrant retrieval + Ollama, grounded answers)   │
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

- [x] Multilingual vs English-only — resolved, multilingual (Hindi, Telugu, code-mixed) confirmed in scope.
- [x] Backend framework — Python/FastAPI, confirmed via P0-SRE2.
- [ ] **LLM provider switch (Claude → Ollama)** — code and docs now updated; still need to validate multilingual output quality with real Hindi/Telugu/code-mixed test inputs before RAG/quiz generation ship.
- [ ] Embedding model — confirm whether OpenAI `text-embedding-3-small` stays, or also moves to a local/free alternative now that the LLM has.
- [ ] Replace the ASCII flow with a proper diagram once the team is happy with the shape.
```

