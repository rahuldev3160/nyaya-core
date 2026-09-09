# Project HANDOFF

## Exact next step
9 exams now registered, 8 with a seeded topic taxonomy (only `rbi_depr` and `upsc_cse`'s
non-prelims papers have none). `upsc_epfo_apfc_eo_ao` (DECIDE-24, S5) is the newest —
seeded with REAL weights from an actual 2025 paper (RESEARCH-10), not coaching-site
guesses. Still nothing has been ingested for real — Phase 1 is fully built but only
smoke-tested against synthetic content. Real next actions, no particular order:
- **Ingest the real 2025 APFC/EO/AO paper** (`Desktop/opportunities/govt notifications/
  epfo_apfc_eoao_2025_question_paper.pdf`, English side) into `upsc_epfo_apfc_eo_ao` via
  `scripts/ingest.py` — real content already exists for this exam specifically, no sourcing
  needed. This would also be the first-ever real (non-synthetic) ingestion run for the whole
  platform, so it validates Phase 1 end-to-end at the same time.
- Otherwise, run `scripts/ingest.py` for real against actual content for any of the other 7
  seeded exams.
- When ready to build the PYQ-explanation batch-generation script: it must validate against
  `PYQExplanation` before writing (partial response = `ReviewNeededError`, never a silent
  partial write) and ground explanations in real retrieved chunks — both are direct fixes
  for BUG-04, not optional nice-to-haves.
- Phase 2 (hybrid retrieval + API) is the bigger remaining phase — better sequenced after a
  real ingest run gives it something real to retrieve against.
- `upsc_epfo_apfc_eo_ao`'s weights are from a single verified year (2025) — worth
  recomputing from real ingested `pyq_bank` topic-tag frequency once more years of content
  exist, rather than treating this as final (see DECIDE-24's caveat).

## Session narrative (2026-09-09, S5)
Rahul asked to move forward with Nyaya Core and, separately, whether UPSC APFC (an exam
notification sitting in his `Desktop/opportunities/govt notifications/` folder, closing
2026-09-11) was already registered — it wasn't. Researched real PYQ patterns via 3 parallel
forks (APFC-specific, EO/AO-specific, wider EPFO family) — found APFC/EO/AO have been one
combined paper since 2025 (not two exams), EO/AO itself is shelved for 2026 (EPFO withdrew
the requisition), and SSA/Stenographer are a structurally different IBPS-conducted exam
with thin syllabus overlap (RESEARCH-09). Weightage from coaching sites was disputed/
self-contradicting across sources.

While waiting on Rahul's naming call (autonomous-loop tick), found a real 2025 combined
APFC/EO/AO question booklet already sitting in the same notifications folder — read all 44
pages/120 items in full and extracted verified, real subject-wise question counts
(RESEARCH-10), which corrected several of the disputed coaching-site numbers materially
(Labour Codes: real 15, not the estimated 3-14 range).

Rahul confirmed the exam should be named around all 3 posts together
(`upsc_epfo_apfc/eo/ao` — adjusted to `upsc_epfo_apfc_eo_ao`, slashes aren't valid in an
exam_id used as a SQLite PK/filename/URL param). Registered it (DECIDE-24): 7 topics reused
from the existing canonical taxonomy with real weights (not the reuse path's previous flat
1.0 — extended `seed_topics.py` to support this, backward compatible, verified against the
existing `uppcs.json`), 20 new topics across 4 exam-specific subjects (English, Science/
Computer, Labour Codes — 9 real named Acts — and Accountancy/Auditing/Insurance). All
weights sum to exactly 120, matching the real paper. Logged as RESEARCH-09/RESEARCH-10/
DECIDE-24 in the audit system.

## Session narrative (2026-09-06, S4)
**Phase 1 is complete.** `scripts/ingest.py` walks a folder and drives
chunk_document → enrich_chunk → write_chunk per file, with hash-based skip-list
resumability, published_date inference, per-chunk uncertainty handling (flagged, not
crashed), and a cost/usage summary at the end. Verified end-to-end with a real smoke run
against a synthetic Article 21/22 `.docx` (throwaway DB/LanceDB copies, real project data
untouched) — correct chunking, correct topic classification, correct LanceDB write.

**exam_id/paper_id naming is now finalized (DECIDE-21) — read this before registering any
new exam.** `exam_id` = `{institution}_{exam}` (`upsc_cse`, `upsc_ies`, `rbi_gradeb`,
`rbi_depr`, `uppcs`, `hpas`, `ukpsc`, `mppsc` — 8 exams total). `paper_id` is short,
un-prefixed, scoped by a composite `(exam_id, paper_id)` key in `papers` — never repeats the
exam's identity. Full checklist in `docs/DATA_DICTIONARY.md`'s Naming conventions section.

**Also added: a real `institutions` table (DECIDE-22).** Rahul asked whether naming rules
are tracked anywhere queryable, not just documentation. Answer: the naming *grammar* stays
documentation (nothing queries a rule at runtime) — but "institution" was a real missing
*dimension*, only present as an unqueryable string prefix inside `exam_id`. Added
`institutions` + `exams.institution_id` FK, seeded for all 8 exams. "Every exam UPSC
conducts" is now `JOIN institutions`, not `exam_id LIKE 'upsc_%'` — see
`docs/DATA_DICTIONARY.md`'s new "Rules vs. data" section for the full reasoning. **Pushed to
GitHub: https://github.com/rahuldev3160/nyaya-core (public, per Rahul's explicit choice —
verified `.env` was never committed to history first).**

