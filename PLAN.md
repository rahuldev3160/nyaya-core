# Plan

Full context and rationale: `docs/FOUNDATION.md`, `docs/decisions.md`. Original approved
plan snapshot: `~/.claude/plans/sequential-herding-scone.md` (session 2026-09-04). This file
is the living version — update it as phases complete or scope shifts.

## Phase 0 — Foundation (complete)
- [x] Repo scaffold, docs/ audit system, FOUNDATION.md, DATA_DICTIONARY.md
- [x] Pydantic schemas: `ChunkMetadata` (with provenance + topic_id FK + published_date +
      `tags: dict` extension field + `is_current`/`superseded_by` — DECIDE-09/11),
      `TextChunk`, `PYQQuestion` (mcq/descriptive discriminated, same `tags` field) —
      `src/schema/models.py`
- [x] `data/core.db` init: `exams`, `papers`, `topics`, `content_types`, `pyq_bank`,
      `chunk_tags` (EAV side table, DECIDE-09), `sections` (parent-document layer, DECIDE-14)
      — `scripts/init_db.py`
- [x] Seed registry rows for exams that already exist elsewhere: `upsc_prelims_gs`,
      `upsc_mains_gs`, `essay`, `ethics`, `ies`, `rbi_grade_b`, `upsc_eco_opt` — plus a
      placeholder row for `upsc_law_optional` (ASSUME-01). **DECIDE-16: did not seed a
      second `upsc_eco_optional` placeholder — needs Rahul's confirmation whether it's
      distinct from `upsc_eco_opt` before Phase 1 touches Economics Optional content.**
- [x] Port `scripts/parsers/` from Devthorium verbatim (7 files, proven, format-agnostic)
      — `src/ingestion/parsers/`, import surface verified against all 7 functions

## Phase 1 — Ingestion + auto-labeling
- Header-aware two-stage chunker (markdown-header split + recursive fallback, page numbers
  preserved) — replaces Recall's flat word-slider; required for Law/Econ integrity. Stage-1
  header sections are persisted to the new `sections` table (DECIDE-14) — each Stage-2 chunk
  carries `section_id` back to its parent.
- **One combined Haiku call per chunk** (cost control, DECIDE-13): generalizes
  `ingest_pyq.py`'s classify-batch pattern to do THREE things in one shot — (a) detect
  content_type + exam/paper/topic_id (existing auto-labeling scope), (b) write the
  Contextual Retrieval blurb (`context_prefix`, DECIDE-13) using cached full-document
  context, (c) for PYQs, the existing question extraction. Use prompt caching (same document
  → many chunk calls) to keep this affordable.
- Ollama `nomic-embed-text` embeddings — embed `context_prefix + content`, not raw content
  alone (that's the point of Contextual Retrieval).
- Incremental/resumable ingestion (hash-based skip-list, same pattern as Recall's
  `ingestion_log.json`) so re-running ingest after new uploads only processes new files
- `published_date` captured at ingest time where derivable (filename year, doc metadata,
  or explicit CLI flag for a batch); `is_current`/`superseded_by` set when a newer doc for
  the same topic/indicator is ingested (DECIDE-11)
- Cost/usage logging on every ingestion batch (Haiku calls add up — surface it, don't guess)

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
- **Auto-merging** (DECIDE-14): after rerank, if ≥2 top chunks share a `section_id`, fetch
  that `sections.full_text` and substitute it for those chunks in the returned context,
  trimming to individual chunks if the merge would exceed the caller's budget (DECIDE-08).
- FastAPI: `/search` (hybrid chunk query, budget param, auto-merge applied), `/pyq`
  (structured bank query by exam/paper/topic/year/format), `/exams`, `/topics?exam_id=`,
  `/papers?exam_id=` (DECIDE-12), `/topic/{topic_id}/brief` (composite: top explanation
  chunks + mcq_pyqs + mains_pyqs for that topic — the "explain X + give PYQs" use case),
  `/verify_citation` (claim + chunk_id → entailment check, DECIDE-15 — consumer opts in per
  call, not run automatically), `/ingest` (admin-only, local)
- `scripts/inventory.py` — prints live counts per exam/paper/topic/content_type

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
- Since this is exactly the high-stakes, cache-forever generation DECIDE-15 targets:
  `generate_answers.py` calls `/verify_citation` on generated claims before insertion —
  Recall's cheap/frequent MCQ-drill generation does not

## Phase 5 — New UX hooks
- Scribe: "read a concept" browse view over synced `document_chunks`, with page citations
- Recall: none needed (Phase 3 already covers it)

## Phase 6 — Extensibility hardening
- Document/script "new exam = registry row + PDFs in a folder + run ingest"
- Law Optional / Econ Optional ingestion (once Rahul sources PDFs) = first real end-to-end
  test of that promise
- BUG-035 (Scribe: 128 junk GS Mains PYQ rows) fixed as a side effect of re-ingesting
  through the new pipeline's source validation
