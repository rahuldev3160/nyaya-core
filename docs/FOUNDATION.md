# Foundation

## Why this project exists
Nyaya Recall and Nyaya Scribe each need grounded content (study material, official
reports, PYQs) but today either have a crude, siloed pipeline (Recall) or none (Scribe).
Nyaya Core is the single platform both ground themselves on. See `PROJECT.md` and `PLAN.md`.

## Stack and why
- **Python** — matches both consumer repos (Recall, Scribe), reuses Recall's existing
  parsers directly.
- **LanceDB** (embedded, `data/lancedb/`) — native hybrid dense-vector + FTS in one store,
  no separate BM25 index to keep in sync. Chosen over Recall's current ChromaDB because
  Chroma has no native hybrid search — that gap is exactly why Recall's retrieval today is
  dense-only.
- **SQLite** (`data/core.db`) — structured registries and the PYQ bank. Relational shape
  fits question records (options, marks, year) far better than a vector store.
- **Ollama `nomic-embed-text`** (768-dim, local) — zero marginal cost, matches the spec
  Rahul is targeting. Replaces Recall's `sentence-transformers/all-MiniLM-L6-v2`; the two
  embedding spaces are not compatible, so cutover means full re-embedding, not a copy.
- **FlashRank** — in-process cross-encoder reranker, no extra service to run.
- **FastAPI** — internal API, consumed live by Recall (same machine) and by a sync script
  for Scribe (Railway, can't reach a local-only store — see DECIDE-03).

## Data model

Two linked stores, joined by a shared `topic_id` (not free text — see DECIDE-04):

1. **LanceDB `chunks` table** — prose from study material, official reports, current
   affairs, notes. One row per chunk: `chunk_id`, `content`, `vector`, `exam_id`,
   `paper_id`, `topic_id` (FK), `content_type` (FK), `source_doc`, `page_number`,
   `published_date`, `source_type`, `verified_by`, `reviewed_at`.
2. **SQLite `core.db`**:
   - `exams`, `papers`, `topics` — data-driven registries. A new exam is a new row, never
     a code change.
   - `content_types` — registry of what a document *is* (mains_pyq, mcq_pyq,
     official_report, study_material, current_affairs, model_answer, syllabus). Marks
     which types are time-sensitive (current_affairs, monthly/yearly reports) for the
     recency boost.
   - `pyq_bank` — one table for both Mains and MCQ questions (`question_format` discriminator).
     Carries `topic_id` (FK, same registry as chunks).

## System boundaries
- **Owns:** ingestion, chunking, labeling, embeddings, hybrid search, the PYQ bank, the
  provenance/verification layer.
- **Does not own:** user accounts, attempts, scores, sessions, quiz generation UX — those
  stay in Recall and Scribe. This platform is grounding data only, never user state.
- **Recall** calls this platform's API live (same machine, no network dependency issue).
- **Scribe** consumes via a re-runnable batch sync script into its own
  `source_documents`/`document_chunks` tables (already exist, unused — see DECIDE-02).

## Users and mental model
Sole user right now: Rahul, as both the aspirant and the operator. He uploads PDFs, runs
ingest, and expects: (a) the platform to figure out what kind of document it is and file
it correctly, (b) a topic query to return grounding text AND both PYQ formats together,
(c) freshness — newer material should be reflected, not buried under older but more
"relevant-sounding" text.

## Approval Gates
- Deleting Recall's existing ChromaDB pipeline (`scripts/ingest.py`, `chunker.py`,
  `embedder.py`, `vector_store/`) — only after Phase 3 validation passes.
- Any change to Scribe's live DB schema or merging its draft migrations (m059-m063) —
  Scribe's own CLAUDE.md already gates ALTER/DROP on existing tables; this project must
  follow that gate too when touching Scribe's repo.
- Spending money — Haiku classification at ingestion scale could add up; check cost before
  a large ingestion batch (hundreds+ of files).
- Anything that makes this platform reachable by anyone other than Rahul (a public API,
  a cloud deployment) — explicitly deferred, flagged in PROJECT.md as post-personal-use.
- Any irreversible action on source content (delete, overwrite ingestion log).
