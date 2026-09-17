# Project HANDOFF

## Exact next step
**DECIDE-37 (2026-09-17, S9): Phase 2 (hybrid retrieval + API) is built and tested —
127/127 passing.** `src/retrieval/hybrid_engine.py` (dense+FTS+RRF+FlashRank rerank,
score floor, trust-weighting, auto-merge) and `src/api/` (`/exams /papers /topics
/search /pyq /topic/{id}/brief /verify_citation /ingest` + new `/attempt`), bound to
`127.0.0.1` only. Run: `.venv/bin/python -m src.api.main`.

**Real finding, not hypothetical:** `scripts/inventory.py` (built first) immediately
showed PFRDA has **zero** indexed LanceDB chunks and EPFO only 125 thin ones (vs.
470/660 real `pyq_bank` rows) — `/search` returns `insufficient_grounding=True` for
PFRDA on essentially every query today. `/pyq` (structured, abundant for both exams) is
the real foundation for PFRDA/EPFO practice, not `/search` — confirmed via a live
regression test (`tests/test_hybrid_engine.py`).

**BUG-15 found + fixed same session:** `pyq_bank.options` is stored as a dict for
`pfrda_gradea` but as a plain list (no letters) for `rbi_depr`/`upsc_epfo_apfc_eo_ao` —
`scripts/quiz.py`'s `print_question()` would have crashed on every rbi_depr/EPFO row.
Fixed via a shared `normalize_options()` (`scripts/quiz.py`), reused by the new
`/pyq`/`/topic/{id}/brief` endpoints so every consumer sees one consistent shape.

**This work is part of a larger, already-approved plan** (Rahul asked for PFRDA/EPFO MCQ
practice "ASAP" and explicitly chose the full-architecture path over a quick interim UI):
`~/.claude/plans/functional-stirring-galaxy.md`. **Update, same session, after this
entry was first written: Phases A, B, and most of D are now DONE, merged, and pushed —
not "next steps" anymore.** Phase A (nyaya-core, this repo) shipped as above. Phase B
(`Devthorium/scripts/generate_dimensions_from_pyqs.py`, calling this platform's
`/topics`+`/pyq`) ran at full scale: PFRDA 121 topics/383 real dimensions (57 flagged
`insufficient_pyq_evidence`, mostly Research-stream stats with zero real content),
EPFO 28 topics/345 dimensions (1 flagged) — committed to Devthorium `main`
(`data/dimensions/{exam_id}.json`). Phase C's Mode 1 (real-PYQ drill, zero LLM calls —
`backend/nyaya_core_client.py` + `backend/routes/nyaya_pyq_drill.py`) and Phase D's UI
(`web/src/app/nyaya/page.tsx`, in both nav bars) shipped together as Devthorium PR #57,
reviewed and merged to `main` by Rahul. **Only Phase C's Mode 2 (AI-generated quizzes,
matching UPSC Prelims' dimension-based generation) remains undone** — deferred
deliberately: Devthorium's `quiz.py` has no single `exam_id`-branchable choke point
(`subject_id`/`subtopic_id` threaded through many nested functions), confirmed by
reading the full 1517-line file, not assumed. Tracked as Devthorium `FEATURES.md` #22.
Read the plan file for the original file-level design before picking that up.

**DECIDE-31 (2026-09-16, external session): the 3 real PFRDA paper-books are now ingested**
— 454 real MCQs + 16 descriptive prompts, `pyq_bank`, `source_type='coaching_derived'`
(these are coaching-site recollections, not official papers). Goal was reframed mid-session
by Rahul: not a flawless practice-quiz answer key (recollections inherently carry errors) but
coverage intelligence — which subjects/topics/subtopics/depth/style PFRDA Grade A actually
tests. Built a real subtopic layer under DECIDE-30's flat 28 topics: 50 subtopics for the 7
General-stream subjects that actually appear in real PYQs, sourced from the real notification's
own sub-items (`data/syllabi/pfrda_gradea_general_p2_subtopics.json`), plus 42 bottom-up
subtopics for Phase-1-Paper-1's aptitude sections derived from real question content
(`data/syllabi/pfrda_gradea_phase1p1_subtopics.json`, no official breakdown exists for these).
RISK-07 resolved for General stream — `exam_topics.weight` is now a real recency-decayed
frequency count, not a placeholder. **Full detail, including the 11-item conflict-resolution
policy and the pipeline (3 parallel verification agents → 3 parallel structuring agents →
`scripts/ingest_pfrda_structured.py`):** `docs/decisions.md#decide-31`.

