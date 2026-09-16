# Eco Optional migration readiness assessment

**Date:** 2026-09-17 | **Author:** external session, alongside DECIDE-35/36
(`pyq_completeness_ledger`, `docs/decisions.md#decide-36`)

**Purpose:** If/when Scribe's (`../Descriptive-exams`) real, quality Eco Optional PYQ data
in `data/upsc_eco_opt.db` is proposed for migration into nyaya-core's `upsc_cse` /
`eco_optional_1` / `eco_optional_2`, what would it need to satisfy first, per this
project's own established rules? This is a plan/tooling document only — **no migration
was performed, no Eco Optional content was written to `pyq_bank`, and nothing in
`eco_optional_1`/`eco_optional_2`'s existing placeholder topics was touched.** The actual
migration, if it happens, is a separate future task pending Rahul's review of this doc and
of the parallel audit currently comparing Scribe's DB against real official scanned exam
PDFs.

All findings below are against the **live** databases, queried directly, not assumed:
`data/core.db` (nyaya-core, this repo) and `../Descriptive-exams/data/upsc_eco_opt.db`
(Scribe).

---

## 1. Does `eco_optional_1`/`eco_optional_2` have a real seeded topic taxonomy yet?

**No — confirmed placeholder-only, and not close to sufficient depth.**

Live `exam_topics` rows in nyaya-core for these two papers today:

| paper_id | topic_id(s) | count |
|---|---|---|
| `eco_optional_1` | `env_econ`, `growth`, `intl_econ`, `macro`, `micro`, `pub_finance` | 6 |
| `eco_optional_2` | `indian_economy_structural` | 1 |

These 6+1 topics are the same **canonical, cross-exam-shared** topics also linked to
`rbi_gradeb`, IES's `ge_01`-`ge_04`, and DEPR (per DECIDE-32's cross-exam sync) — they are
broad subject buckets, not a real Eco-Optional-specific taxonomy at any usable granularity.

Scribe's own `topics` table, by contrast, already has a real, much deeper structure for the
same content: **31 topic/subtopic rows for Paper 1, 50 for Paper 2 (81 total)**, with a real
`topic_level` distinction (`topic` vs `subtopic`) — i.e. Scribe already built roughly what
DECIDE-29/30/31's "fresh taxonomy" precedent calls for; nyaya-core just never received it.

**Per DECIDE-29's established rule** ("fresh, exam-specific taxonomy replacing reused
canonical topics — appropriate when depth/scope genuinely differ", repeated for PFRDA in
DECIDE-30/31 and for DEPR/DSIM in DECIDE-32): Eco Optional's real content volume (908
questions spanning 1997-2025, see §3) is far beyond what a 6-topic and a 1-topic bucket can
usefully classify. **A fresh taxonomy must be built before migration** — the current
placeholders are not a base to extend, they're a stand-in that was never replaced.

Scribe's 81 topic/subtopic rows are a legitimate **starting point** to curate from (same
precedent DECIDE-21's session used when importing IES/RBI Grade B's real taxonomies
wholesale from Descriptive-exams' own `ies.db`/`rbi.db` — "no new research needed, sitting
unused"), but they should be **verified against the real syllabus, not imported blindly** —
per DECIDE-29's method, and because Scribe's own classification is exactly what the parallel
audit is currently checking for errors. Re-verifying topic assignments while re-verifying
question counts is the efficient order to do this in, not two separate passes.

## 2. What would Scribe's `source_type` values need to map to in nyaya-core's provenance model?

Live check of `pyq_questions.source_type` in Scribe's DB: only two distinct values exist,
**`official_pyq`** and **`coaching_derived`** — the identical vocabulary nyaya-core's own
`pyq_bank.source_type` already uses (same two values seen live in nyaya-core's EPFO/PFRDA
rows). The value strings need **no translation**:

| Scribe `pyq_questions.source_type` | nyaya-core `pyq_bank.source_type` |
|---|---|
| `official_pyq` | `official_pyq` (direct) |
| `coaching_derived` | `coaching_derived` (direct) |

**But `status` is where real work is needed — Scribe has no equivalent column at all.**
nyaya-core's `pyq_bank.status` (`unverified`/`verified`/`void`, DECIDE-27) is a **separate
axis from provenance**: `verified` is earned *only* by a real, human-checked match against
an authoritative source — for MCQs, `scripts/merge_answer_key.py` reading a real official
answer key (never inferred from `source_type`, never Haiku's own belief, per DECIDE-27's
explicit rule). Eco Optional is descriptive, so the MCQ-key mechanism doesn't literally
apply, but the underlying rule does: a question having `source_type='official_pyq'` in
Scribe's schema means *someone believed it came from an official paper when it was entered*
— it is not evidence that a person has since checked the transcribed text against the real
scanned PDF. Scribe's schema has no `verified_by`/`reviewed_at`-equivalent columns at all.