**Then: `pyq_explanations` schema designed (DECIDE-23), informed by a real Recall failure
(BUG-04).** Rahul described a future MCQ practice feature and asked to look into Recall's
existing equivalent first. Found it 100% broken: all 904 rows in Recall's
`question_explanations` table have every wrong-option field silently empty, because the
schema forces four independent option notes onto statement-based questions (the dominant
real UPSC format — "how many of the following statements are correct") where that shape
doesn't apply. Also zero grounding (pure model recall, no citations) and a "Resolved" issue
(ISSUE-013) that only ever covered 3 of the 4 surfaces sharing this defect.

Built (schema only — the generation script itself is later, on-demand, per Rahul's explicit
choice): `MCQQuestion.statements` (populated at PYQ-extraction time when a question is
statement-based — live-tested against a real 3-statement question via the actual Haiku API,
correctly detected and extracted), a discriminated `ExplanationDetail` union
(`StandaloneExplanation`/`StatementBasedExplanation`) so per-statement vs. per-option
rationale never gets forced onto the wrong shape, `PYQExplanation` (concept_summary always
shown, detail only on a wrong attempt, `elimination_strategy` as a first-class field — real
exam-technique reasoning never attempted anywhere in this system before), and a new
`pyq_explanations` table. All new model validation tested (`tests/test_explanation_models.py`
— confirms the union actually rejects a mismatched shape, not just that valid input passes).

**Cross-project fallout logged the same session** (Rahul explicitly asked for this): new
`ISSUE-029` in Devthorium's `ISSUES.md` for the actual bug, a follow-up note on `ISSUE-013`
clarifying its fix never covered this surface, `GL-06` in `~/.claude/GLOBAL_LEARNINGS.md`
(a "Resolved" issue only covers what was checked, not the whole bug class), and Devthorium's
own close-task checklist updated to check sibling features before closing an issue in future.

7 exams now have a seeded topic taxonomy: `upsc_cse` (271, all under paper `prelims_gs`),
`upsc_ies` (156, real papers `ge_01`-`ge_04`), `rbi_gradeb` (38), `uppcs`/`hpas`/`ukpsc`/
`mppsc` (19/15/31/20). Only `rbi_depr` and `upsc_cse`'s non-prelims papers (mains_gs1-4,
essay, eco_optional, law_optional) have zero topics yet — real, not a bug, just no content
sourced there yet.

Next is either Phase 2 (hybrid retrieval + API — `LocalHybridEngine`, FastAPI endpoints,
`scripts/inventory.py`), OR running `scripts/ingest.py` for real once Rahul has an actual
content folder ready for any of the seeded exam/paper combinations. Recommend the real
ingest run first: Phase 2's retrieval logic is much easier to validate against real indexed
content than against nothing.