**Same session, continued — DECIDE-32: RBI DEPR registered for real, RBI DSIM added as 11th
exam.** Rahul supplied RBI's real 2026 notification (`~/Desktop/opportunities/govt
notifications/DEPR29042026....pdf`) after RESEARCH-11 (below) found `rbi_depr` was only ever
a placeholder and hit a CAPTCHA wall trying to resolve a real structural dispute between two
coaching sources. Real notification resolved it: DEPR Phase II is two Descriptive Economics
papers (Micro+Macro, then Quant/Econometrics+Indian-Economy-Policy), no separate Statistics
paper. Also surfaced RBI DSIM (Department of Statistics and Information Management), a
separate cadre in the same notification whose 9-topic syllabus is a much closer real match to
PFRDA Research stream than DEPR's own econometrics module — registered as the platform's
11th exam. Executed RESEARCH-11's cross-exam topic-linking plan (`rbi_gradeb`'s existing
`macro`/`micro`/`growth`/`pub_finance`/`intl_econ`/`env_econ` now link to `eco_optional_1`,
IES's `ge_01`-`ge_04`, and DEPR; new `indian_economy_structural` topic links `eco_optional_2`
+ IES `ge_04`). PFRDA Research ↔ DSIM deliberately left unlinked (notes-only on each of
PFRDA's 11 Research topics) — real 1:1 syllabus-name overlap, but zero real PFRDA
Research-stream PYQ evidence exists to confirm matching depth. 41/41 tests still passing.
Full detail: `docs/decisions.md#decide-32`, `docs/research.md#research-11`.

**RISK-08 resolved (2026-09-16, external session, same day as above):**
`pfrda_budget_economic_survey` additively cross-linked to canonical `indian_econ` (DECIDE-33,
`scripts/migrate_010_resolve_risk08_budget_ecosurvey.py`) — genuine scope match (Budget/
Economic Survey are primary-source current-developments documents, not theory of varying
depth, so DECIDE-30's UG/PG depth-mismatch concern doesn't apply). Real PFRDA frequency for
this topic explicitly left unconfirmed rather than inferred from the 0/3 recall-based
paper-book sample — see DECIDE-33 and GL-07 in `~/.claude/GLOBAL_LEARNINGS.md` for why that
inference would have been unsafe. 41/41 tests still passing.