**Required mapping:** every migrated row, regardless of its Scribe `source_type`, must land
as **`status='unaudited'`** in `pyq_completeness_ledger` terms / **`status='unverified'`**
in `pyq_bank` terms until a human actually confirms the question text against a real source
document (exactly the parallel audit's job). This is the same discipline already applied to
PFRDA's `coaching_derived` rows (DECIDE-31) — provenance label and verification status are
independent, and a migration must not conflate "labeled official" with "confirmed correct."

## 3. What would Scribe's `question_id`s need to become?

Scribe's `question_id` format is a flat, paper-scoped sequence: **`{exam_short}_p{N}_{seq:04d}`**
(e.g. `upsc_p1_0001`) — not year-scoped, and carrying no relationship to the exam's own
literal printed question number. Scribe's schema has **no `question_number` column at all**.

nyaya-core's convention (`src/ingestion/enrich.py:197`, DECIDE-27) is:
- `pyq_bank.question_id` — an **internal, chunk-derived** string
  (`{chunk_id}_pyq_{i}`, where `chunk_id` = `{exam_id}_{source_stem}_{page}_{idx}`) —
  never the exam's own numbering, generated by nyaya-core's own ingestion pipeline from a
  real source file, not carried over from another system's ID.
- `pyq_bank.question_number` — the **literal number printed on the question paper**
  (DECIDE-27) — "the only key a real answer key [or, for descriptive papers, the real
  scanned question paper] can be matched against."
- Identifying tuple for the ledger/reporting purposes this task built:
  `(exam_id, paper_id, year, question_number)`.

**Concretely, before migration:**
1. `exam_id`/`paper_id` need remapping — Scribe's single `exam_id='upsc_eco_opt'` +
   `paper_id='upsc_p1'`/`'upsc_p2'` must become nyaya-core's `exam_id='upsc_cse'` +
   `paper_id='eco_optional_1'`/`'eco_optional_2'` (DECIDE-21's "papers, not separate exams"
   convention — already the live `papers` schema in this repo).
2. Real `question_id`s must be **regenerated by nyaya-core's own ingestion pipeline**
   against real source PDFs — Scribe's IDs cannot be copied over verbatim; they were never
   designed to be chunk-traceable.
3. A real **`question_number`** must be backfilled for every row from the literal exam paper
   — data Scribe's schema never captured. Not knowable from Scribe's DB alone.
4. **A real, live data-quality blocker found during this check:** Scribe's `paper_id='upsc_p2'`
   has **55 rows with `year=0`** (an unresolved/unknown-year placeholder) — 6% of that
   paper's 908 total rows. These can't even be placed at the `(exam_id, paper_id, year)`
   grain this ledger (and any future migration) requires until the real year is determined.
   Per this project's architecture lesson L-16 ("scarce-source data -> flag-and-halt, not
   guessed") and L-17, this is exactly the kind of gap that must be resolved by checking the
   real source, never inferred or defaulted to a placeholder year.

## Real counts found (context for the parallel audit, not acted on here)

Scribe's `pyq_questions` totals, live, for reference:

| paper_id | years covered | total questions | rows with year=0 |
|---|---|---|---|
| `upsc_p1` | 1997-2025 (29 years) | 497 | 0 |
| `upsc_p2` | 2000-2025 (missing 2002) | 411 | 55 |

908 total. This is not a completeness verdict (that's the parallel audit's job, backed by
real scanned PDFs) — it's the shape of what a future migration would need to place into
`pyq_completeness_ledger` at the `(exam_id, paper_id, year)` grain, once the year=0 rows are
resolved and a real taxonomy exists to tag them with.

## Summary — what must happen first, in order

1. Resolve the 55 `year=0` rows in Scribe's `upsc_p2` against real source papers (blocks
   even placing this data at the right grain).
2. Curate a fresh Eco-Optional-specific topic taxonomy for `eco_optional_1`/`eco_optional_2`
   (DECIDE-29's method) — Scribe's 81 topic/subtopic rows are a legitimate starting point to
   verify, not a ready-made import.
3. Re-ingest via nyaya-core's own pipeline against real source PDFs (not a DB-to-DB copy) so
   `question_id` is properly chunk-traceable and `question_number` is populated from the
   real paper.
4. Land every migrated row as `status='unverified'` regardless of Scribe's `source_type` —
   promote to `verified` only after a human confirms it against a real source, which is what
   the parallel audit is already doing.
5. Only then record real `expected_count`/`source_reference` rows in
   `pyq_completeness_ledger` (this task's new table) per `(exam_id, paper_id, year)`, so
   "how complete is our Eco Optional coverage" becomes `scripts/pyq_completeness.py report
   --exam_id upsc_cse` instead of a manual PDF comparison, permanently.

**Not done here, by design:** no taxonomy was built, no rows were written to `pyq_bank`, no
existing `eco_optional_1`/`eco_optional_2` `exam_topics` rows were changed. This document is
input to Rahul's decision, not an execution of it.