Run command: `.venv/bin/python scripts/ingest.py --folder <path> --exam-id <exam_id>
--source-type <official_pyq|ai_generated|coaching_derived|self_notes> [--paper-id <paper_id>]`
(`--paper-id` narrows topic classification to one paper within the exam — set it whenever a
folder's content is known to belong to one paper, e.g. only Ethics-paper PDFs.)

**Also fixed post-Phase-1, same session:** Rahul asked hard questions about the taxonomy
that surfaced a real design gap — `topics.exam_id NOT NULL` silently locked in "no cross-exam
topic sharing" without that ever being an explicit decision, and it turned out to be exactly
Descriptive-exams' `DECIDE-32`, pending since 2026-06. Fixed same session: see DECIDE-19,
`scripts/migrate_002_topics_exam_agnostic.py` (already run against the live `data/core.db`,
271 rows migrated with zero loss), `src/ingestion/enrich.py::load_topics()` and
`scripts/seed_topics.py` both updated to match, all 21 tests re-verified passing.

**Then: 4 State PCS exams registered and seeded (DECIDE-20).** Rahul named 8 target State
PCS exams; real eligibility research (RESEARCH-08) found 4 confirmed feasible for him right
now — **UP (`uppcs`), Himachal (`hpas`), Uttarakhand (`ukpsc`), MP (`mppsc`)** — all
registered in `exams` and seeded via the extended `seed_topics.py` (now supports a
`reused_topics` list alongside the existing `subjects` shape, in `data/syllabi/
{uppcs,hpas,ukpsc,mppsc}.json`). Verified the DECIDE-19 payoff directly: "polity" is one
canonical topic row now linked to 5 exams via `exam_topics`, not duplicated — `topics` grew
by only the 45 genuinely new state-specific rows, not 4x the shared UPSC content.
**4 exams left unresolved, not built:** Gujarat is excluded (Rahul's own condition —
Gujarati is a compulsory qualifying Mains paper, not just an option). Haryana, Maharashtra,
and Rajasthan each have one specific open question (see RESEARCH-08) before any taxonomy
work should start for them — don't build these without resolving that question first.

**Then: exam_id/paper_id naming finalized + IES/RBI imported (DECIDE-21).** Rahul flagged
real ambiguity in the naming (`upsc_eco_optional` doesn't say which UPSC exam; a
hypothetical `rbi_eco` wouldn't say Grade B vs DEPR) and asked for researched options before
finalizing. Presenting them surfaced the actual root cause: Essay/Ethics/GS/both Optionals
were modeled as 6 separate top-level exams in Phase 0 when they're really papers of one
exam (UPSC CSE) — the `papers` table existed for this and had zero rows. Rahul confirmed
the restructuring. Ran `scripts/migrate_003_exam_paper_restructure.py` against the live DB
(zero data loss — only `upsc_prelims_gs` had real dependent data). `papers`' PK is now the
composite `(exam_id, paper_id)`; `exam_topics` gained a `paper_id` column (default `'_all'`
sentinel); `topics` gained a `notes` column. `enrich.py`/`ingest.py`/`seed_topics.py` all
paper-aware now. Then imported IES (156 topics, real `ge_01`-`ge_04` papers) and RBI Grade B
(29 topics + 9 subject groupings) from Descriptive-exams' `ies.db`/`rbi.db` — no new
research needed, checked for `topic_id` collisions first (zero found). All 21 tests
re-verified passing after every schema change in this sequence.

## Open items
- **`topics` is now exam-agnostic (DECIDE-19)** — a topic like "monetary_policy" is one
  canonical row, linked to whichever exams care about it via `exam_topics`. Only
  `upsc_prelims_gs` is linked today (271 rows, real weights from Devthorium's syllabus.json
  — `avg_questions_per_year` per subject). `enrich.load_topics()` raises `ReviewNeededError`
  for any exam with zero `exam_topics` rows. **Real, unimported taxonomies already exist**
  for 2 more exams — no new research needed, just an importer:
  - `ies.db`'s `topics` table (Descriptive-exams repo): 156 rows, real 3-level hierarchy
  - `rbi.db`'s `rbi_topic_weights` (Descriptive-exams repo): 29 rows, real PYQ-derived weights
  **EPFO-APFC and State PCS have no internal source** — real official data found this
  session (RESEARCH-07): EPFO-APFC 2026 syllabus is a flat subject list (several subjects —
  Polity/Economy/Current Affairs — directly reusable via `exam_topics` against existing
  `upsc_prelims_gs` topics; Labour Laws/Social Security/Accounting/Statistics/Auditing/
  Insurance are genuinely new branches needing real curation). State PCS (checked UPPSC)
  structurally overlaps UPSC heavily — but "State PCS" isn't one exam; needs Rahul to name
  the specific state(s) before real per-state taxonomy work starts. EPFO-APFC applications
  close **11 Sept 2026** — flag to Rahul if this is a real target, separate from the
  taxonomy question.
  - `essay`, `ethics`, `upsc_mains_gs`, `upsc_law_optional` still have zero taxonomy source
    of any kind, internal or external — genuinely open.
- Law/Econ Optional content sourcing is on Rahul (ASSUME-01) — no action needed from this
  project until he supplies PDFs.
- Naming: repo is currently `nyaya-core` as a placeholder — confirm with Rahul or leave as-is.
- No project venv existed before this session despite Phase 0 claiming a verified import
  surface — created `.venv` (Python 3.11) + installed `requirements.txt` this session so
  code can actually run. Use `.venv/bin/python`, not bare `python3` (that resolves to
  Homebrew's 3.14 or system 3.9, neither has the deps installed).
- Created `nyaya-core/.env` (gitignored) this session, copying `ANTHROPIC_API_KEY` from
  Devthorium's `.env` — needed for the enrichment call's live API access.

## Session log
**2026-09-06 (S4):** Built Phase 1's chunker AND the Haiku enrichment call in one session.
Found and fixed BUG-02 first (all 3 PDF
parsers discarded page boundaries — joined pages into one string before returning; the
other 4 parsers normalized to the same `list[(page_num, text)]` shape for interface
consistency). Logged DECIDE-17 (exam_id is ingestion-run-scoped/caller-supplied, not
Haiku-classified — confirmed by checking Devthorium's `ingest_pyq.py` classify pattern,
which only ever classifies topic within one already-known exam). Built
`src/ingestion/chunker.py`: `split_sections()` (Stage 1, heading-line detection incl. a
hard `Article N`/`Section N` boundary rule for statute integrity), `persist_sections()`
(writes to `sections` table), `chunk_section()` (Stage 2, atomic-block packing — paragraphs,
with consecutive table rows kept as one unbreakable block; an oversized block is emitted
whole rather than split), `chunk_document()` (end-to-end driver). Wrote
`tests/test_chunker.py` (4 tests, all passing) covering statute-boundary integrity,
table-row atomicity across a chunk boundary, paragraph-boundary splitting on a long
headerless section, and page-number/section persistence end-to-end. Created project `.venv`
(none existed) and installed `requirements.txt` to actually run the tests. Installed Ollama
via Homebrew + pulled `nomic-embed-text` (274MB) — both running locally, ready for the
embedding step.

Then found the `topics` table was empty (Phase 0 never seeded it) — would have forced the
enrichment call to either invent topic_id strings (reintroducing the free-text problem
DECIDE-04 exists to prevent) or fail outright. Wrote `scripts/seed_topics.py`, imported
Devthorium's real `data/syllabus.json` for `upsc_prelims_gs` (271 rows, subject > topic >
subtopic — DECIDE-18). Built `src/ingestion/enrich.py`: one Haiku call per chunk
(`prompts/enrich_chunk_system.txt` for the cacheable per-document static content —
valid content_types + valid topics + source doc text; `prompts/enrich_chunk_user.txt` for
the per-chunk varying part), returns `ChunkMetadata` + optional `PYQQuestion`.
`ReviewNeededError` raised (not a silent default) when Haiku can't match a registered topic,
or a PYQ is missing year/correct_option. `source_type` is caller-supplied, same reasoning as
DECIDE-17's `exam_id` — provenance is known before ingestion, not inferred from chunk text.
Wrote `tests/test_enrich.py` (7 tests, all passing, using a fake response — proves the
parsing/validation logic). Then ran a real live smoke test against the actual Haiku API on
an Article 21/22 sample: correctly classified to `right_to_freedom`, sensible
`context_prefix`, no hallucinated PYQ on non-PYQ content — and confirmed prompt caching
actually fires (`cache_creation_input_tokens` on the first chunk of a doc,
`cache_read_input_tokens` on the second) rather than just assuming DECIDE-13's cache_control
parameter does what it's supposed to. Created `nyaya-core/.env` (none existed) with
`ANTHROPIC_API_KEY` copied from Devthorium's for this.

Finally built `src/ingestion/embed.py`: `ChunkRecord` (a `LanceModel` mirroring
`ChunkMetadata` plus the `vector` field; `tags` stored as a JSON string rather than a native
map, to sidestep pyarrow map-type friction for a field nothing inside LanceDB queries by
key), `embed_text()` (Ollama `nomic-embed-text`, confirmed 768-dim), `write_chunk()`
(embeds `context_prefix + content` together — the actual point of Contextual Retrieval —
and upserts via LanceDB's `merge_insert` on `chunk_id` so re-ingesting a document updates
existing rows instead of duplicating them, which the later incremental-ingestion step
depends on). `tests/test_embed.py` (2 tests against a real local Ollama call and a
throwaway LanceDB table, confirmed upsert-not-duplicate behavior explicitly).

Closed out Phase 1 with `scripts/ingest.py`: walks a folder, drives the full
chunk→enrich→embed pipeline per file, hash-based skip-list (`data/ingestion_log.json`,
same pattern as Devthorium's, saved after every file so a crash mid-batch doesn't lose
progress), `data/flagged_chunks.jsonl` for chunks Haiku itself flagged as uncertain (run
continues rather than aborting), filename-year `published_date` inference (plus a CLI
override), and a cost/usage summary. Added `enrich.persist_pyq()` (writing extracted PYQs
to `pyq_bank` was still missing) and threaded `published_date`/usage-stats through
`enrich_chunk()`'s return. Ran a full real smoke test (synthetic Article 21/22 `.docx`,
throwaway copies of core.db and LanceDB so real project data stayed untouched): 2 sections,
2 correctly-classified chunks, 2 LanceDB rows, 0 false PYQs. `tests/test_ingest.py` (8
pure-logic tests) caught a real regex bug: `\b(19|20)\d{2}\b` never matches a year after an
underscore (e.g. "report_2023") because `\b` doesn't fire between two word characters —
fixed with a digit-lookaround instead. 21/21 tests passing across all 4 new test files.
PLAN.md/MASTER_INDEX.md/decisions.md/bugs.md updated in the same session.


**2026-09-05 (S3):** Phase 0 built end-to-end, as a concept-first learning session (Rahul is
building this project specifically to learn the underlying concepts, not just ship it).
Wrote `src/schema/models.py` (`TextChunk` pre-enrichment shape, `ChunkMetadata` matching
DATA_DICTIONARY.md's `chunks` row, `PYQQuestion` as a Pydantic discriminated union of
`MCQQuestion`/`DescriptiveQuestion` on `question_format`) — verified the union actually
rejects a malformed MCQ missing `options` (ValidationError), not just that valid input
passes. Wrote `scripts/init_db.py` — full SQLite schema (`exams`, `papers`, `topics`,
`content_types`, `sections`, `pyq_bank`, `chunk_tags`), `PRAGMA foreign_keys = ON`,
idempotent `INSERT OR IGNORE` seeding — ran it, confirmed 8 exams + 9 content_types seeded.
Ported all 7 parser modules from `../Devthorium/scripts/parsers/` verbatim into
`src/ingestion/parsers/`, rebuilt the `__init__.py` import surface identically, verified all
7 extract functions import cleanly and their transitive deps (pdfplumber, pdf2image,
pytesseract, python-docx, bs4) are present in this environment.
Found and logged **DECIDE-16**: PLAN.md's own Phase 0 registry list names both
`upsc_eco_opt` (already-exists) and `upsc_eco_optional` (ASSUME-01 placeholder) — plausibly
the same exam. Seeded only `upsc_eco_opt` rather than risk a duplicate registry row; flagged
for Rahul's confirmation rather than guessing. `PLAN.md` Phase 0 checklist and
`docs/decisions.md`/`docs/MASTER_INDEX.md` updated in the same session.

**2026-09-04 (S2):** Rahul asked for an audit of S1's docs against 6 criteria (universal/
navigable, sufficient retrieval size, extensible indexing, vector reliability, latency,
hallucination) plus research into further architecture options. Researched (WebSearch, real
sources, see docs/research.md RESEARCH-01–05) LanceDB reliability, Anthropic's Contextual
Retrieval technique, embedding model choice, parent-document retrieval, and 2026 hallucination
mitigation practice. Found and root-caused a real bug: Scribe's `generate_answers.py`
truncates chunks to 400 chars — confirms Rahul's "explanations too short" complaint. Wrote
`docs/AUDIT-001-architecture-review.md` with findings + fixes. Adopted 5 new decisions
(DECIDE-08–12: caller-supplied retrieval budget, no mid-chunk truncation, extensible
tags/EAV field, score floor + explicit no-grounding signal, is_current/superseded_by hard
flag, browse endpoints) directly — no real tradeoff. 3 open questions were resolved this
session (see S3 above): adopt Contextual Retrieval (yes, DECIDE-13), adopt parent-document/
auto-merging retrieval (yes, DECIDE-14), citation verification aggressiveness (sampled/
high-stakes only, DECIDE-15).

**2026-09-04 (S1):** Project created from scratch this session. Investigated Recall
(Devthorium) and Scribe (Descriptive-exams) codebases to ground a spec doc's gap analysis;
scope expanded during planning into this standalone platform. Plan approved via plan mode
(`~/.claude/plans/sequential-herding-scone.md`). Mid-Phase-0, Rahul asked three sharpening
questions (topic+PYQ composite query, nomenclature reference, adaptability/freshness) —
answered and folded in as DECIDE-04/05/06/07 + RISK-01/02 before continuing scaffold.
Repo directory structure, docs/ audit system, FOUNDATION.md, DATA_DICTIONARY.md, PLAN.md
written.