**Next real steps, no particular order:**
- **Built `pyq_completeness_ledger` + `scripts/pyq_completeness.py` (DECIDE-36, 2026-09-17,
  external session, branch `feature/pyq-completeness-ledger`, forked from and fast-forwarded
  onto DECIDE-35's `feature/ingest-rbi-depr-2025` commit, not merged to main yet):** Rahul
  noticed Scribe shows incomplete PYQ counts for some UPSC Eco Optional years; a parallel
  audit is finding the exact real gaps by hand there. Built the reusable, exam-agnostic
  infrastructure so that question is always a query going forward, for any exam — not a
  one-off fix. New table `pyq_completeness_ledger` (one row per `exam_id`/`paper_id`/`year`:
  `expected_count` from a real source, live `actual_count` from `pyq_bank`,
  `source_reference`, auto-derived `status` complete/partial/unaudited, `gap_detail`,
  `last_audited_at`). `scripts/pyq_completeness.py record`/`report` — `report` never lets a
  partial/unaudited row hide in a rollup, and flags any registered paper with zero ledger
  rows at all as its own explicit category. Verified live against real zero-content
  `eco_optional_1`/`eco_optional_2` (actual=0, no error) and real EPFO 2023 GAT counts from
  DECIDE-27 (114/120 → partial, 114/114 → complete), then deleted the sanity-check rows
  (same discipline as DECIDE-34's demo cleanup) — `pyq_completeness_ledger` is empty again,
  ready for Rahul's own real audits. Also wrote
  `docs/eco_optional_migration_readiness.md`: confirmed live that `eco_optional_1`/`_2` only
  have 6+1 reused canonical topics (not real Eco-Optional depth) while Scribe's own DB
  already has 81 real topic/subtopic rows to verify-and-curate from; confirmed Scribe's
  `source_type` values map 1:1 to nyaya-core's but every migrated row must land
  `status='unverified'` (Scribe has no verification column at all); found Scribe's
  `question_id`s don't fit `(exam_id, paper_id, year, question_number)` and 55 of its 908
  rows (`upsc_p2`, 6%) carry an unresolved `year=0`. **No migration performed, no `pyq_bank`
  rows written, no existing topics touched** — plan/tooling only, pending Rahul's review of
  this doc plus the parallel audit. 101/101 tests passing (82 pre-existing after DECIDE-35's
  merge + 19 new). Full detail: `docs/decisions.md#decide-36`.
- **Ingested RBI DEPR's first-ever real content (DECIDE-35, 2026-09-17, external session,
  branch `feature/ingest-rbi-depr-2025`, not merged to main yet):** `rbi_depr`/`phase1_p1`
  (DECIDE-32's "Phase I, Paper 1 — Objective Type (Economics)") had zero real questions and
  all-flat-1.0 placeholder weights since registration. Ingested the real 2025 RBI DEPR
  Prelims Set-1 paper (`~/Desktop/UPSC/Mains/Other Eco Exams/RBI-DEPR (Prelims) Set-1
  (2025).pdf` + its answer key — both a real, digital-text Next IAS reproduction of the exam,
  `source_type='coaching_derived'`, not an RBI-official release) via the existing generic
  `scripts/ingest.py` pipeline (fit cleanly, same shape as EPFO's digital-PDF precedent —
  no dedicated structuring script needed this time). 65/65 questions extracted with clean
  `question_number`s 1-65, all mapped to one of the 8 already-registered `phase1_p1` topics
  (0 questions flagged; 7 whole *chunks* — cover/instruction pages, not questions — flagged
  "no registered topic matched," a real but harmless retrieval-embedding gap, BUG-09's
  independent-failure-mode design already handles this). Answer key was ALSO real digital
  text (not scanned) — wrote `scripts/extract_answer_key_digital.py` (pure `pdfplumber` +
  regex, zero LLM at all, stricter than DECIDE-27 requires) instead of reusing the
  scanned-key/Haiku-vision `scripts/extract_answer_key.py`; merged via the existing
  `scripts/merge_answer_key.py` unmodified (DECIDE-27's mechanical-merge-only path). Result:
  **65/65 verified, 0 unverified, 0 void** — a full real key existed for every question, a
  first for this platform. One real chunk-boundary extraction gap found (BUG-13/14's known
  class): Q55's options split across a page break, only 2 of 4 extracted automatically;
  manually patched from the same source PDF page already visually verified during this
  session's own read-before-building step (literal transcription of real printed text, not
  an LLM guess — the row's `correct_option='C'` was already correct from the mechanical
  merge, only the `options` array was incomplete). `scripts/migrate_012_recompute_rbi_depr_
  phase1p1_weight.py` recomputed `phase1_p1`'s `exam_topics.weight` from this real data
  (DECIDE-31's Q2 recency-decay formula, `0.9^years_ago`; all 2025 so decay=0.9 flat):
  `depr_quant_methods_econ` 1.0→14.4, `intl_econ` 1.0→9.0, `macro`/`growth` 1.0→8.1 each,
  `micro`/`pub_finance` 1.0→6.3 each, `indian_econ` 1.0→4.5, `env_econ` 1.0→1.8 — real
  first signal for this exam's Phase I Paper 1, no longer a flat placeholder. Real API cost:
  ~$0.10 (Haiku 4.5, 8131 input + 13369 output + 9206 cache-write + 110472 cache-read
  tokens — one 14pp paper, cents not dollars, per the cost-consciousness ask). Set-2/Set-3
  question PDFs deliberately NOT touched — no matching answer key exists anywhere for either,
  per this session's explicit scope. Tests: `tests/test_extract_answer_key_digital.py` (8
  new, pure parser function, no I/O), `tests/test_migrate_012.py` (4 new, throwaway-sqlite
  pattern) — 70 pre-existing + 12 new = 82/82 passing.
- **Built real per-user coverage (DECIDE-34, 2026-09-16, external session):** the original
  plan assumed `coverage_depth` could be joined from Recall's (Devthorium's) attempt logs.
  Verified against Recall's live code/DB first (not just nyaya-core's own notes) — Recall
  has zero PFRDA/EPFO content: `data/upsc.db`'s `topic_weights.exam_source` only has
  `rbi_grade_b`/`upsc_prelims`, `pyq_questions` has no exam-scoping column at all, no file
  anywhere in Devthorium references nyaya-core/core.db/pfrda/epfo. Nothing to join. Built
  it directly on nyaya-core instead: `scripts/migrate_011_user_attempts_coverage.py` adds
  `user_attempts` (attempt log) and `topic_coverage` (computed per exam_id+topic_id:
  attempts_count/accuracy/coverage_depth — no row for an untested topic, never a row of
  zeros). `scripts/quiz.py` is a new interactive CLI: `.venv/bin/python scripts/quiz.py
  --exam_id pfrda_gradea [--paper_id ID] [--topic_id ID] [--n 10]` — pulls real quizzable
  `pyq_bank` questions (verified/unverified-but-void-excluded, real `correct_option`, real
  `topic_id`), orders them by `daily_priority.py`'s own real ranking (reused, not
  reimplemented), grades each answer immediately, logs to `user_attempts`, and recomputes
  `topic_coverage` for every topic touched from ALL historical attempts (not just that
  session's) using the layered-coverage skill's Q3 depth rule (accuracy >= 75% -> 1.0;
  45-74% -> accuracy; < 45% -> accuracy * 0.5). `daily_priority.py`'s
  `fetch_coverage_depth()` now reads real `topic_coverage` rows, falling back to 0.0 for
  untested topics (unchanged correctness) — its printed/written coverage note and
  uncovered/at-risk counts now describe this real mixed state instead of claiming zero
  coverage everywhere. Real surprise found running the demo: `exam_topics` carries both
  parent topics (e.g. `pfrda_costing`, a rollup) and child subtopics (e.g.
  `pfrda_cost_control_analysis`) as independent weighted rows, and real PYQ tagging lands at
  whichever granularity DECIDE-31's structuring pass produced — `quiz.py`/`topic_coverage`
  key off whatever `topic_id` a question actually carries, so no design change was needed.
  Demo run (3 right/2 wrong across `pfrda_companies_act`/`pfrda_economics_basic`) confirmed
  `topic_coverage` populates correctly and `daily_priority.py`'s ranking shifts accordingly
  (`pfrda_companies_act`: rank 2 -> rank 9, priority_score 32.10 -> 10.70); demo rows deleted
  immediately after — `user_attempts`/`topic_coverage` are empty again, never mistake this
  for real progress. Tests: `tests/test_migrate_011.py` (5 new), `tests/test_quiz.py` (10
  new), `tests/test_daily_priority.py` (+4 for the real-coverage wiring) — 51 pre-existing +
  19 new = 70/70 passing. Branch `feature/coverage-loop` (built on top of
  `feature/daily-priority`), not merged to main yet. Full detail: `docs/decisions.md#decide-34`.
- **Built `scripts/daily_priority.py`** (2026-09-16): CLI implementing the `layered-coverage`
  skill's Q4 formula (`priority = weight * (1 - coverage_depth)`) against real
  `exam_topics.weight` data. Run: `.venv/bin/python scripts/daily_priority.py [--exam_id
  pfrda_gradea] [--paper_id ID] [--top 15]` — prints a ranked table per real paper_id
  (General/Research/common streams labeled separately for `pfrda_gradea`) and writes
  `docs/daily_priority_<exam_id>.md` (overwritten each run). `coverage_depth` is hardcoded
  to 0.0 for every item — confirmed against the live schema that nyaya-core has no per-user
  attempt/accuracy table (that lives in Recall/Scribe's own DBs) — so today it ranks purely
  by weight; the Research stream's flat 1.0 placeholder weights make its ranking meaningless
  and the script says so in its own output. Tests: `tests/test_daily_priority.py` (10 new,
  51/51 total passing). Branch `feature/daily-priority`, not merged to main yet.
- **PFRDA Research stream still has zero real content and — per RESEARCH-11 — likely never
  will from a coaching-site source** (checked 6 major sites, none cover it; ~2 vacancies
  nationally is the likely reason). `phase1_p2_research`/`phase2_p2_research` weights stay
  DECIDE-30's flat 1.0 placeholder (RISK-07 only resolved for General stream). If Rahul ever
  finds/creates real Research-stream content, revisit the PFRDA↔DSIM notes-only links first.
- `eco_optional_1`/`eco_optional_2` and the new `rbi_depr`/`rbi_dsim` topics are ALL flat 1.0
  placeholder weights (except DEPR's two real 0.5/0.5 "equal weightage" splits) — no real PYQ
  content has been ingested for any of them yet, same placeholder-until-real-content pattern
  as PFRDA's own history.
- 7 PFRDA questions/labels across the 3 ingested years fell back to a parent-level topic_id
  because no subtopic in the fixed taxonomy fit well (see the structuring agents' notes in
  `data/raw_ingest_staging/pfrda/*_structured.json`) — worth a look if that taxonomy gets
  refined further.
- Phase 2 (hybrid retrieval + API) is still the bigger unbuilt phase generally — this session
  didn't touch it; better sequenced after more real content exists across more exams.

**Also worth doing when picking this up again:** the same session that produced DECIDE-30
found nyaya-core's `exam_topics.weight` column isn't cross-exam-comparable (raw sums range
10.47–451 across exams) and that only one cluster (CSE+4 State PCS) actually shares canonical
topic_ids — IES/RBI/EPFO/PFRDA each have separate, unlinked vocabularies even where they
conceptually overlap (e.g. three separate "IS-LM"-type rows). A normalized-weight view and
real canonical-topic linking across these four are the real unbuilt tasks behind treating
"which topic serves the most exams" as a live query instead of manual reasoning — not done
this session, deliberately sequenced after real PFRDA/EPFO content exists to link against.

**DECIDE-27/28/29 (S8) landed and paid off immediately: 6 real EPFO paper-instances (5 GAT
years + 2023 GS) now verified against real official answer keys, 608 total verified
questions, 0 ever guessed by an LLM.** Schema has `question_number`, `status`
(unverified/verified/void), `source_file` + `answer_key_file` (DECIDE-28 — every row
traceable to its exact source). `scripts/extract_answer_key.py` transcribes a scanned
official key PDF (per-series, Haiku vision — literal transcription, never judgment);
`scripts/merge_answer_key.py` merges one series' answers into `pyq_bank` by
`question_number`, zero LLM.

**Per-paper result (all against real, visually-verified official UPSC answer keys):**
| Year | Paper | Verified | Void (UPSC-dropped) | Unverified/no-number |
|---|---|---|---|---|
| 2012 | APFC GAT (Series D) | 85 | 1 | 4 |
| 2016 | APFC GAT (Series A) | 87 | 0 | 3 |
| 2017 | EO/AO GAT (Series A) | 110 | 0 | 0 |
| 2021 | EPFO GAT (Series A) | 98 | 1 | 7 |
| 2023 | EO/AO GAT (Series A) | 114 | 0 | 0 |
| 2023 | APFC GS (Series A) | 114 | 0 | 0 (6 never extracted) |

Each shortfall from 120 is a real, understood, non-silent gap — mostly a handful of
chunk-boundary/malformed-option extraction misses (BUG-13/14) — never a guessed answer
standing in for a real one.

**Taxonomy fixed (DECIDE-29), unblocking the GS paper:** Rahul reviewed the topic taxonomy
before letting GS ingest and flagged that 6 of 25 topics were reused UPSC-Prelims-style
canonical rows (`polity`/`economy`/`current_affairs`/`history_amac`/`modern_history`/
`reading_comprehension`) with real depth/scope mismatches — EPFO's actual coverage isn't
"exactly similar" to UPSC Prelims'. Replaced with 8 fresh EPFO-specific topics sourced from
the real UPSC EPFO 2026 notification's Appendix-I syllabus (`~/Desktop/opportunities/govt
notifications/epfo 2026 notification.pdf`, page 22) — not invented. This also added the
previously-missing `epfo_quant_stats_mental_ability` topic (RISK-05's real cause) and, as a
side effect of recomputing weights from real 546-question frequency, resolved RISK-04. The
GS paper ingested cleanly right after (only 3/16 chunks flagged) — a direct, measurable
payoff of the fresh taxonomy.

**Still open, real work, no particular order:**
- **RISK-05, remainder:** the topic now exists, but the specific 6 flagged 2023 GAT
  questions (Q115-120) and possibly similar content in other years weren't re-processed
  against it — worth a targeted re-run once there's time, not urgent.
- **2025 paper: still NOT re-verified with a real key.** The `.numbers` "Solved Answer Key"
  in `pyqs_formatted(notebooklm)/` is NotebookLM-generated (Rahul confirmed: "the answers
  are llm generated so can't be trusted, i need to verify answers yet") — never merge it.
  The 36 existing 2025 rows are `unverified` (BUG-12 — they were Haiku's own guesses). A
  cleaner **digital, English-only NotebookLM-retyped 2025 paper** exists in that same folder
  (`...APFC & EO/AO Exam 2025...`) — re-ingest from that instead of the original bilingual
  scan already in `raw_ingest_staging/` (same fix 2023 GAT/GS got this session), then merge
  a real key once Rahul sources one himself.
- Fix BUG-13's root cause in `chunk_document()` itself (the persist-time dedup added this
  session is a safety net, not a fix to the chunk-boundary overlap).
- A few individual items are flagged for manual review, not silently merged: 2017's Q51 and
  2023 GS's Q40/Q71 (key says a letter but too few options were extracted — real extraction
  defects), see `data/flagged_chunks.jsonl` and the merge-script warnings in session log.
- Consider the same taxonomy-freshness review (DECIDE-29's question) for any other exam that
  reuses canonical topics via `exam_topics` — IES/RBI's imports were real per-exam
  taxonomies from the start so likely fine, but worth a deliberate check, not an assumption.

**Also open, no blockers left on the DB side:** `upsc_cse`'s Optional papers are now
correctly split into Paper I/II (`eco_optional_1`/`eco_optional_2`, `law_optional_1`/
`law_optional_2` — DECIDE-25, `scripts/migrate_004_split_optional_papers.py`, already run).
**None of the 4 have a seeded topic taxonomy yet** — that's the real remaining blocker
before any Eco/Law Optional content can be ingested (`enrich.load_topics()` will hard-raise
otherwise). If Rahul sources a real Economics/Law Optional syllabus for either paper, seed
it via `scripts/seed_topics.py`'s existing pattern before attempting ingestion.

Phase 1 (ingestion) is validated end-to-end against real content, now with real verified
answers too. 9 exams registered, 8 with a seeded topic taxonomy (only `rbi_depr` and
`upsc_cse`'s 4 Optional papers have none). Real next actions, no particular order:
- Otherwise, run `scripts/ingest.py` for real against actual content for any of the other 7
  seeded exams.
- When ready to build the PYQ-explanation batch-generation script: it must validate against
  `PYQExplanation` before writing (partial response = `ReviewNeededError`, never a silent
  partial write) and ground explanations in real retrieved chunks — both are direct fixes
  for BUG-04, not optional nice-to-haves. Now unblocked in principle for any question with
  `status='verified'`, since a trustworthy `correct_option` is a prerequisite for this.
- Phase 2 (hybrid retrieval + API) is the bigger remaining phase — better sequenced after
  more real content is ingested to retrieve against.

## Session narrative (2026-09-12, S8)
Rahul asked for a plan for how to proceed without correct answer keys (he'll feed real ones
later, standing rule: no question ever solved by the LLM). Answered with a split plan (what's
unblocked vs. hard-blocked); he confirmed proceeding now with "capture now, verify later."

Investigated `~/Desktop/UPSC/epfo_apfc_eo_ao/` (Rahul pointed me there) and found real
official answer keys already on disk for 5 EPFO years (2012/2016/2017/2021/2023) — visually
confirmed genuine UPSC scans (exam code, Series letter, dropped-item count), not the
NotebookLM "Solved Answer Key" for 2025 which Rahul separately flagged as untrustworthy
("the answers are llm generated so can't be trusted, i need to verify answers yet").

Built DECIDE-27 (see decisions.md): schema gets `question_number` + `status`
(unverified/verified/void), `correct_option` only ever set by a real key merge, never by
Haiku. Found BUG-12 while doing this — the 36 existing 2025 rows had `correct_option` filled
by Haiku's own guess (the original prompt asked for it), not real data; reset to unverified.
Also fixed a crash (a null entry inside an extracted `options` array took down a whole
ingestion run) — now a per-item flagged failure instead.

Built `scripts/extract_answer_key.py` (Haiku vision transcribes a scanned key PDF page —
literal reading, never asked to judge correctness) and `scripts/merge_answer_key.py` (pure
data join by `question_number`). First extraction attempt merged all 4 series together and
produced ~100 false conflicts — the key PDFs put one full series per page (A/B/C/D), not one
shared grid; fixed to key results by series and pick the one matching the question paper's
own printed series.

Ingested the 2023 EO/AO GAT paper as proof. First attempt (raw bilingual scan) produced 190
rows for a 120-question paper — the paper interleaves Hindi and English pages for Part B,
and nothing stripped the Hindi ones, so many questions got extracted twice (BUG-13, partly).
Killed it, cleaned up (`pyq_bank`/`sections`/LanceDB rows for that doc), and Rahul redirected
me to `pyqs_formatted(notebooklm)/` — clean, digital-text, English-only NotebookLM-retyped
versions of several papers already exist there (2023 EO/AO GAT, 2023 APFC GS, and 2025)
rather than needing OCR on the raw scans at all. Re-ingested from that file: 114/120
questions extracted cleanly (6 missing — no `quantitative_aptitude` topic seeded yet, RISK-05
— and 5 small chunk-boundary duplicates, BUG-13, manually deduped). Merged the real Series A
key: **114/114 verified against the real official answer, 0 guessed.**

Logged DECIDE-27, BUG-12, BUG-13, RISK-05 in the audit docs.

**Continued same session:** Rahul asked to proceed with the remaining 4 years, adding a
standing instruction to always track exact source files so a bad source can be found and
fixed later. Added DECIDE-28: `pyq_bank.source_file` + `answer_key_file` columns, threaded
through `enrich_chunk`/`build_pyqs`/`persist_pyq`, backfilled for the two already-ingested
docs via `scripts/migrate_006_source_provenance.py`. While doing this, turned BUG-13's
manual-dedup workaround into a real fix: `persist_pyq` now checks for an existing
`(exam_id, paper_id, year, question_number)` before inserting and skips true duplicates
(can't rely on `ON CONFLICT(question_id)` since a chunk-boundary duplicate gets a different
chunk-derived id) — added 3 tests locking this in.

Ingested 2016/2017/2021 (all bilingual scans, same `extract_english_pages.py` treatment as
2023) and 2012 (English-only but its coaching-compiled PDF's first pages are text-heavy
while its real content pages are image-only — `get_page_text_quality`'s first-3-pages sample
got fooled into picking `digital_pdf` when it needed `scanned_pdf`; added a `--parser`
override flag to `ingest.py` rather than patch this one file around the heuristic, since the
same false-positive could hit a future coaching-compiled PDF). Hit and fixed BUG-14 mid-batch
on 2017: a chunk packed with dense MCQs produced a response Haiku cut off mid-string, and
the unguarded `json.loads` crashed the entire run — raised `max_tokens` to 4096 and made a
parse failure a flagged per-chunk failure instead of fatal. Also fixed a validation bug in
`merge_answer_key.py`: a dropped item's "X" placeholder was rejected by the A/B/C/D letter
check before the dropped-item exemption ever got a chance to apply (hit on 2021's real
dropped Q71).

Merged all 4 real keys (2012 Series D, others Series A — each visually confirmed to match
its own question paper's printed series). 494 real verified questions across 5 GAT years,
plus 2 real UPSC-dropped items correctly marked `void`, zero ever guessed by an LLM.

**Continued further same session:** before letting the 2023 APFC General Studies paper
ingest, Rahul reviewed the topic taxonomy and rejected reusing `upsc_prelims_gs`'s topics —
"curate fresh taxonomy for epfo_apfc_eo_ao exams, topics are not exactly similar to
upsc_prelims syllabus." Investigating found the real problem was more specific than "similar
to prelims": 6 of the 25 already-seeded topics (`polity`, `economy`, `current_affairs`,
`history_amac`, `modern_history`, `reading_comprehension`) were the exact same shared
canonical rows `upsc_cse`/State PCS use (DECIDE-19's reuse mechanism, applied here without
enough scrutiny) — `reading_comprehension` was even parented under `comprehension` ->
`csat`, a UPSC-CSE-Paper-2-only concept EPFO doesn't have at all. Found the real official
syllabus in `~/Desktop/opportunities/govt notifications/epfo 2026 notification.pdf`'s
Appendix-I (9 real subjects, not invented) and built DECIDE-29 from it: 8 new EPFO-scoped
topics, `migrate_007_epfo_fresh_taxonomy.py` retagging all 228 affected `pyq_bank` rows + 53
chunk rows, unlinking the old shared `exam_topics` rows (canonical topics themselves
untouched for their real owners), and recomputing every weight from real 546-question
frequency (a bonus real fix for RISK-04). This also added the syllabus's missing "Elementary
Mathematics, Statistics and General Mental Ability" subject, resolving RISK-05's root cause.

Registered the `gs` paper_id, ingested the 2023 APFC GS paper (clean NotebookLM digital PDF,
same reasoning as the GAT papers) — 114/120 extracted cleanly, only 3/16 chunks flagged, a
sharp improvement directly attributable to the fresh taxonomy. Merged its real Series A key:
**114/114 verified.**

**Session final: 608 real verified questions across 6 paper-instances (5 GAT years + 2023
GS), zero ever guessed by an LLM.** 2025's re-verification is the one piece intentionally
left open — waiting on Rahul for a real, non-LLM key.

## Session narrative (2026-09-10, S7)
Rahul asked where the project stood; asked how many of the 2025 paper's 120 real questions
are actually in the DB right now. Queried `data/core.db` directly rather than trust the
prior session's prose: **36**, confirmed. Investigated `data/flagged_chunks.jsonl` to
explain the gap — found it's append-only across all 7 of S5's debug attempts (not reset
between them), so an exact single-run count isn't cleanly recoverable from it alone, but
the shape is clear: ~70 questions flagged for missing `correct_option` (no answer key in
the raw booklet), 11 chunks (multiple questions each) dropped entirely for no topic match.
Also found flagged entries store only `{file, chunk_index, reason}` — not the actual
question text — and that `ingestion_log.json` already has this file's hash marked done, so
a plain re-run will silently skip it rather than retry the flagged content.

Rahul rejected the flag-and-continue pattern outright: EPFO only has 6-7 real past papers
in total, so losing 70% of one paper's questions is a real usability problem, not an
acceptable trade-off. He's going to source a real answer key himself, then wants a rebuild
that gets all 120 — and set a general standing instruction: flag problems early and solve
them, don't skip or work around them, because a flagged problem is always solvable but a
skipped one silently erodes completeness. Logged as **DECIDE-26** (supersedes DECIDE-15's
sampled-verification assumption for this specific scarce-content case). Updated "Exact
next step" with the concrete pre-requisites for the next real run (`--force` reprocessing
path, an actual answer-key-matching design, and diagnosing the 11 dropped chunks by
re-extracting OCR text for their source pages) rather than just re-stating the old command.
Nothing coded yet — waiting on Rahul to source the key before designing the matching
mechanism against its real format.

## Session narrative (2026-09-09, S6)
Rahul asked for a status/estimate ("what's complete, what's left, how long till the model's
done") — answered with the Phase 0-6 breakdown from `PLAN.md` (Phase 0+1 done and validated;
Phase 2 hybrid retrieval+API next, ~2-3 sessions; Phase 3 Recall cutover, Phase 4 Scribe
sync). Discussed sequencing new ingestion (IES/more EPFO years/CSE Prelims are ready now;
Mains GS/Eco Optional are blocked on missing topic taxonomies) and flagged that all real
ingestion so far has been PYQ-only — the chunker's section-splitting/auto-merging path
(a Phase 2 dependency) has never been tested against real prose content.

Rahul said he has the EPFO papers now and is downloading answer keys, will NotebookLM them
into docx. Separately confirmed Eco Optional/Eco Opt naming was already resolved in a past
session (DECIDE-16→DECIDE-21) — I had wrongly told him it was still open by quoting a stale
`PLAN.md` note without checking `decisions.md`'s own status field (**BUG-11**, fixed: both
docs corrected).

Rahul then caught a real second gap: every UPSC Optional subject is 2 compulsory
papers/year with disjoint syllabi, but `eco_optional`/`law_optional` had each been left as
ONE paper row when `mains_gs` was correctly split into gs1-gs4 for the identical reason
back in DECIDE-21. Fixed as **DECIDE-25**: split into `eco_optional_1`/`_2`,
`law_optional_1`/`_2` (his chosen `_1`/`_2` naming) via
`scripts/migrate_004_split_optional_papers.py` — zero dependent data existed, clean split.
`scripts/init_db.py` updated for fresh clones. No topics seeded for any of the 4 yet.

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

Then ran the platform's first-ever real (non-synthetic) ingestion — the actual 2025 paper,
after building `scripts/extract_english_pages.py` to drop the bilingual booklet's Hindi/
blank/instruction pages (stopword-density heuristic; a naive ASCII-token-count first
attempt was wrong — Tesseract's eng model produces plenty of ASCII-alphabetic garbage off
Devanagari script, verified empirically before trusting the fix). Real content immediately
surfaced 6 real bugs, found and fixed one at a time across 7 ingestion attempts:
**BUG-05** (`sections.topic_id` FK pointed at a table dropped by an old migration —
migrate_002's rename didn't propagate to a table created before it ran), **BUG-06**
(`ingest.py` never called `load_dotenv()`, only worked before via manual shell export),
**BUG-07** (assumed ≤1 PYQ per chunk, crashed on real dense-MCQ content — Haiku returned a
list, code expected an object), **BUG-08** (PYQ `year` never backfilled from
`--published-date` — >half of one run's flags were this alone), **BUG-09** (one invalid
question discarded its valid siblings in the same chunk — confirmed one real chunk lost 6
good questions to 1 bad one — and `topic_id` was chunk-level not question-level, wrong for
content with no section headers to key off), **BUG-10** (a failed chunk-level topic
classification still discarded valid per-question classifications inside it — same
reasoning as BUG-09, one layer up, found by explicitly asking "does this same argument
apply anywhere else").

**Final real yield: 36 verified questions in `pyq_bank`, across 14 distinct correctly
per-question-tagged topics** (up from 0; General Science 6, Accountancy 6, Computer
Applications 5, History 4, 2 different Labour Acts, Insurance 2, Auditing 2, Polity 2, plus
English/Economy singles) — real, not synthetic, proof the per-question topic-tagging fix
works (previously every question in a chunk would have inherited one shared topic). Total
Haiku cost across all 7 attempts (including every crashed/debugging run): ~40-45 cents.
Remaining ~95 flagged questions per full run are now understood to be mostly the real
answer-key gap (this raw booklet has no key; most domain-knowledge MCQs aren't
independently verifiable by an LLM), not a pipeline defect — see RISK-04 and the "Exact
next step" above for what that implies for future ingestion of more years' content.

Rahul also asked several concept-level questions this session (why a verified answer
matters at all for a "just questions" bank, how Haiku arrives at answers without a key, why
chunking/"clubbing" happens and what it trades off) — answered in-conversation, not
re-logged here since they're conceptual, not decisions, but they're what directly motivated
BUG-09/BUG-10's discovery: tracing "why does clubbing lose quality" led straight to both
bugs. Committed and pushed: `7738bea` on `origin/main`.

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
