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

### DECIDE-13 — Adopt Contextual Retrieval {#decide-13}
**Date:** 2026-09-04 | **Session:** S2 | **Status:** Active

**Decision:** Every chunk gets a short (50-100 token) LLM-generated context blurb prepended
before embedding (Anthropic's technique, RESEARCH-02). Combined into the same ingest-time
Haiku call that already does content_type/topic classification (Phase 1), not a separate
call, to control cost. Raw chunk content is stored separately from the contextualized
(embedded) version — citations should point to the real source text, not the blurb.
**Rationale:** Rahul's explicit go-ahead. Proven 35-49% fewer retrieval failures, 67%
combined with reranking (already planned). One-time ingest cost, zero query-time cost.

### DECIDE-14 — Adopt parent-document/auto-merging retrieval from Phase 2 {#decide-14}
**Date:** 2026-09-04 | **Session:** S2 | **Status:** Active

**Decision:** Build the section-hierarchy now, not retrofit later. New `sections` table in
`core.db` (section_id, doc_id, exam_id, topic_id, content_type, heading, full_text,
page_start, page_end) — the parent is the chunker's Stage-1 markdown-header split (before
Stage-2 recursive sub-splitting), not the whole source document, so merged context stays
within a sane token range. Each `chunks` row carries `section_id` (FK). At retrieval: if
≥2 top-ranked chunks share a `section_id`, the engine returns that section's full text
instead of the disjoint chunks, budget permitting (DECIDE-08) — trims to individual chunks
if merging would exceed the caller's budget.
**Rationale:** Rahul's explicit go-ahead — structural fix for the confirmed "content too
short" bug (AUDIT-001 §2), cheaper to design into the schema now than retrofit once
chunks/pyq_bank rows already exist without parent linkage.
**Rejected:** Flat top-k-only retrieval (simpler, no schema change) — rejected per Rahul's
choice; the bug already happened once and the schema cost of fixing it now is small.

### DECIDE-15 — Citation verification: sampled, high-stakes only {#decide-15}
**Date:** 2026-09-04 | **Session:** S2 | **Status:** Active

**Decision:** Full claim-vs-source entailment verification is NOT run on every generation.
It's invoked selectively by the consumer for high-stakes, low-volume, cache-forever calls
(Scribe's Mains model-answer generation) — never for cheap, high-volume calls (Recall's MCQ
drills). Nyaya Core exposes a reusable verification helper (`/verify_citation`: claim +
chunk_id → entailment yes/no); consumers opt in per call.
**Rationale:** Rahul's explicit choice, matches the existing cost-scaling pattern already
used elsewhere in his projects (Haiku for cheap/frequent, Sonnet for expensive/rare —
`generate_answers.py`, `MainsEvaluator`). Full verification on everything would add an LLM
call to every single MCQ-drill generation, disproportionate cost for low-stakes output.
**Rejected:** Full verification everywhere (safest, rejected as disproportionate cost) and
no verification at all (cheapest, rejected as leaving hallucinated citations unchecked
where it matters most — Mains answers Rahul actually studies from).

### ASSUME-01 — Law/Econ Optional sourcing deferred {#assume-01}
**Date:** 2026-09-04 | **Session:** S1

Rahul will source Law Optional and Economics Optional PDFs himself, later. Schema
(`exams`/`papers` registry rows) is ready from Phase 0; ingestion is deferred until source
material exists. Not a blocker for Phases 0-4.

### DECIDE-16 — `upsc_eco_opt`/`upsc_eco_optional` are the same exam; standardized on `upsc_eco_optional` {#decide-16}
**Date:** 2026-09-05 (opened, S3) | **Resolved:** 2026-09-06 (S4) | **Status:** Closed

**Decision:** Confirmed by Rahul — one exam, not two. Renamed the seeded row from
`upsc_eco_opt` to `upsc_eco_optional` (zero dependent rows existed yet in `topics`/
`papers`/`sections`/`pyq_bank`, so this was a clean rename, not a migration) for naming
consistency with the other UPSC Mains optional paper, `upsc_law_optional` — both now spell
"optional" out fully rather than one abbreviating to "opt". `scripts/init_db.py` updated to
match, so a fresh clone seeds the correct id.
**Original open question (S3):** PLAN.md Phase 0's registry list named `upsc_eco_opt` under
"exams that already exist elsewhere" AND separately listed `upsc_eco_optional` under the
ASSUME-01 placeholder group — plausibly the same exam. Seeded only one rather than risk a
duplicate registry row; flagged rather than guessed.

### DECIDE-17 — `exam_id` is ingestion-run-scoped, not Haiku-classified per chunk {#decide-17}
**Date:** 2026-09-06 | **Session:** S4

**Decision:** `sections.exam_id` is `NOT NULL` and gets written at Stage-1 chunking time —
before the Haiku enrichment call that classifies `content_type`/`topic_id` runs. Rather than
require exam detection before enrichment exists, `exam_id` is a parameter supplied by the
ingestion caller (the folder being ingested IS the exam scope — matches CLAUDE.md's "a new
exam is a row... drop PDFs in a folder + run ingest" model), never something an LLM infers
per chunk. Only `topic_id`/`content_type` on `sections` are nullable and get backfilled
after the first chunk in that section is classified.
**Rationale:** Checked the ancestor pattern this generalizes from — Devthorium's
`ingest_pyq.py:classify_batch()` classifies `subject_id`/`topic_id`/`subtopic_id` within one
already-known exam; it never classifies which exam a document belongs to. Devthorium never
needed to, being single-exam. Nyaya Core is multi-exam, but the exam is still known ambient
context (which folder you pointed the ingester at), not a property of chunk content that
needs inference — a UPSC Prelims GS passage and a RBI Grade B passage can look identical in
isolation.
**Rejected:** Having Haiku classify `exam_id` per chunk too — rejected because exam scope is
already known before ingestion starts (nobody drops mixed-exam PDFs in one folder), so
inferring it from content would add cost and a failure mode (misclassification) for a value
that's never actually ambiguous at ingest time.

### DECIDE-18 — Seed `topics` from Devthorium's real syllabus.json, not Haiku-invented strings {#decide-18}
**Date:** 2026-09-06 | **Session:** S4

**Decision:** Phase 0 left the `topics` table empty. Rather than let the Haiku enrichment
call invent topic_id strings per chunk (Devthorium's `ingest_pyq.py` ancestor pattern does
exactly this for topic_id/subtopic_id, only subject_id is a closed set), `scripts/
seed_topics.py` imports Devthorium's existing `data/syllabus.json` (subject > topic >
subtopic, 3 levels via `parent_topic_id`) into `topics` for `upsc_prelims_gs` — 271 rows.
The enrichment prompt is given this closed candidate list and told to pick from it or
return null, never invent a new id.
**Rationale:** DECIDE-04 already established `topic_id` as a registry FK, not free text —
letting an LLM freely generate it per chunk would reintroduce exactly the inconsistent-
naming problem DECIDE-04 exists to prevent (e.g. "fundamental_rights" vs "fundamental_right"
as two different topic_ids across chunks), silently breaking the "one topic query pulls both
grounding chunks and PYQs" guarantee. The 4th level in syllabus.json (`dimension`) is
PYQ-weighting granularity from Devthorium's own `priority_scorer.py` — a different concern
from retrieval topic granularity — so it's not imported as a `topics` row.
**Open:** only `upsc_prelims_gs` has a real taxonomy source right now. The other 7 seeded
exams (`upsc_mains_gs`, `essay`, `ethics`, `ies`, `rbi_grade_b`, `upsc_eco_optional`,
`upsc_law_optional`) have zero topics — `load_topics()` in `src/ingestion/enrich.py` raises
`ReviewNeededError` rather than silently proceeding if asked to enrich content for an exam
with no seeded taxonomy. Per Rule 2 (verify before building), not inventing a UPSC
Ethics/Essay/IES/RBI taxonomy from training knowledge — needs a real source (Rahul, or a
fetched official syllabus) before those exams' content can be ingested. **Superseded in
part by DECIDE-19** — IES and RBI Grade B turn out to already have real, usable taxonomies
sitting in Descriptive-exams' own databases (`ies.db`/`rbi.db`), not something to generate;
see DECIDE-19.

### DECIDE-19 — `topics` made exam-agnostic; `exam_topics` junction table added (resolves DECIDE-32) {#decide-19}
**Date:** 2026-09-06 | **Session:** S4

