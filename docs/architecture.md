# Architecture

_Owner: Team — P0-TEAM1_

To be filled in during Phase 0. Must cover, end to end:

- **Auth** — stack decision (see P0-SHI1), session handling
- **Ingestion** — upload -> storage -> PDF text extraction / OCR -> topic-tree extraction
- **RAG** — vector store choice, embedding model, retrieval pipeline, cost/rate-limit notes (see P0-SHR1)
- **Scheduling** — mastery-gap-driven priority scheduling
- **Quiz flow** — generation, grading, feedback loop back into scheduling

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

## System diagram

_Add a diagram (e.g. Mermaid or an image in this folder) once the architecture is agreed._
