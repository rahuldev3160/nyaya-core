# Decisions

### DECIDE-01 — New standalone repo {#decide-01}
**Date:** 2026-09-04 | **Session:** S1 | **Status:** Active

**Decision:** Nyaya Core is its own repo, not built inside Devthorium (Recall) or
Descriptive-exams (Scribe).
**Rationale:** Rahul wants one platform that generalizes to future exams beyond UPSC/IES/RBI.
Building it inside either product repo would couple it to that product's release cycle and
deployment target (Scribe is on Railway; this platform is local-only).
**Rejected:** Building inside Devthorium (it already owns ingestion+Chroma) — rejected
because it would still couple the platform's lifecycle to Recall's, and Recall's repo is
scoped as "10-day UPSC Prelims prep" per its own CLAUDE.md, not a general platform.
**Assumptions baked in:** none.

### DECIDE-02 — Replace Recall's pipeline outright {#decide-02}
**Date:** 2026-09-04 | **Session:** S1 | **Status:** Active

**Decision:** Recall's ChromaDB/naive-chunker pipeline is retired and replaced, not run
alongside the new one during a validation window.
**Rationale:** Personal-use only right now, no live-traffic risk. Running both in parallel
adds sync/drift complexity for no real benefit at this scale.
**Rejected:** Parallel run with gradual cutover — rejected as unnecessary overhead given
no external users.

### DECIDE-03 — Scribe consumes via batch sync {#decide-03}
**Date:** 2026-09-04 | **Session:** S1 | **Status:** Active

**Decision:** Scribe does not call Nyaya Core's API live. A sync script pulls a snapshot
into Scribe's own DB.
**Rationale:** Scribe is deployed on Railway; Nyaya Core is local-only (matches the spec's
zero-cloud-cost premise). Railway cannot reach a Mac-only service without exposing it.
Matches Recall's existing "pregenerate everything, zero live API calls" philosophy, and
generalizes an ad-hoc pattern `generate_answers.py` already uses for 2 of ~7 exams.
**Rejected:** Deploying Nyaya Core's API somewhere reachable — rejected for now, breaks
zero-cost local-first premise and adds an uptime dependency; revisit only if live grounding
becomes a hard requirement.
**Consequence:** RISK-01 (freshness lag for Scribe).

### DECIDE-04 — topic_id is a shared FK, not free text {#decide-04}
**Date:** 2026-09-04 | **Session:** S1 | **Status:** Active

**Decision:** Chunk metadata's topic field is a foreign key into the `topics` registry
table, the same one `pyq_bank` uses — not an independent free-text string per store.
**Rationale:** Rahul's core use case ("explain Indian monsoon + give PYQs on it") requires
a single topic query to pull grounding chunks AND both PYQ formats. Free-text tags on each
store independently would drift ("Indian Monsoon" vs "monsoon system") and silently break
that join.
**Rejected:** Free-text topic tags with fuzzy matching at query time — rejected as fragile;
a shared registry is cheap to build correctly now vs. debugging silent retrieval misses later.

### DECIDE-05 — LanceDB over ChromaDB {#decide-05}
**Date:** 2026-09-04 | **Session:** S1 | **Status:** Active

**Decision:** New chunk store is LanceDB, not a continuation of Recall's ChromaDB.
**Rationale:** LanceDB has native hybrid dense+FTS search in one store. Chroma's retrieval
in Recall today is dense-only (`quiz.py:622-629`) — no BM25/hybrid — because bolting FTS
onto Chroma is awkward. Matches the spec Rahul is targeting.

### DECIDE-06 — Ollama nomic-embed-text over sentence-transformers {#decide-06}
**Date:** 2026-09-04 | **Session:** S1 | **Status:** Active

**Decision:** Embeddings via local Ollama `nomic-embed-text` (768-dim), replacing Recall's
in-process `sentence-transformers/all-MiniLM-L6-v2` (384-dim).
**Rationale:** Matches the spec Rahul is targeting; zero marginal cost either way.
**Rejected:** Keeping sentence-transformers (simpler, no daemon dependency) — rejected to
follow the spec choice; flagged as an operational cost in FOUNDATION.md (Ollama must be
running locally for ingestion and query-time embedding).
**Assumptions baked in:** ASSUME — Ollama daemon overhead is acceptable for a local-only,
single-user tool. Revisit if this becomes a friction point.

### DECIDE-07 — Recency signal in ranking {#decide-07}
**Date:** 2026-09-04 | **Session:** S1 | **Status:** Active