**Decision:** Rahul raised, independently, the exact cross-exam topic-sharing question that
had sat pending since 2026-06 as Descriptive-exams' `AUDIT-008` `DECIDE-32` — "should
'Monetary Policy' in IES/RBI point to one canonical entity in `nyaya.db master_topics`?"
`topics.exam_id NOT NULL` (as originally built in Phase 0) had silently answered "no"
without that ever being an explicit decision. Fixed: `topics` (`topic_id`, `name`,
`parent_topic_id`) is now exam-agnostic — one canonical entity per real-world concept. A new
`exam_topics` junction table (`exam_id`, `topic_id`, `weight`, `is_core`) says which exams a
topic is relevant to and how much. `chunks.topic_id`/`pyq_bank.topic_id` are unaffected —
still a single FK into `topics`, DECIDE-04 untouched. `src/ingestion/enrich.py`'s
`load_topics()` now joins through `exam_topics`; `scripts/seed_topics.py` inserts into both
tables, additionally capturing each subject's real `avg_questions_per_year` (from
Devthorium's syllabus.json) as `exam_topics.weight` — previously dropped entirely.
**Rationale (researched, not asserted):** real precedent for "one canonical entity, reused
across multiple classification systems via a mapping/crosswalk table" — O*NET's
occupation↔ESCO crosswalks, general relational-DB many-to-many practice (junction table
carrying the relationship's own attributes, never entity duplication), and 2026 RAG
knowledge-base practice (controlled taxonomy + relationship layer, not per-source
duplication) all converge on this shape. Migrated with zero data loss (271 existing rows,
`scripts/migrate_002_topics_exam_agnostic.py`) since zero chunks/PYQs existed yet to
reference the old shape — the cheapest point this could ever be fixed.
**Payoff:** an RBI monetary-policy chunk ingested once becomes retrievable for IES prep too,
the moment IES's real taxonomy (already sitting in `ies.db`, not yet imported) also links to
that same `topic_id` — zero re-ingestion, zero duplicate Haiku enrichment cost.
**Rejected:** a full concept graph/ontology — real-world precedent (RAG knowledge-base
practice) explicitly favors a controlled taxonomy + junction/crosswalk layer over full graph
modeling at this scale; graph traversal complexity buys nothing a single-user, ~9-exam
system needs today.

### DECIDE-20 — 4 State PCS exams registered; `seed_topics.py` extended for reuse-plus-new-branch {#decide-20}
**Date:** 2026-09-06 | **Session:** S4

**Decision:** Rahul is targeting 8 State PCS exams; real eligibility research (RESEARCH-08)
found 4 immediately feasible (UP, Himachal, Uttarakhand, MP — open to non-domicile
candidates, no disqualifying language requirement), 1 blocked by his own stated condition
(Gujarat — Gujarati is a compulsory qualifying Mains paper), 1 needing more verification
before ruling in/out (Maharashtra — sources disagree on whether Marathi-at-10th-standard is
a hard eligibility bar), 1 structurally uncertain (Haryana — sources disagree on whether
Mains still has an optional subject), and 1 not-yet-applicable (Rajasthan RAS — the live
2026 cycle's application window already passed; this would target a future cycle). Only the
4 confirmed-feasible exams were registered and seeded this session, per Rahul's explicit
"go for feasible ones for now."

Registered `uppcs`, `hpas`, `ukpsc`, `mppsc` in `exams` (scripts/init_db.py). Each state's
real research showed the same pattern: Prelims/Mains GS content overlaps `upsc_prelims_gs`'s
existing taxonomy heavily (history, geography, polity, economy, environment, science,
current affairs, CSAT), plus one genuinely state-specific branch (state history/dynasties/
movements/geography/culture) with no existing canonical topic. This is exactly DECIDE-19's
payoff — extended `scripts/seed_topics.py` to accept a `reused_topics` list (link-only,
creates zero new topic rows) alongside the existing `subjects` shape (creates new topic
rows) in one file. Verified: "polity" is now one canonical row linked to 5 exams via
`exam_topics`, not duplicated 5 times — `topics` grew by only the genuinely new
state-specific rows (85 new), not 4× the shared content.

New state-specific taxonomy content (`data/syllabi/{uppcs,hpas,ukpsc,mppsc}.json`) was
hand-curated from real per-state syllabus research (coaching-site aggregation of official
syllabi — Drishti IAS, PW, StudyIQ, etc. — not the primary official PDF text itself,
disclosed in each file's `_source_note`). Granularity varies honestly by how much real
detail existed in the sources found — Uttarakhand's is richest (named dynasties, named
popular movements; UKPSC's own materials state ≥1/3 of Prelims questions reference the
state directly, the heaviest state-weighting found among the 4), Himachal's is thinnest.
**Open:** Haryana/Maharashtra/Rajasthan need the specific unresolved questions answered
before any taxonomy work starts for them (see RESEARCH-08). Gujarat is out per Rahul's own
stated condition.

### DECIDE-21 — Finalized `exam_id`/`paper_id` naming convention; restructured UPSC exams into papers {#decide-21}
**Date:** 2026-09-06 | **Session:** S4

**Decision:** Rahul flagged a real inconsistency with concrete examples: `upsc_eco_optional`
doesn't say which UPSC exam (CSE vs EPFO vs IES vs CAPF), and a hypothetical `rbi_eco`
wouldn't say whether it means RBI Grade B's general economics section or RBI DEPR's. Asked
for 3-4 researched naming options before finalizing. Presented 4 (flat-but-explicit,
two-level using the schema as designed, explicit-level-segment, and enterprise registry
codes), grounded in real precedent — Common Core's fixed-hierarchy dot notation, ISCED's
hierarchical education codes, and standard DB practice that a child entity's key shouldn't
repeat its parent's identity. Rahul chose the two-level option.

**Root cause found while presenting options:** the ambiguity wasn't really a string-format
problem — `essay`, `ethics`, `upsc_mains_gs`, `upsc_eco_optional`, and `upsc_law_optional`
had all been modeled as separate top-level EXAMS in Phase 0, when they're really PAPERS of
one exam (UPSC's Civil Services Examination). The `papers` table existed for exactly this
and had zero rows. Confirmed with Rahul before touching it (bigger change than a rename) —
approved.

**What changed** (`scripts/migrate_003_exam_paper_restructure.py`, already run against the
live `data/core.db`, zero data loss — only `upsc_prelims_gs` had real dependent data, 271
`exam_topics` rows):
- `exam_id` = `{institution}_{exam}` — the actual exam a candidate applies to, never a paper
  within it. Renamed `ies` → `upsc_ies`, `rbi_grade_b` → `rbi_gradeb`. Added `rbi_depr`
  (placeholder — Rahul referenced it as a real, distinct RBI exam).
- Merged `upsc_prelims_gs`/`upsc_mains_gs`/`essay`/`ethics`/`upsc_eco_optional`/
  `upsc_law_optional` into one `upsc_cse` exam with 8 `papers` rows (`prelims_gs`,
  `mains_gs1`-`mains_gs4`, `essay`, `eco_optional`, `law_optional`) — `mains_gs` was split
  into the 4 real, materially-different GS papers rather than kept as one blob, since
  nothing depended on the old undifferentiated shape (zero data loss to lose).
- `papers`' PK became the **pair** `(exam_id, paper_id)`, not `paper_id` alone — `paper_id`
  never needs to repeat its exam's identity (`essay`, not `upsc_cse_essay`), same reasoning
  DECIDE-19 already established for `topic_id` not repeating its exam's identity.
- `exam_topics` gained a `paper_id` column (default `'_all'` sentinel — a real string, not
  NULL, since SQLite treats every NULL as distinct for uniqueness and would silently break
  idempotent re-seeding). Necessary the moment papers share an exam_id: without it, a
  document from `upsc_cse`'s Essay paper would see Prelims-only topics (`modern_history`,
  `polity`) as valid classification candidates just because they share an `exam_id`. State
  PCS exams and `rbi_gradeb`/`upsc_ies`'s non-GE content stay at `'_all'` — accurate, not
  wrong, since no paper-level content exists for them yet.
- `pyq_bank`'s FK became composite `(exam_id, paper_id) REFERENCES papers(exam_id, paper_id)`.
- `src/ingestion/enrich.py::load_topics()` gained an optional `paper_id` param;
  `build_chunk_metadata`/`build_pyq`/`enrich_chunk` now populate `ChunkMetadata.paper_id`/
  `PYQBase.paper_id` (previously always `None`, a real gap this closed as a side effect).
  `scripts/ingest.py` gained `--paper-id`; `scripts/seed_topics.py` gained `--paper-id`
  (default `'_all'`).
- Added `topics.notes` (nullable free-text) — needed once RBI's real curator notes (e.g.
  "Mundell-Fleming appeared TWICE in 2024") needed a home; deliberately NOT `chunk_tags`
  (keyed by real chunk_id, a different entity than a topic).

**Then imported IES + RBI Grade B's real taxonomies** (`scripts/import_ies_rbi_taxonomy.py`,
no new research needed — RESEARCH-07 already found these sitting unused in
Descriptive-exams' `ies.db`/`rbi.db`): 156 IES topics across real `ge_01`-`ge_04` papers,
29 RBI topics + 9 subject-groupings. Checked for `topic_id` collisions against the existing
316 topics before importing — zero found, imported as-is.
**Rejected:** Option 1 (rename in place, keep separate exams) — would have left the deeper
exam/paper conflation unfixed. Option 3 (explicit level segment, `upsc_cse_mains_essay`) —
redundant once `papers` properly scopes by `exam_id`; the level info lives in the paper's
own `name` field, not its id. Option 4 (registry codes) — not human-readable, wrong fit for
a system Rahul is meant to eyeball and debug himself.

### DECIDE-22 — Added `institutions` table (real join target, not just an id prefix) {#decide-22}
**Date:** 2026-09-06 | **Session:** S4

**Decision:** Rahul asked whether the naming rules themselves are tracked anywhere usable
for real SQL querying/joining, not just documentation a person reads. Answer, made explicit
in `docs/DATA_DICTIONARY.md`'s new "Rules vs. data" section: the *grammar* for constructing
an id (DECIDE-21) is documentation — nothing ever runs a query to fetch a naming rule, a
person applies it when adding a row. But "institution" itself was a real, missing
*dimension* — only present as an unqueryable string prefix inside `exam_id`. Added
`institutions` (`institution_id` PK, `name`) and `exams.institution_id` (FK). "Every exam
UPSC conducts" is now `JOIN institutions`, not `exam_id LIKE 'upsc_%'`. Seeded for all 8
exams — `upsc`/`rbi` conduct 2 each; each State PCS exam's own commission (`uppsc`, `hppsc`,
`ukpsc`, `mppsc`) is its own institution (UP/HP have a distinct commission-vs-exam acronym;
UK/MP's commission acronym doubles as the exam reference too — a real asymmetry in common
usage, not modeled inconsistently).
**Rejected:** Storing the naming rule text itself in a database table — a rule isn't data
anything queries at runtime; it's exactly the kind of institutional knowledge
`docs/decisions.md`/`MASTER_INDEX.md` already exist to track, and a second copy would just
be something to keep in sync for no benefit.

