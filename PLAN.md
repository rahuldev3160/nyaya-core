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
- [x] Fixed all 7 ported parsers to return `list[(page_number, text)]` instead of a joined
      string (BUG-02 — page boundaries were silently lost, caught before any consumer used
      them) — `src/ingestion/parsers/*.py`
- [x] Header-aware two-stage chunker (heading-line split + atomic-block recursive fallback,
      page numbers preserved) — replaces Recall's flat word-slider; required for Law/Econ
      integrity. Stage-1 sections persisted to the `sections` table (DECIDE-14) — each
      Stage-2 chunk carries `section_id` back to its parent. `exam_id` is caller-supplied,
      not Haiku-classified (DECIDE-17). — `src/ingestion/chunker.py`, `tests/test_chunker.py`
      (4 tests: statute-boundary integrity, table-row atomicity, paragraph-boundary
      splitting, page/section persistence end-to-end — all passing)
- [x] Seeded `topics` table from Devthorium's real `syllabus.json` (DECIDE-18) — 271 rows
      for `upsc_prelims_gs`. Other 7 exams still unseeded; `enrich.load_topics()` raises
      rather than silently proceeding for those. — `scripts/seed_topics.py`
- [x] **One combined Haiku call per chunk** (cost control, DECIDE-13): generalizes
  `ingest_pyq.py`'s classify-batch pattern to do THREE things in one shot — (a) detect
  content_type + topic_id (exam_id is caller-supplied, DECIDE-17), (b) write the
  Contextual Retrieval blurb (`context_prefix`, DECIDE-13) using cached full-document
  context, (c) for PYQs, the existing question extraction. Uncertain classification (no
  topic match, PYQ missing year/correct_option) raises `ReviewNeededError` rather than
  guessing (DECIDE-10's principle applied to ingestion). Live-tested against the real
  Haiku API: correct topic match, sensible context_prefix, and confirmed prompt caching
  actually hits (`cache_creation` on chunk 1 of a doc, `cache_read` on chunk 2+) — the
  cost control DECIDE-13 exists for is verified working, not just assumed. —
  `src/ingestion/enrich.py`, `prompts/enrich_chunk_{system,user}.txt`,
  `tests/test_enrich.py` (7 tests, all passing)
- [x] Ollama `nomic-embed-text` embeddings — embed `context_prefix + content`, not raw
      content alone (that's the point of Contextual Retrieval). Writes to LanceDB's
      `chunks` table via `merge_insert` (upsert by `chunk_id`, not append) so re-running
      ingestion over the same document updates rather than duplicates. — `src/ingestion/
      embed.py`, `tests/test_embed.py` (2 tests, real Ollama calls, throwaway table)
- [x] Incremental/resumable ingestion (hash-based skip-list, same pattern as Recall's
      `ingestion_log.json` — path+size+mtime sha256, `data/ingestion_log.json`, saved after
      every file so a mid-batch crash doesn't lose progress) so re-running ingest after new
      uploads only processes new/changed files. A chunk Haiku flags as uncertain
      (`ReviewNeededError`) doesn't abort the batch — appended to
      `data/flagged_chunks.jsonl` for manual review, run continues. — `scripts/ingest.py`
- [x] `published_date` captured at ingest time (filename year regex, or an explicit
      `--published-date` CLI flag for a whole batch — doc-metadata extraction not built,
      no real source document tested it against yet). `is_current`/`superseded_by`
      (DECIDE-11) deferred — no re-ingestion-of-a-newer-doc scenario exists yet to need it.
- [x] Cost/usage logging on every ingestion batch (input/output/cache-write/cache-read
      token totals printed at the end of a run) — `scripts/ingest.py`
- [x] End-to-end pipeline verified with a real smoke run (synthetic Article 21/22 `.docx`,
      throwaway DB/LanceDB copies so real project data stayed untouched): 2 sections
      persisted, 2 chunks correctly classified to `right_to_freedom` and written to
      LanceDB, 0 false-positive PYQ extraction, 0 chunks flagged. `tests/test_ingest.py`
      (8 tests, pure-logic: hashing, skip-list, parser detection, date inference — a
      word-boundary regex bug caught here: `\b` doesn't fire between `_` and a digit, e.g.
      "report_2023", fixed with a digit-lookaround instead)

**Phase 1 complete.** Next: Phase 2 (hybrid retrieval + API) — needs real content ingested
first to be meaningfully testable; only `upsc_prelims_gs` has a topic taxonomy seeded today.

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