**Decision:** Add `published_date`/`as_of_date` to chunk and PYQ metadata; mark certain
content types (`current_affairs`, `monthly_report`, `yearly_report`) as time-sensitive in
the `content_types` registry; apply a mild recency boost in ranking for those types.
**Rationale:** Rahul's adaptability requirement — uploading a newer report should be
reflected when a topic is queried, not buried under older but equally-relevant-scoring text.
Pure semantic similarity has no notion of "newer is better" for time-sensitive content.
**Rejected:** Hard recency filter (always return newest N) — rejected, would break relevance
for evergreen content (statute text, NCERT concepts) where recency is irrelevant; boost is
scoped to time-sensitive content types only.

### DECIDE-08 — Retrieval budget (k / token limit) is caller-supplied, never a hardcoded default {#decide-08}
**Date:** 2026-09-04 | **Session:** S2 | **Status:** Active

**Decision:** `/search` and `/topic/{id}/brief` take a caller-specified budget. No global
`final_k` constant in the engine. Never truncate a chunk's content mid-string to fit a
budget — drop whole lower-ranked chunks instead.
**Rationale:** Root cause of a confirmed real bug (AUDIT-001 §2) — Scribe's
`generate_answers.py` truncates chunks to 400 chars, Recall's `quiz.py` caps at 8 chunks
regardless of task. A live MCQ-explanation call and a batch Mains-model-answer call have
very different context needs; one fixed budget serves neither well.
**Rejected:** A generous single global default (e.g. always 15 chunks) — rejected as
wasteful for cheap/fast calls and still potentially insufficient for the heaviest ones.

### DECIDE-09 — Extensible tagging: JSON field + EAV side table, not schema migration {#decide-09}
**Date:** 2026-09-04 | **Session:** S2 | **Status:** Active

**Decision:** Add one `tags` JSON/dict field to `chunks` and `pyq_bank` (Phase 0), plus a
companion SQLite `chunk_tags(chunk_id, tag_key, tag_value)` EAV table for tags that need
fast indexed lookup.
**Rationale:** Rahul's explicit ask — add a new index later (e.g. exam_name, difficulty)
without touching existing schema/code. Fixed columns for known dimensions stay fast; the
tags path absorbs anything ad hoc with zero migration.
**Rejected:** Schema migration per new dimension — rejected, disruptive on LanceDB
specifically (columnar, not a clean ALTER TABLE ADD COLUMN operation like SQLite).
**Open:** LanceDB's exact JSON/struct filtering support needs verifying during Phase 1
build, not assumed here.

### DECIDE-10 — Score floor + explicit "insufficient grounding" signal {#decide-10}
**Date:** 2026-09-04 | **Session:** S2 | **Status:** Active

**Decision:** Chunks below a similarity/rerank threshold are never used as grounding. If
nothing clears the bar, the API returns an explicit "insufficient grounding" result instead
of silently falling back to ungrounded generation.
**Rationale:** Recall's current fallback (`quiz.py:466-469`) literally tells the LLM to
"generate from canonical syllabus knowledge" when no chunks match — an explicit hallucination
invitation. RESEARCH-05: abstaining on ungrounded claims is the single most reliable
hallucination mitigation.
**Rejected:** Always returning the top-k regardless of score — rejected, defeats the point
of a floor.

### DECIDE-11 — `is_current`/`superseded_by` on time-sensitive content {#decide-11}
**Date:** 2026-09-04 | **Session:** S2 | **Status:** Active

**Decision:** Extend DECIDE-07's soft recency boost with a hard flag for content types
marked time-sensitive: when a newer source supersedes an older one for the same
topic/indicator, the older one is excluded from grounding by default, not just ranked lower.
**Rationale:** RESEARCH-05's documented failure mode — a valid old citation presented as
current fact ("the citation exists but the grounding does not"). A soft boost alone doesn't
prevent this; an old Economic Survey figure can still outrank a new one on raw similarity.
**Rejected:** Recency boost alone (original DECIDE-07 scope) — insufficient per research,
upgraded here.

### DECIDE-12 — Browse endpoints added to the API surface {#decide-12}
**Date:** 2026-09-04 | **Session:** S2 | **Status:** Active

**Decision:** Add `/topics?exam_id=` and `/papers?exam_id=` to Phase 2's API, alongside the
already-planned `/exams` and `/topic/{id}/brief`.
**Rationale:** "Navigable" was a stated requirement; the original API list only had
whole-registry listing and one composite lookup, no way to drill down exam → papers → topics.

### ASSUME-01 — Law/Econ Optional sourcing deferred {#assume-01}
**Date:** 2026-09-04 | **Session:** S1

Rahul will source Law Optional and Economics Optional PDFs himself, later. Schema
(`exams`/`papers` registry rows) is ready from Phase 0; ingestion is deferred until source
material exists. Not a blocker for Phases 0-4.