### DECIDE-23 — `pyq_explanations` schema, designed against Recall's real failure (BUG-04) {#decide-23}
**Date:** 2026-09-06 | **Session:** S4

**Decision:** Rahul described a future MCQ practice feature (timed/untimed, topic+exam+year
filtered, cross-exam mixing, per-question explanations that go deeper on a wrong attempt).
Before designing it, investigated Recall's existing equivalent feature (fork research) —
found it 100% broken (BUG-04) in a way that directly shapes this design, not just "make the
prompt better."

**What was built** (`src/schema/models.py`, `scripts/init_db.py` — schema only; the actual
batch-generation script is a separate, later, on-demand piece of work per Rahul's explicit
choice, not built this session):
- `MCQQuestion.statements: Optional[list[str]]` — populated at PYQ-extraction time
  (`enrich.py`/`prompts/enrich_chunk_system.txt`, both updated) when a question is
  statement-based ("how many of the following statements are correct"), the dominant real
  UPSC Prelims format. `None` for standalone-option MCQs. Live-tested against a real
  3-statement UPSC-style question via the actual Haiku API — correctly detected and
  extracted all 3 statements, correctly classified topic_id `parliament` (Rahul's own
  example topic), not just validated against hand-written fake data.
- `pyq_bank.statements` column (JSON, nullable) mirrors this in SQLite.
- New models: `OptionRationale`/`StatementRationale` (leaf-level rationale), a discriminated
  `ExplanationDetail` union (`StandaloneExplanation` | `StatementBasedExplanation`) so a
  statement-based question gets per-statement evaluation + a combination-rationale instead
  of four fake independent option notes — this exact mismatch is what left 100% of Recall's
  904 rows silently empty. `PYQExplanation` (top-level, matches new `pyq_explanations`
  table): `concept_summary` (brief, always shown — Rahul's "briefly" case),
  `detail` (the discriminated union, detailed — shown only on a wrong attempt, matching
  "in detail for wrong attempts"), `elimination_strategy` (real exam-technique reasoning —
  never attempted anywhere in this system before, confirmed by fork research), 
  `grounding_chunk_ids` (citations — BUG-04's zero-grounding problem), `verified_by`/
  `reviewed_at` (same provenance pattern as everything else in this schema).
- `pyq_explanations` table (SQLite): 1:1 with `pyq_bank` via `question_id`.
- Verified the discriminated union actually rejects a malformed shape (missing
  `combination_rationale` on a statement-based explanation, missing `rationale` on a
  standalone option) — same standard Phase 0 held `MCQQuestion`/`DescriptiveQuestion` to,
  not just that valid input passes.

**Explicitly deferred, confirmed with Rahul:** the batch-generation script itself (the thing
that actually calls an LLM to produce a `PYQExplanation`) is a separate, later, deliberately
on-demand job — not automatic at ingestion time, for cost control. When built, it must:
validate the response against `PYQExplanation` before writing (a partial response is
`ReviewNeededError`, never a silent partial write — BUG-04's second root cause), and ground
the explanation in real retrieved chunks rather than pure model recall (BUG-04's third).

**Cross-project follow-up, same session:** logged BUG-04 findings into Devthorium's own
`ISSUES.md` (new ISSUE-029, plus a follow-up note on ISSUE-013 clarifying its fix never
covered this third surface), and the general process lesson into
`~/.claude/GLOBAL_LEARNINGS.md` (GL-06 — a "Resolved" issue only covers the surface actually
checked, not the whole bug class) plus Devthorium's own close-task checklist, so a
similar-looking defect in a sibling feature doesn't go unnoticed again.

### DECIDE-24 — Registered `upsc_epfo_apfc_eo_ao`; real per-subject weights from RESEARCH-10, not guessed {#decide-24}
**Date:** 2026-09-09 | **Session:** S5

**Decision:** Registered UPSC's EPFO recruitment test as one exam,
`upsc_epfo_apfc_eo_ao` (`exams`, institution `upsc`), not two. Rahul asked for
`upsc_epfo_apfc/eo/ao`; slashes aren't usable in an `exam_id` (it's a SQLite PK, a
`data/syllabi/{exam_id}.json` filename, and a FastAPI query-string value in Phase 2) so this
substitutes underscores while keeping the same intent — every post APFC/EO/AO named
together, reflecting RESEARCH-09/RESEARCH-10's finding that they've been one combined paper
since 2025. No `papers` row — single paper, same pattern as `rbi_gradeb` and the State PCS
exams (`paper_id = '_all'` in `exam_topics`).

**Topic seeding — reuse-first, same DECIDE-19 payoff as State PCS:** 7 links to existing
canonical topics with *real* weights instead of the reuse path's previous flat `1.0`
(`current_affairs` 10, `economy` 9, `polity` 12, `history_amac` 5, `modern_history` 4, `csat`
15 — reused for the Elementary Maths/Stats/GMA syllabus head, `reading_comprehension` 5).
4 genuinely new subjects seeded (20 new topic rows): `general_english` (non-RC portion),
`general_science_computer`, `labour_codes_social_security` (9 real Act-level topics —
EPF Act 1952, ESI Act 1948, Payment of Wages Act 1936, Employees' Compensation Act 1923,
Industrial Disputes Act 1947, Trade Unions Act 1926, Maternity Benefit Act 1961, Payment of
Gratuity Act 1972, the 4 new Labour Codes), `accountancy_auditing_insurance`. All weights
sum to exactly 120 — the real question count from RESEARCH-10's paper, not a coincidence,
a deliberate check that the seeding matched the source.

**`seed_topics.py` extended (backward compatible):** `reused_topics` entries can now be
either a bare topic_id string (unchanged behavior, weight defaults to `1.0`) or
`{"id": ..., "weight": ...}` when a real per-topic count exists — needed because RESEARCH-10
gave real weights for reused topics too (e.g. `polity` genuinely gets 12 questions in this
exam, not the placeholder 1), and flattening that to 1.0 would have thrown away the exact
signal `exam_topics.weight` exists to carry. Verified against the existing plain-string
`uppcs.json` re-run (idempotent, identical counts) before treating it as safe.

**Weight-modeling caveat, explicitly not resolved by this decision:** these are real
numbers from ONE verified year (2025), not a multi-year average — RESEARCH-09 found genuine
year-to-year volatility in this exam's subject weightage. Documented as a caveat in
`data/syllabi/upsc_epfo_apfc_eo_ao.json`'s `_source_note` rather than invented a
confidence/provenance column — same "grammar/caveat stays documentation, not a queried
field" reasoning as DECIDE-22, since nothing runs a query asking "how many years is this
weight based on." The real fix, per the architecture discussion, is to recompute weight
from actual ingested `pyq_bank` topic-tag frequency once more real years of content exist —
not to model uncertainty explicitly now.

**Rejected:** two separate `exam_id`s (`upsc_apfc`/`upsc_eo_ao`) — would duplicate every
topic weight twice for content that is, per RESEARCH-10, literally one paper.

### DECIDE-26 — No-skip ingestion: flag-and-halt, not flag-and-continue, for scarce exams {#decide-26}
**Date:** 2026-09-10 | **Session:** S7

**Decision:** For exams where real source material is scarce (EPFO-family: only 6-7 past
papers exist in total), a chunk/question that can't be fully resolved during ingestion must
be treated as a blocking problem to solve, not a row to drop and move past. Concretely:
when Rahul sources a real answer key for a paper, re-ingestion must (a) actually reprocess
that file (`ingestion_log.json`'s hash-skip currently prevents this — needs a `--force`
path added to `scripts/ingest.py` before the next real run) and (b) resolve
`correct_option` from the real key by question number, not from a Haiku guess — the
previous run's ~84/120 unresolved questions were overwhelmingly "no correct_option" flags
caused by Haiku lacking a key, not bad extractions. Any chunk that still can't be resolved
after that (e.g. the 11 chunks flagged "no registered topic matched" — cause not yet
diagnosed, OCR text for those pages wasn't retained) must stop the run and surface the
specific unresolved item for Rahul to fix at the root (e.g. add a missing topic), rather
than silently logging it to `flagged_chunks.jsonl` and reporting a lower final yield as
success.

**Rationale:** DECIDE-15's "sampled/high-stakes-only" verification policy assumed
verification gaps are a long tail against abundant content. That assumption doesn't hold
for an exam with only 6-7 real papers ever published — every unresolved question is a
material fraction of all content that will ever exist for this exam, so completeness bar is
higher here than the general policy. Rahul: "we can always find a solution to any kind of
problem if that problem is flagged and not skipped or worked around."
**Rejected:** keep flag-and-continue as-is and just accept the ~30% loss rate — rejected
because it directly hurts usability of the practice-question feature on already-scarce
content, per Rahul's explicit reasoning.
**Not yet designed:** the actual answer-key-ingestion mechanism (how a sourced key — likely
an image/PDF/coaching-site page — gets matched to question numbers and merged in before or
during enrichment). Design this once Rahul has the real key in hand and its format is
known, not speculatively now.

### DECIDE-25 — Split `eco_optional`/`law_optional` into Paper I/II {#decide-25}
**Date:** 2026-09-09 | **Session:** S6

**Decision:** Rahul flagged that every UPSC Optional subject is 2 compulsory papers/year
with disjoint syllabi (Economics Paper I = theory — micro/macro, growth, international
econ, money-banking; Paper II = the Indian economy — planning, agriculture, industry,
poverty). DECIDE-21's restructuring correctly split `mains_gs` into `mains_gs1`-`mains_gs4`
for the same reason but left both Optionals as one paper row each — a real gap, not a style
choice, since Paper I and Paper II content/topics genuinely don't overlap.

**What changed** (`scripts/migrate_004_split_optional_papers.py`, run against the live
`data/core.db`; `scripts/init_db.py`'s `PAPERS` updated for fresh clones): `eco_optional` →
`eco_optional_1`/`eco_optional_2`; `law_optional` → `law_optional_1`/`law_optional_2`.
Naming matches the `_1`/`_2` convention Rahul chose over the existing no-separator
`mains_gs1..gs4` precedent, for readability. Zero dependent rows existed in
`exam_topics`/`pyq_bank`/`sections` for either old paper_id (no Optional topics seeded, no
Optional content ingested yet) — clean split, not a data migration; the script hard-aborts
if it ever finds dependent rows instead of silently assuming zero, since that assumption is
only true today.

**Doc-hygiene fallout also fixed this session:** `PLAN.md`'s Phase 0 checklist still carried
a stale "DECIDE-16 needs Rahul's confirmation" note from S3, never updated after DECIDE-16
resolved in S4 — corrected to point at the actual outcome (DECIDE-16 → DECIDE-21 → this).

### DECIDE-27 — correct_option is NEVER Haiku-determined, only merged from a real key {#decide-27}
**Date:** 2026-09-12 | **Session:** S8

**Decision:** Extends DECIDE-26 into a permanent structural rule, not just a per-run policy.
`MCQQuestion.correct_option` is `Optional[str]`, defaults to `None`, and is set by exactly
one path: `scripts/merge_answer_key.py` writing a letter it read from a real, human-sourced
answer key — never by `enrich_chunk`'s Haiku call, even when Haiku is confident. Added
`MCQQuestion.status` (`unverified`/`verified`/`void`) so "we don't know yet" and "UPSC itself
dropped this item" are distinct, queryable states, not both collapsed into a null. Added
`PYQBase.question_number` (the literal number printed on the question) since it's the only
key a real answer key can be matched against — `question_id` is an internal chunk-derived
string, never the exam's own numbering.

**Why now:** Two real findings triggered this. (1) The 36 rows already in `pyq_bank` from
the 2025 paper turned out to have `correct_option` filled by Haiku's own guess — the
original `enrich_chunk_system.txt` literally asked for "text of the correct option, or null
if not determinable" (see BUG-12). (2) Rahul separately flagged that a NotebookLM-generated
"solved answer key" for the 2025 paper is not trustworthy either — he needs to verify
answers himself. Both are the same root problem (an LLM's own belief about a right answer,
presented as data) — DECIDE-26 already banned this for *dropped* questions; this makes it a
structural guarantee for *all* questions, not a per-session judgment call.

**Real official answer keys exist for 5 EPFO years already on disk** (2012/2016/2017/
2021/2023, `~/Desktop/UPSC/epfo_apfc_eo_ao/*Answer-Key*.pdf`) — visually confirmed genuine
UPSC-format scanned sheets (exam code, Series letter, dropped-item count), not LLM output.
Each covers 4 series (A/B/C/D, different question order per series) on separate pages —
`scripts/extract_answer_key.py` transcribes all 4 per PDF; the caller must pick the series
matching the actual question-paper PDF's own printed series (never assume A).

**Proof of concept, same session:** ingested the 2023 EO/AO GAT paper (using the clean
NotebookLM-retyped digital PDF in `pyqs_formatted(notebooklm)/`, not the scanned original —
avoids OCR errors and the bilingual Hindi/English page-pair duplication the scanned version
has) and merged the real Series A key: **114/120 questions verified against a real official
key, 0 guessed.** 6 questions (115-120, quantitative aptitude) didn't extract at all — no
registered topic for that subject yet (see RISK-05) — a real, understood, non-silent gap,
not a re-run of DECIDE-26's original 70%-loss problem.

### DECIDE-28 — every pyq_bank row carries its exact source file(s) {#decide-28}
**Date:** 2026-09-12 | **Session:** S8

**Decision:** Rahul's explicit ask: be able to trace any question, and any verified answer,
back to the literal file it came from, so a source later found to be wrong can be found and
re-checked rather than guessed at. Added `pyq_bank.source_file` (the question-paper file the
row was extracted from, threaded through `enrich_chunk`/`build_pyqs`/`persist_pyq` from
`ingest.py`'s own file path — not inferred) and `pyq_bank.answer_key_file` (the exact
answer-key PDF + series that set `correct_option`, e.g.
`".../UPSC-EPFO-EO-AO-Answer-Key-2023.pdf#series=A"`, set only by
`scripts/merge_answer_key.py`). Both are plain columns, not a separate source-registry table
— a row already has everything needed to answer "where did this come from," no join needed.
`scripts/migrate_006_source_provenance.py` backfilled both for the two documents ingested
before this column existed (2025's paper, 2023's `notebooklm` PDF + its verified key).

### DECIDE-29 — fresh, EPFO-specific topic taxonomy replacing 6 reused UPSC-Prelims topics {#decide-29}
**Date:** 2026-09-12 | **Session:** S8

**Decision:** Rahul, reviewing the taxonomy before letting the 2023 APFC General Studies
paper ingest: "curate fresh taxonomy for epfo_apfc_eo_ao exams, topics are not exactly
similar to upsc_prelims syllabus." Investigation found 6 of the exam's 25 seeded topics
(`polity`, `economy`, `current_affairs`, `history_amac`, `modern_history`,
`reading_comprehension`) were literally the same shared canonical rows DECIDE-19's
exam-agnostic model lets `upsc_cse`/State PCS reuse — appropriate when depth/scope
genuinely match (IES/RBI), wrong here since EPFO's coverage of these subjects is real but
shallower/differently-scoped than UPSC Prelims'. `reading_comprehension` was even parented
under `comprehension` -> `csat`, a UPSC-CSE-Paper-2-only concept EPFO doesn't have. `csat`
itself was linked to this exam with zero actual usage — a stray import, unlinked outright.

Sourced the real replacement from the actual UPSC EPFO 2026 notification's Appendix-I
("Scheme, Syllabus, Weightage") — `~/Desktop/opportunities/govt notifications/epfo 2026
notification.pdf`, page 22 — the 9 real syllabus subjects, not invented. Created 8 new
EPFO-scoped topics (`epfo_governance_constitution`, `epfo_economy_dev_issues`,
`epfo_current_events`, `epfo_culture_heritage_freedom` with two children
`epfo_ancient_medieval_culture`/`epfo_modern_freedom_struggle`, `epfo_reading_comprehension`
re-parented under this exam's own `general_english`, and
`epfo_quant_stats_mental_ability` — syllabus subject vi, entirely missing before this,
resolving RISK-05). `scripts/migrate_007_epfo_fresh_taxonomy.py` retagged all 228 affected
`pyq_bank` rows and 53 LanceDB chunk rows from the old shared topic_ids to the new ones,
unlinked the 7 old `exam_topics` rows for this exam (canonical rows untouched for their real
owners), and recomputed every `exam_topics.weight` for this exam from real observed
frequency across all 546 then-ingested questions (RISK-04's payoff, no longer
single-year-seeded).

**Immediate real payoff:** the 2023 APFC General Studies paper, ingested right after this
fix, got 114/120 questions cleanly tagged (only 3 chunks flagged) — a sharp improvement over
the old taxonomy's flagging rate on comparable content. 608 total verified questions across
6 real paper-instances (5 GAT years + this GS year) as of this session.

### DECIDE-30 — Register PFRDA Officer Grade 'A' as a new exam, fresh taxonomy {#decide-30}
**Date:** 2026-09-15/16 | **Session:** external (Mission 2027 strategy session) | **Status:** Active

**Decision:** Registered `pfrda_gradea` (10th exam) under a new `pfrda` institution — Rahul
is applying to both General and Research streams, real notification found (Advt. 03/2026,
applications close 24 Sep 2026, Phase-I 15 Oct, Phase-II 20 Nov). Modeled as one exam with
6 papers (`phase1_p1`/`phase2_p1` common to all streams; `phase1_p2_general`/
`phase2_p2_general` and `phase1_p2_research`/`phase2_p2_research` fully disjoint syllabi),
matching DECIDE-21/25's "streams are papers, not separate exams" precedent.
**Rationale:** Per DECIDE-29's precedent, curated a fresh 28-topic taxonomy rather than
reusing canonical UPSC/RBI/IES topics — real PYQ sampling (2025 PFRDA paper-book) confirmed
PFRDA General's Economics section is genuinely UG-101 level, well below the postgrad depth
CSE/RBI/IES's canonical Macro Theory topics assume; forcing a link would misrepresent depth.
Phase-I Paper 1's 4-section weight (English/Quant/Reasoning/GA, 22.22/22.22/33.33/22.22) is
real, from the notification's stated 20/20/30/20-of-90 question split. **General/Research
Paper-2 topics all carry a flat placeholder weight of 1.0** — no real per-subject frequency
exists yet (the 3 real PFRDA paper-books on disk haven't been ingested), same honest-
placeholder pattern already used for State PCS (RISK-04's original problem) — do not treat
as real weights.
**Rejected:** Cross-linking PFRDA's "Union Budget & Economic Survey" line to the canonical
Indian-Economy/current-affairs topic — plausible real match, but deliberately deferred
rather than decided in a rushed pass; flagged as RISK-07 below.
**Assumptions baked in:** none — every topic/paper/weight traces to the real notification,
read via vision this session (`scripts/migrate_008_register_pfrda.py`'s docstring has full
citation). Actual PDF ingestion of the 3 real PFRDA paper-books is NOT done — schema/taxonomy
only. 41/41 tests still passing post-migration.

### DECIDE-31 — Ingest the 3 real PFRDA paper-books as coverage intelligence, not a scored quiz bank {#decide-31}
**Date:** 2026-09-16 | **Session:** external | **Status:** Active

**Decision:** Ingested all 3 real PFRDA Grade A "recollected question" paper-books
(`~/Desktop/PFRDA/*.pdf`, 2021/2022/2025 — coaching-site compilations of candidate memory,
carrying the source's own disclaimer about recall inaccuracy, NOT official PFRDA-released
papers) — 454 real MCQs + 16 descriptive-English prompts, `source_type = 'coaching_derived'`
(never `official_pyq`). Resolves RISK-07: `exam_topics.weight` for every topic/subtopic that
received real data is now a recency-decayed real frequency count
(`weight = Σ 0.9^(2026 - year)` per real observed occurrence, rolled up from subtopic to
parent subject), not the DECIDE-30 flat 1.0 placeholder.

**Rationale — goal reframe (Rahul, this session):** the point of this ingestion isn't a
flawless practice-quiz answer key — recollected questions inherently carry errors — it's
coverage intelligence: which subjects/topics/subtopics PFRDA Grade A actually tests, at what
depth, in what style. This changed two things from the EPFO precedent (DECIDE-26/27):
1. A prior research pass (3 parallel fable-model agents, one per year) cross-verified every
   MCQ against independent recollection sources (ixamBee etc.) and, where none existed,
   independent fact-checking (redoing the math, checking real statutes/regulations) —
   `data/raw_ingest_staging/pfrda/{2021,2022,2025}_verified_questions.md`. 11 items came back
   genuinely `CONFLICTING` (book's answer disputed by independent verification). Rahul's
   resolution policy for these, applied case-by-case not by blanket rule: where the
   independently-verified correct answer is confidently grounded in a real, checkable source
   (a bare-act section, an official FAQ, or a passage directly contradicting the book) →
   corrected `correct_option`, `status='verified'` (4 items: 2021 Costing Q5, 2025 RC Q4,
   2025 NPS Vatsalya Q14, 2025 Companies Act Q3). Where the recollection's own options don't
   contain any valid real answer (the true fact isn't among the 5 choices — a corrupted
   recollection, not just an uncertain one) → `correct_option=NULL`, `status='void'` (2
   items: 2022 GA cricket-award Q, 2025 UN-CEBD year Q). Where genuinely unresolvable either
   way (ambiguous stem, or a real methodological/convention dispute like syllogism
   possibility-conclusions) → `correct_option=NULL`, `status='unverified'` (5 items).
2. Rather than dropping ambiguous items or authoring replacement questions (the initial
   plan), everything gets ingested — even a `void`/`unverified` question still carries real
   topic/subtopic signal about what's tested, which is the actual goal now.

**New subtopic layer built the same session** (DECIDE-30 had only 28 flat top-level topics,
no depth below subject level): 50 subtopics for the 7 General-stream Paper-2 subjects that
actually appear in real PYQs (Commerce & Accountancy, Management, Finance, Costing,
Companies Act, Economics, Pension Sector), transcribed directly from the real notification's
own lettered/numbered sub-items (`data/syllabi/pfrda_gradea_general_p2_subtopics.json`) —
Companies Act's 7 subtopics are the Act's own real chapter titles (III/IV/VIII/X/XI/XII/
XXVII), not invented. Plus 42 bottom-up subtopics for Phase-1-Paper-1's aptitude sections
(Quant/Reasoning/English/GA), which have no official sub-breakdown in the notification —
consolidated from real per-question labels two independent structuring passes proposed over
the 2022/2025 papers (`data/syllabi/pfrda_gradea_phase1p1_subtopics.json`).

**Real finding, not previously known:** only 7 of the 12 General-stream syllabus subjects
ever appear across all 3 real papers (Commerce & Accounts, Management, Finance, Economics,
Costing, Companies Act, Pension Sector) — PFRDA Act 2013, Union Budget & Economic Survey,
AI/ML, Media, and Marketing & Communication never show up in any of the 2021/2022/2025
recollections. Either genuinely new for the 2026 notification or just unsampled — worth
watching once a 2026 paper (real or recollected) exists to check against.

**Mechanical pipeline, zero LLM in the answer path:** `scripts/ingest_pfrda_structured.py` —
loads the 3 already-resolved `*_structured.json` files (built by 3 parallel structuring
agents against Rahul's exact resolution rules, self-checked against each source's own
summary counts), normalizes a paper_id naming drift (`phase1_p2`/`phase2_p2` →
`..._general`), remaps Phase-1-Paper-1 subtopic labels via keyword rules, and does a plain
`INSERT OR IGNORE` into `pyq_bank`. No Haiku call anywhere in this script — every
`correct_option` traces to the verification pass's own reasoning, never an ingest-time guess.

**Not done, real follow-up:** Research-stream Paper-2 (`phase1_p2_research`/
`phase2_p2_research`) still carries DECIDE-30's flat 1.0 placeholder weights — none of the 3
books contain Research-stream content (all 3 are General-stream), so RISK-07 is only
resolved for the General stream. RISK-08 (Budget/Economic-Survey cross-link) still open,
untouched this session.

### DECIDE-32 — Register real RBI DEPR + new RBI DSIM exam, execute RESEARCH-11's cross-exam topic-linking plan {#decide-32}
**Date:** 2026-09-16 | **Session:** external | **Status:** Active

**Decision:** RESEARCH-11 (`docs/research/RESEARCH-11-pfrda-research-stream-sync.md`) found
`rbi_depr` was only ever a placeholder (zero papers/topics) and couldn't resolve a real
disagreement between two coaching sources on DEPR's Phase II structure. Rahul supplied the
real official notification (RBISB/DA/01/2026-27, dated 29.04.2026,
`~/Desktop/opportunities/govt notifications/DEPR29042026....pdf`, read via vision this
session) — resolving the dispute definitively: **Phase II is two Descriptive Economics
papers (Micro+Macro module paper, then Quant/Econometrics+Indian-Economy-Policy module
paper), no separate Statistics paper, no English in Phase II** (English is Phase I Paper II
only). Registered `rbi_depr`'s real 4-paper structure and its real syllabus topics.

**Same notification revealed a second, closer sync partner for PFRDA Research stream that
RESEARCH-11 couldn't find** (RBI's notification page was CAPTCHA-gated for that research
pass): **RBI DSIM** (Department of Statistics and Information Management), a separate
Grade B (DR) cadre recruited in the same notification, not previously registered anywhere in
the platform. DSIM's real 9-topic syllabus (Theory of Probability/Distributions/Sampling,
Linear Models & Economic Statistics, Statistical Inference, Stochastic Processes,
Multivariate Analysis, Econometrics & Time Series, Optimization & Statistical Computing,
Data Science/AI/ML, Database Management) is a much tighter real match to PFRDA Research
stream's 11 topics than DEPR's own econometrics module — DEPR is fundamentally an economics
exam with a quant module attached, DSIM is a statistics exam, same shape as PFRDA Research.
Registered `rbi_dsim` as the platform's 11th exam (3 papers, real topics from its own
syllabus).

**Executed RESEARCH-11's proposed cross-exam topic-linking**, with one real payoff found
mid-implementation: `rbi_gradeb`'s canonical `macro`/`micro`/`indian_econ` topics already had
real children from their original seeding (`consumer_theory`, `production_theory`,
`money_banking`, `is_lm`, etc. under macro/micro; `india_macro_data`/`rbi_monetary_data`/
`schemes_indices` under `indian_econ`) — DEPR's Phase II Micro/Macro modules reuse these
directly (no duplication), and `indian_econ`'s existing children being "current developments"
flavored (not deep structural/historical) directly **confirms** RESEARCH-11's finding that a
new `indian_economy_structural` topic (linked only to `upsc_cse/eco_optional_2` +
`upsc_ies/ge_04`) was the right call, not reusing `indian_econ` — the exact DECIDE-29-shaped
depth trap, caught before it happened this time. `upsc_cse`'s Economics Optional papers
(previously zero topics) now link `macro`/`micro`/`intl_econ`/`growth`/`pub_finance`/
`env_econ`. `upsc_ies`'s `ge_01`-`ge_04` get the same canonical topics linked additively —
their own 156 real fine-grained topics are untouched, this only adds a coarser cross-exam
discovery layer alongside them.

**Deliberately NOT auto-linked: PFRDA Research stream ↔ RBI DSIM.** Despite near 1:1
syllabus-name overlap, RESEARCH-11 found zero real PYQ evidence for PFRDA Research stream —
asserting depth-equivalence to DSIM's confirmed postgrad-level content would be exactly the
unverified claim DECIDE-29 already warned against. Instead, each of PFRDA Research's 11
topics got a `notes` annotation naming its plausible DSIM correspondence (10 of 11 have one;
`pfrda_statistical_quality_control` has no clean DSIM match, likely PFRDA-specific) — for a
human to confirm once real PFRDA Research-stream content exists, not decided here.

**Mechanical migration, real weights only where the notification states them:**
`scripts/migrate_009_register_rbi_depr_dsim.py` — DEPR Phase II's Micro/Macro 0.5/0.5 and
Quant/Indian-Economy 0.5/0.5 splits are real (notification states "equal weightage"
explicitly, both places); every other weight is an honest flat 1.0 placeholder (no real
per-topic frequency exists for DEPR/DSIM/eco_optional/the new IES cross-links — same pattern
as DECIDE-30's original PFRDA placeholders). 41/41 tests still passing post-migration.

### DECIDE-33 — Resolve RISK-08: cross-link PFRDA's Budget/Economic-Survey topic to canonical `indian_econ` {#decide-33}
**Date:** 2026-09-16 | **Session:** external (Mission 2027 planning) | **Status:** Active

**Decision:** Additively cross-linked `pfrda_budget_economic_survey` (PFRDA General stream,
`phase1_p2_general` + `phase2_p2_general`) to the canonical `indian_econ` topic already
shared by RBI DEPR/DSIM, UPSC CSE Eco-Optional, and UPSC IES (DECIDE-32) —
`scripts/migrate_010_resolve_risk08_budget_ecosurvey.py`. `pfrda_budget_economic_survey`
itself is kept, not replaced (2 new `exam_topics` rows, weight 1.0, additive alongside it) —
same pattern as DECIDE-32's IES cross-links.

**Rationale (DECIDE-29's depth/scope method):** DECIDE-30 rejected a broad PFRDA-General-
Economics link to canonical Macro/Micro because PFRDA General's economics is genuinely
UG-101 level, below the postgrad depth `indian_econ`'s theory topics assume — that concern
does not transfer here. Union Budget & Economic Survey are annual primary-source government
documents, not theory of varying depth; every candidate across every exam studies the same
actual Budget/Survey each year. `indian_econ`'s existing children (`india_macro_data`:
GDP/CPI/fiscal-deficit/CAD; `schemes_indices`: PMJDY/MUDRA/PSL etc; DECIDE-32's
`fiscal_policy_india`, `sectoral_developments_india`) are exactly the content Budget/
Economic-Survey source documents report — a genuine scope match, not a forced one.

**Explicitly NOT claimed — real PFRDA frequency for this topic remains unconfirmed.**
DECIDE-31 found zero occurrences of this topic across all 3 real recalled PFRDA paper-books.
Caught before being read as confirmation: those 3 books are candidate-recall reconstructions
(not official papers), a dataset that systematically under-captures low-salience facts
(precise Budget/Survey figures forgotten more easily than a conceptual question) and small
sections, across only 3 non-exhaustive years. Zero-in-recall is weak/incomplete signal, not
proof of real-world absence — collapsing "in scope per official syllabus" and "confirmed
tested at X frequency" into one claim would be exactly the kind of unverified inference this
repo's own provenance discipline exists to prevent. `pfrda_budget_economic_survey`'s weight
stays DECIDE-30's honest flat 1.0 placeholder; the new `topics.notes` field states this
explicitly so a future reader doesn't misread the link as frequency-confirmed. See GL-07 in
`~/.claude/GLOBAL_LEARNINGS.md` for the general version of this lesson.

**Verification:** 41/41 tests still passing post-migration.

### DECIDE-34 — Real per-user coverage signal built directly on nyaya-core, not joined from Recall {#decide-34}
**Date:** 2026-09-16 | **Session:** external session, same day as DECIDE-31/32/33

**Decision:** The original plan assumed `coverage_depth` could come from joining
`exam_topics` against Recall's (Devthorium's) attempt logs. Verified against Recall's live
code/DB before building anything (Step 0, not just trusting nyaya-core's own notes, which
could have been stale): `data/upsc.db`'s `topic_weights.exam_source` only has `rbi_grade_b`
and `upsc_prelims` rows; `pyq_questions` has no exam-scoping column at all (Recall is a
single-exam app); no file under Devthorium's `backend/`/`scripts/`/`web/` references
`nyaya-core`, `core.db`, `pfrda`, or `epfo`. Nothing to join. This matches
`daily_priority.py`'s own module docstring (same session): no per-user attempt table exists
anywhere in nyaya-core.

**What was built instead:**
- `scripts/migrate_011_user_attempts_coverage.py` — adds `user_attempts` (attempt-level
  log: question_id FK to `pyq_bank`, chosen_option, correct_option, is_correct,
  attempted_at) and `topic_coverage` (computed per exam_id+topic_id: attempts_count,
  accuracy, coverage_depth, last_computed_at). An untested topic gets NO row — never a row
  of zeros — so `daily_priority.py`'s existing "no row = untested = coverage_depth 0.0"
  fallback (the layered-coverage skill's anti-false-positive rule) keeps working unchanged.
- `scripts/quiz.py` — interactive CLI quiz runner over real `pyq_bank` questions
  (`status != 'void'`, a real recorded `correct_option`, a non-null `topic_id` — the last
  two are practical necessities beyond the literal spec: an ungraded or untagged question
  can't be scored into `topic_coverage`). Reuses `daily_priority.py`'s own
  `get_scopes`/`fetch_items` ranking to order questions by real priority instead of
  reimplementing it. Grades each answer immediately, logs to `user_attempts`, then at
  session end recomputes `topic_coverage` for every topic touched from ALL historical
  attempts for that topic (not just the session's), per the layered-coverage skill's Q3
  depth rule: accuracy >= 75% -> 1.0, 45-74% -> accuracy (proportional), < 45% -> accuracy
  * 0.5 (penalised).
- `daily_priority.py`'s `fetch_coverage_depth()` now reads real `topic_coverage` rows
  (falling back to 0.0 when none exist) instead of the previous hardcoded `COVERAGE_DEPTH`
  stub; `COVERAGE_NOTE` and the uncovered/at-risk counts in both the printed and written
  report now describe the real mixed state instead of claiming zero coverage everywhere.

**Real surprise found during the demo run:** `exam_topics` (and `topics`) for `pfrda_gradea`
carry BOTH parent-level topics (e.g. `pfrda_costing`, weight 32.85, a rollup) AND their
child subtopics (e.g. `pfrda_cost_control_analysis`, weight 9.83) as independent rows —
real PYQ questions in `pyq_bank` are tagged at whichever granularity DECIDE-31's
structuring pass landed on (subtopic for most, parent for some, per HANDOFF's existing
"7 questions fell back to a parent-level topic_id" note). `quiz.py`/`topic_coverage`
correctly key off whatever `topic_id` a given question actually carries, so this works as-is
— no design change needed — but it means `daily_priority.py`'s ranked list mixes
parent-rollup rows and child rows as separate ranked items, which is pre-existing behaviour
this session did not touch.

**Verification:** 51 pre-existing tests + 19 new (4 `test_daily_priority.py`, 5
`test_migrate_011.py`, 10 `test_quiz.py`) = 70/70 passing. Demo run against 5 real PFRDA
General-stream questions (3 right / 2 wrong across `pfrda_companies_act` and
`pfrda_economics_basic`) confirmed `topic_coverage` populated correctly and
`daily_priority.py`'s ranking shifted accordingly (`pfrda_companies_act`: rank 2 -> rank 9,
priority_score 32.10 -> 10.70); demo `user_attempts`/`topic_coverage` rows deleted
immediately after, confirmed empty before finishing — never Rahul's real progress data.

### DECIDE-35 — Ingest RBI DEPR's first-ever real content (2025 Prelims Set-1), recompute `phase1_p1` weight {#decide-35}
**Date:** 2026-09-17 | **Session:** external | **Status:** Active | **Branch:** `feature/ingest-rbi-depr-2025` (not merged)

**Decision:** `rbi_depr`/`phase1_p1` ("Phase I, Paper 1 — Objective Type (Economics)",
registered DECIDE-32) had zero real questions and all-flat-1.0 placeholder weights across
its 8 topics since registration — this session gave it its first real content. Source: a
real, 14-page, 100-mark, 65-question RBI DEPR Prelims 2025 Set-1 paper plus its matching
answer key (`~/Desktop/UPSC/Mains/Other Eco Exams/RBI-DEPR (Prelims) Set-1 (2025).pdf` +
`... Anskey.pdf`) — both are Next IAS coaching-site reproductions of the real exam (digital
text, "By Vibhas Jha Sir" branding), not an RBI-official release, so `source_type =
'coaching_derived'` (same provenance category as DECIDE-31's PFRDA books), not
`official_pyq`. `Set-2`/`Set-3` question PDFs in the same folder were deliberately NOT
ingested — no matching answer key exists anywhere for either, and DECIDE-27 bans guessing
one.

**Verified before building (per Rahul's standing rule):** read both real PDFs directly.
Confirmed the paper is 65 questions (Q1-30 @ 1 mark, Q31-65 @ 2 marks = 100 marks, matching
the cover page's own stated scheme) and the key is a single flat digital-text list ("1.
(d)", "14. (c)", ... "65. (c)") — spot-checked 6 values against the source PDF by eye
before trusting the mechanical parse. Ran `get_page_text_quality()` against the question PDF
first rather than assuming: 1869 avg chars/page, correctly auto-detected as `digital_pdf`
(no OCR needed, contrary to a real possibility flagged in this session's brief).

**Pipeline — the existing generic `scripts/ingest.py` fit cleanly, no dedicated structuring
script needed** (unlike DECIDE-31's PFRDA books, which arrived pre-structured by a separate
verification pass): this is a single small already-clean digital paper, the exact same shape
as EPFO's own precedent (DECIDE-27). Copied the question PDF into
`data/raw_ingest_staging/rbi_depr/` and ran `scripts/ingest.py --exam-id rbi_depr --paper-id
phase1_p1 --source-type coaching_derived --published-date 2025-01-01`: 65/65 questions
extracted with clean, gapless `question_number`s 1-65 (2 chunk-boundary duplicate
extractions correctly deduped by the existing BUG-13 guard, not lost content), 0 individual
questions flagged. 7 whole *chunks* (cover/instructions pages, not question content) were
flagged "no registered topic matched" — BUG-09's independent-failure-mode design already
means this doesn't touch question extraction; a real but harmless retrieval-embedding gap,
not investigated further (out of this session's scope).

**Answer key was ALSO real digital text, not scanned — a stricter-than-required mechanical
path was possible.** `scripts/extract_answer_key.py` exists for a *scanned* key (Haiku
vision transcription, per DECIDE-27) — the wrong tool here. Wrote
`scripts/extract_answer_key_digital.py` instead: `pdfplumber` text extraction + a plain
regex over `"<number>. (<letter>)"` pairs, zero LLM call anywhere in the script (stricter
than DECIDE-27 demands, which only bans an LLM from *judging* the answer — here there isn't
even a transcription judgment call). Output matches `extract_answer_key.py`'s existing JSON
shape exactly, so `scripts/merge_answer_key.py` merged it unmodified — no changes to the
already-tested mechanical-merge script. Result: **65/65 verified against the real key, 0
unverified, 0 void** — the first RBI DEPR paper-instance with a complete real key, unlike
EPFO's own history of partial-coverage years.

**Real gap found and fixed with the real source, not guessed:** Q55's 4 options straddled a
page break in the source PDF; `enrich_chunk`'s per-chunk extraction only captured 2 of them
(`merge_answer_key.py` printed its existing "only has 2 option(s) extracted" warning,
correctly still merging the real letter). This is the same BUG-13/14-class chunk-boundary
miss already known from EPFO ingestion. Fixed by hand from the exact same source PDF page
already visually verified during this session's own read-before-building step (literal
transcription of real printed text — `["21.2", "28.6", "36.5", "42.1"]` — not an LLM guess;
`correct_option='C'` was already right from the mechanical merge, only `options` was
incomplete). No other question in this batch had an option-count anomaly.

**`scripts/migrate_012_recompute_rbi_depr_phase1p1_weight.py`** recomputed `phase1_p1`'s
`exam_topics.weight` from this real data, reusing DECIDE-31's exact Q2 recency-decay formula
(`weight = Σ 0.9^(2026 - year)` per real observed occurrence) — no parent/subtopic rollup
needed here (all 8 `phase1_p1` topics are top-level, unlike PFRDA's subtopic layer). All 65
questions are year 2025, so decay is a flat 0.9 per occurrence:

| topic_id | before | after | real question count |
|---|---|---|---|
| `depr_quant_methods_econ` | 1.0 | 14.4 | 16 |
| `intl_econ` | 1.0 | 9.0 | 10 |
| `growth` | 1.0 | 8.1 | 9 |
| `macro` | 1.0 | 8.1 | 9 |
| `micro` | 1.0 | 6.3 | 7 |
| `pub_finance` | 1.0 | 6.3 | 7 |
| `indian_econ` | 1.0 | 4.5 | 5 |
| `env_econ` | 1.0 | 1.8 | 2 |

Only `rbi_depr`/`phase1_p1` was touched — `phase1_p2`/`phase2_p1`/`phase2_p2`'s still-
placeholder weights, and every other exam, are untouched (this is real signal for exactly
the paper that received real content, not a broader retroactive change).

**Real API cost:** ~$0.10 (Haiku 4.5: 8,131 input + 13,369 output + 9,206 cache-write +
110,472 cache-read tokens, one 14-page paper) — cents, matching the cost-consciousness ask;
the digital-text answer key extraction cost $0, no LLM call at all.

**Verification:** `tests/test_extract_answer_key_digital.py` (8 new, pure-function tests
against the parser, no PDF/LLM I/O) + `tests/test_migrate_012.py` (4 new, throwaway-sqlite
pattern per `tests/test_migrate_011.py`'s precedent) — 70 pre-existing + 12 new = 82/82
passing.

**Not done, real follow-up:** `rbi_depr`'s other 3 papers (`phase1_p2` English descriptive,
`phase2_p1`/`phase2_p2` Descriptive Economics) still carry DECIDE-32's flat placeholder
weights — this session only had real content for the objective Phase I Paper 1. `Set-2`/
`Set-3` remain real, unused source material until a matching key is found for either.

### DECIDE-36 — Added reusable, exam-agnostic `pyq_completeness_ledger` + readiness assessment for a future Eco Optional migration {#decide-36}
**Date:** 2026-09-17 | **Session:** external

**Decision:** Rahul noticed Scribe (Descriptive-exams, a sibling product) shows incomplete
PYQ counts for some years of UPSC Economics Optional; a separate, parallel audit is finding
the exact real gaps there by hand (comparing Scribe's DB against real official scanned exam
PDFs). That audit is a one-off. This task built the reusable infrastructure so the *next*
time "how much of the real exam content do we actually have, year by year" comes up — for
any exam, not just Eco Optional — it's a query, not a fresh manual comparison.

**What was built** (`scripts/migrate_013_pyq_completeness_ledger.py` — note: migration
number 012 was already claimed, uncommitted, by a concurrent session's
`migrate_012_recompute_rbi_depr_phase1p1_weight.py` at the time this ran; took 013 to avoid
a collision once both land):
- `pyq_completeness_ledger` — one row per `(exam_id, paper_id, year)`, the finest grain
  "how complete is this year's content" makes sense at. `expected_count` (nullable — the
  real count from an authoritative source, never invented), `actual_count` (live
  `COUNT(*)` from `pyq_bank`, computed by the population script every run, never manually
  typed so it can't drift), `source_reference` (free text, a real file path/citation),
  `status` (`complete`/`partial`/`unaudited`, CHECK-constrained, derived automatically —
  never passed in), `gap_detail` (free text, which question numbers are missing, when
  knowable), `last_audited_at`. Composite PK `(exam_id, paper_id, year)` mirrors `papers`'
  own composite-PK pattern (DECIDE-21) and gives the "proper index on the triple" for free
  via SQLite's automatic unique index, same as `papers`' `sqlite_autoindex_papers_1`; a
  separate `idx_pyq_completeness_status` index serves the "every partial/unaudited row,
  fast" query. FK is the composite `(exam_id, paper_id) REFERENCES papers(exam_id,
  paper_id)`, same pattern `pyq_bank` already uses. Nothing exam-specific is hardcoded.
- `scripts/pyq_completeness.py` — `record` (upsert one row: computes `actual_count` live,
  derives `status` — `unaudited` if `expected_count` unknown, `complete` if
  `actual >= expected`, `partial` otherwise, including the `actual==0`-but-`expected`-known
  case, which is a real quantified gap, not "we don't know") and `report` (prints every
  non-`complete` row explicitly, worst-covered first — unaudited rows sort ahead of
  quantified partial gaps, and any paper registered in `papers` with **zero** ledger rows
  at all is flagged separately, so an un-recorded paper is never silently indistinguishable
  from a clean one. A rollup summary line comes after, never instead of, the explicit
  listing — same anti-false-positive mechanism the `layered-coverage` skill's "a higher
  metric must never hide a lower gap" rule already established for `topic_coverage`).
  Verified against zero-content `eco_optional_1`/`eco_optional_2` (real live state today —
  `actual_count=0`, no error) and against `upsc_epfo_apfc_eo_ao`/`gat`/2023's real
  114/120-verified content from DECIDE-27 (produces `partial` at expected=120,
  `complete` at expected=114) before deleting the sanity-check rows — real progress data,
  same discipline DECIDE-34's demo cleanup established.

**Migration-readiness assessment** (`docs/eco_optional_migration_readiness.md`) — checked,
not assumed, against both live DBs:
- **Taxonomy:** confirmed live — `eco_optional_1` has 6 reused canonical topics,
  `eco_optional_2` has 1 (`indian_economy_structural`); Scribe's own `upsc_eco_opt.db`
  already has 81 real topic/subtopic rows (31 P1 + 50 P2) with a real `topic_level`
  distinction. Per DECIDE-29's precedent, a fresh Eco-Optional-specific taxonomy must be
  curated before migration — Scribe's 81 rows are a legitimate starting point to verify
  (same precedent as importing IES/RBI Grade B's taxonomies), not a ready-made import,
  since the parallel audit is checking exactly this kind of classification for errors.
- **Provenance mapping:** Scribe's `pyq_questions.source_type` has exactly the same two
  values nyaya-core already uses (`official_pyq`/`coaching_derived`) — no string
  translation needed. But Scribe has no `status`-equivalent column at all; every migrated
  row must land as nyaya-core `status='unverified'` regardless of `source_type`, per
  DECIDE-27's rule that `verified` is earned only by an actual human check against a real
  source, never inferred from provenance labels.
- **ID convention:** Scribe's `question_id` (`upsc_p1_0001`-style, flat sequence, no year
  scoping) and its total lack of a `question_number` column don't fit nyaya-core's
  chunk-derived `question_id` + literal `question_number` split (DECIDE-27). Real
  `question_id`s would need regenerating via nyaya-core's own ingestion against real source
  PDFs, and `question_number` backfilled from the real paper — not derivable from Scribe's
  DB alone. Also surfaced a live, concrete blocker: 55 of Scribe's 908 rows
  (`upsc_p2`, 6%) carry `year=0` (unresolved) and can't be placed at this ledger's grain
  until resolved against a real source (L-16/L-17: flag-and-halt, never guess).

**Explicitly not done:** no taxonomy built, no `pyq_bank` rows written, no existing
`eco_optional_1`/`eco_optional_2` `exam_topics` rows touched — this is tooling + a plan,
migration itself is a separate future task pending Rahul's review of this doc and the
parallel audit's findings.

**Verification:** 82 pre-existing (after DECIDE-35's merge) + 19 new
(`tests/test_migrate_013_pyq_completeness_ledger.py`, `tests/test_pyq_completeness.py`,
covering empty-exam/zero-content, complete, partial, and unaudited cases) = 101/101 passing.

**A real process note, not a design decision:** this task ran in a shared working directory
with the concurrent DECIDE-35 session (same repo checkout, no worktree isolation) — HEAD
moved between branches mid-task as that session committed. Verified `data/core.db` is
git-untracked (checkouts never touch it) before proceeding, then fast-forwarded this
task's branch onto the finished DECIDE-35 commit rather than diverging from it. Flagging
here so a future reader isn't surprised this branch's first parent is DECIDE-35's commit.

### DECIDE-37 — Phase 2 (hybrid retrieval + API) built; PFRDA/EPFO practice sequenced as an additive Devthorium path, not a full Recall cutover {#decide-37}
**Date:** 2026-09-17 | **Session:** S9

**Decision:** Built PLAN.md's Phase 2 exactly as spec'd —
`src/retrieval/hybrid_engine.py` (`LocalHybridEngine`: LanceDB dense vector + LanceDB
native FTS + RRF k=60 + FlashRank cross-encoder rerank, score floor →
`insufficient_grounding` per DECIDE-10, `source_type='ai_generated'`/`is_current=False`
exclusion, auto-merge via `sections.full_text` per DECIDE-14) and `src/api/` (FastAPI:
`/exams /papers /topics /search /pyq /topic/{id}/brief /verify_citation /ingest`, bound
to `127.0.0.1` only). Also added `POST /attempt` (`src/api/routes_attempts.py`) — beyond
the original Phase 2 spec — so `scripts/quiz.py`'s CLI and any future web consumer share
one real `user_attempts`/`topic_coverage` signal instead of forking a second attempt
history for the same real questions. `scripts/inventory.py` built first, per its own
purpose: it immediately surfaced that `chunks` (LanceDB) has **zero PFRDA rows and only
125 thin EPFO rows** against 470/660 real `pyq_bank` rows — so `/search`-based grounding
is effectively unusable for PFRDA today and thin for EPFO; `/pyq` (structured, abundant)
is the real foundation for both exams, not `/search`.

For getting PFRDA/EPFO MCQ practice into Devthorium ("Recall") specifically: build it as
a **new, additive code path**, not a unification of Devthorium's existing
Chroma/`syllabus.json` pipeline. Two research passes this session verified Devthorium's
hardcoding (`DB_PATH`/`syllabus.json`/one Chroma collection, zero `exam_id` concept
anywhere) spans 6+ route files and 30+ scripts — a full refactor is real, multi-session
work with regression risk to the UPSC Prelims flow Rahul studies from daily, for zero
PFRDA/EPFO benefit (that pipeline serves neither exam today). PFRDA/EPFO have nothing to
migrate *from* in Devthorium, so an additive path costs zero migration risk to the
working product and gives PLAN.md's own Phase 3 ("migrate + cut over Recall," which
already assumes prove-then-migrate, not simultaneous cutover) a lower-stakes proving
ground later.

Also found (not yet fixed as a design change, only patched at read-time — see BUG-15):
Devthorium's existing "PYQ pattern dimensions" (`generate_syllabus_dimensions.py`) are not
actually derived from real PYQ text — it sends Haiku only `{subtopic_id, name}` and asks
it to invent dimensions from training knowledge, zero real PYQ/Chroma content passed in.
For PFRDA/EPFO (far more niche than UPSC Prelims) this is a real quality risk, so any new
dimension-generation script for these exams should ground itself in nyaya-core's real
`/pyq` corpus instead — ideas for this are in `~/.claude/plans/functional-stirring-galaxy.md`
(Phase B), not yet built this session.

**Rationale:** Matches this project's own established build discipline (verify against
real data before designing on top of it — `inventory.py` existing specifically prevents
the "assumed /search would just work" failure mode) and Rahul's explicit choice to build
toward the full unified-platform vision without destabilizing what already works daily.
**Rejected:** Simultaneous full Recall cutover (unification-first) — rejected as
disproportionate risk to a live daily-use product for zero immediate PFRDA/EPFO benefit.
**Verification:** 127/127 tests passing (101 pre-existing + 26 new across
`tests/test_hybrid_engine.py`, `tests/test_api.py`, and `tests/test_quiz.py`'s new
`normalize_options` cases) — includes a live regression test against the real local DB
confirming `search("...", "pfrda_gradea")` returns `insufficient_grounding=True` rather
than crashing or silently returning an empty-but-"ok" result.
**Consequence:** BUG-15 (found + fixed in the same session). Phases B (real-PYQ-grounded
dimension generation), C (Devthorium exam-context plumbing), and D (UI exam switching) —
all Devthorium-side — are the next unblocked work, not yet started.

### DECIDE-38 — Persisted, indexed AI-generated question bank in `pyq_bank` {#decide-38}
**Date:** 2026-09-18 | **Session:** S10 | **Status:** Active

**Decision:** AI-generated PFRDA/EPFO practice questions are stored directly in `pyq_bank`
(`source_type='ai_generated'`, `status='unverified'` by default) rather than a new
dedicated table, and the generation pipeline (`scripts/generate_ai_pyq_bank.py`,
`prompts/ai_pyq_bank_quiz.txt`) lives in nyaya-core, not Devthorium. `unverified` is not a
serving gate — AI rows are served immediately, same as real content; a new optional
`scripts/review_ai_questions.py` lets Rahul spot-check and flip specific rows to
`verified`/`void`. Structured per-option rationale is written into `pyq_explanations` at
generation time (closing DECIDE-23's long-open "batch generator never built" gap). No
external sourcing — generation grounds strictly in the syllabus + real PYQs already
ingested (Rahul's explicit choice).
**Rationale:** `source_type='ai_generated'` was already a first-class value in
`src/schema/models.py`'s `SourceType` literal, anticipated but never used — reusing
`pyq_bank` means every existing consumer (indexing, `topic_coverage`, the `/pyq` API, the
Devthorium drill's serving filter) works with zero new query surface. Building the
pipeline in nyaya-core (not Devthorium, where Devthorium's own unmerged PR #58 put an
equivalent live/ephemeral version) matches the documented target architecture — "nyaya-
core is the single indexed data platform, Recall a thin consumer." Gating on `status='verified'`
before serving was rejected as impractical: spot-checking every generated question before
use isn't realistic at exam-prep scale; a UI badge (`source_type`) is the honesty
mechanism instead.
**Rejected:** A new dedicated `ai_generated_bank` table (would duplicate indexing/serving
logic for no real benefit); gating on human review before serving (too slow for the real
urgency — PFRDA/EPFO exams have near-term dates); reviving Devthorium PR #58's ephemeral
per-session approach (throws away every generated question, no reusable bank).
**Verification:** Piloted live on `pfrda_reasoning_syllogism` (7 questions written,
verified via `/pyq` and end-to-end in Devthorium's `/nyaya` drill UI in a real browser).
Full-scale run attempted same session — see BUG-16/17 in `docs/bugs.md` and RISK-10 in
`docs/risks.md` for what actually happened.
