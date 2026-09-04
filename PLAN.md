# Plan

Full context and rationale: `docs/FOUNDATION.md`, `docs/decisions.md`. Original approved
plan snapshot: `~/.claude/plans/sequential-herding-scone.md` (session 2026-09-04). This file
is the living version — update it as phases complete or scope shifts.

## Phase 0 — Foundation (in progress)
- [x] Repo scaffold, docs/ audit system, FOUNDATION.md, DATA_DICTIONARY.md
- [ ] Pydantic schemas: `ChunkMetadata` (with provenance + topic_id FK + published_date +
      `tags: dict` extension field + `is_current`/`superseded_by` — DECIDE-09/11),
      `TextChunk`, `PYQQuestion` (mcq/descriptive discriminated, same `tags` field)
- [ ] `data/core.db` init: `exams`, `papers`, `topics`, `content_types`, `pyq_bank`,
      `chunk_tags` (EAV side table, DECIDE-09)
- [ ] Seed registry rows for exams that already exist elsewhere: `upsc_prelims_gs`,
      `upsc_mains_gs`, `essay`, `ethics`, `ies`, `rbi_grade_b`, `upsc_eco_opt` — plus
      placeholder rows for `upsc_law_optional`/`upsc_eco_optional` (ASSUME-01)
- [ ] Port `scripts/parsers/` from Devthorium verbatim (7 files, proven, format-agnostic)

## Phase 1 — Ingestion + auto-labeling
- Header-aware two-stage chunker (markdown-header split + recursive fallback, page numbers
  preserved) — replaces Recall's flat word-slider; required for Law/Econ integrity
- Auto-labeling: generalize `ingest_pyq.py`'s Haiku classify-batch pattern to detect
  content_type + exam/paper/topic_id, for both prose and PYQs (Mains and MCQ)
- Ollama `nomic-embed-text` embeddings
- Incremental/resumable ingestion (hash-based skip-list, same pattern as Recall's
  `ingestion_log.json`) so re-running ingest after new uploads only processes new files
- `published_date` captured at ingest time where derivable (filename year, doc metadata,
  or explicit CLI flag for a batch)

## Phase 2 — Hybrid retrieval + API
- `LocalHybridEngine`: dense (LanceDB vector) + BM25 (LanceDB FTS) + RRF(k=60) + FlashRank
  rerank. **`k`/token-budget is a caller-supplied param, not a hardcoded default**
  (DECIDE-08) — batch calls (model-answer generation) request a generous budget, interactive
  calls (topic browse) request a small one. Never truncate a chunk mid-content to fit a
  budget — drop whole lower-ranked chunks instead.
- **Score floor** (DECIDE-10): chunks below a similarity/rerank threshold are excluded; if
  nothing clears it, return an explicit "insufficient grounding" result, never a silent
  fallback to ungrounded generation.
- Recency: soft boost for `content_type.is_time_sensitive` chunks (DECIDE-07), **plus** a
  hard `is_current`/`superseded_by` exclusion once a newer source supersedes an older one
  for the same topic/indicator (DECIDE-11).
- Trust-weighted grounding: `source_type = ai_generated` chunks are deprioritized/excluded
  from grounding by default (don't let AI output silently become "ground truth" for more
  generation).
- FastAPI: `/search` (hybrid chunk query, budget param), `/pyq` (structured bank query by
  exam/paper/topic/year/format), `/exams`, `/topics?exam_id=`, `/papers?exam_id=`
  (DECIDE-12), `/topic/{topic_id}/brief` (composite: top explanation chunks + mcq_pyqs +
  mains_pyqs for that topic — the "explain X + give PYQs" use case), `/ingest` (admin-only,
  local)
- `scripts/inventory.py` — prints live counts per exam/paper/topic/content_type
- **Pending Rahul's call (AUDIT-001 Q1/Q2/Q3) before finalizing this phase:** Contextual
  Retrieval at ingest time, parent-document/auto-merging retrieval, citation-verification
  aggressiveness.

## Phase 3 — Migrate + cut over Recall
- Re-ingest Recall's content root + `pyq_questions` through the new pipeline from source
  (not a direct Chroma copy — RISK-02)
- Swap `backend/routes/quiz.py`'s `fetch_chunks()`/`get_collection()` (quiz.py:622-629) to
  call `/search` instead of local Chroma
- Point `pyq.py`/`/quiz/pyq` at `/pyq`
- Validate: compare old vs new top-k on ~10 known subtopics before deleting old pipeline
  (approval gate — see FOUNDATION.md)
- No new Recall UX needed — `/quiz/start`+exam-sim, `/quiz/generate`+session/diagnostic,
  and `pyq.py` already cover timed/topic-wise/subject-wise/full-length/PYQ-browse

## Phase 4 — Batch sync + Scribe grounding
- Sync script (re-runnable, idempotent — mitigates RISK-01): generalizes the existing hack
  in `generate_answers.py` (currently direct cross-repo Chroma read, hardcoded to papers
  `ge_03`/`ge_04` only) into a real pull from Nyaya Core's API for Scribe's full exam scope
- Write into Scribe's already-existing, currently-unused `source_documents`/
  `document_chunks` tables (`scripts/upsc/01_init_upsc_db.py:335-363`) — `embedding_slot`
  stores a reference to Nyaya Core's `chunk_id`, not a local embedding
- Rewire `generate_answers.py` to read local synced chunks for all exams
- Merge draft migrations m059-m063, aligning `source_type` values to Nyaya Core's enum
- `model_answers.data_points[].source` becomes a real citation (source_doc + page_number)

## Phase 5 — New UX hooks
- Scribe: "read a concept" browse view over synced `document_chunks`, with page citations
- Recall: none needed (Phase 3 already covers it)

## Phase 6 — Extensibility hardening
- Document/script "new exam = registry row + PDFs in a folder + run ingest"
- Law Optional / Econ Optional ingestion (once Rahul sources PDFs) = first real end-to-end
  test of that promise
- BUG-035 (Scribe: 128 junk GS Mains PYQ rows) fixed as a side effect of re-ingesting
  through the new pipeline's source validation
