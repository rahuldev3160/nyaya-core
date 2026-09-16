# Risks

### RISK-01 — Scribe freshness lags behind ingestion {#risk-01}
**Date:** 2026-09-04 | **Session:** S1 | **Status:** Open

**Risk:** Because Scribe consumes via batch sync (DECIDE-03), newly ingested content is
only reflected in Scribe after the sync script is re-run — not automatically, unlike Recall
which queries live.
**Mitigation:** Make the sync script trivially re-runnable (one command, idempotent,
incremental). Document this clearly so it's an expected workflow step, not a surprise.
**Escalation trigger:** If Rahul finds himself forgetting to re-sync and hitting stale
grounding regularly, revisit DECIDE-03 (e.g. a scheduled local cron that syncs + a git-push
of the exported snapshot, or exposing the API after all).

### RISK-03 — LanceDB's concurrency model won't hold at multi-user scale {#risk-03}
**Date:** 2026-09-04 | **Session:** S2 | **Status:** Open, deferred

**Risk:** LanceDB is reliable for a single local writer + single-machine reader (Rahul's
current setup) but has known limitations under concurrent multi-writer load — not built for
high-concurrency production use (RESEARCH-01).
**Mitigation:** None needed now — out of scope for personal use. When "publish it later"
becomes real, revisit the vector store choice (Qdrant, pgvector, or LanceDB Cloud are the
likely candidates) before opening this platform to concurrent users.
**Escalation trigger:** Any plan to onboard a second real user.

### RISK-04 — `upsc_epfo_apfc_eo_ao` topic weights seeded from a single verified year {#risk-04}
**Date:** 2026-09-09 | **Session:** S5 | **Status:** Resolved 2026-09-12 (S8, DECIDE-29) —
`migrate_007_epfo_fresh_taxonomy.py` recomputed every `exam_topics.weight` for this exam
from real observed frequency across 546 questions spanning all 5 ingested GAT years.

**Risk:** `exam_topics.weight` for this exam was seeded from RESEARCH-10's real 2025 paper —
a genuine improvement over coaching-site guesses (RESEARCH-09), but still only one data
point. RESEARCH-09 independently confirmed real year-to-year volatility in this exam's
subject weightage (e.g. Labour Codes swung from an estimated 6 to a confirmed 15). A single
year's weight risks being treated as stable ground truth when it may not be.
**Mitigation:** Documented as an explicit caveat in `data/syllabi/upsc_epfo_apfc_eo_ao.json`'s
`_source_note` (DECIDE-24) rather than silently presented as final. The real fix is
recomputing `exam_topics.weight` from actual ingested `pyq_bank` topic-tag frequency once
more real years exist — not a schema change now, just a scripted recompute later.
**Escalation trigger:** As soon as a second real year of this exam's content is ingested
(Rahul is actively sourcing more — 2023 flagged as highest priority in-session), recompute
weights from real multi-year data before treating them as reliable for practice
prioritization.

### RISK-02 — Old Chroma metadata too sparse for direct migration {#risk-02}
**Date:** 2026-09-04 | **Session:** S1 | **Status:** Open

**Risk:** Recall's existing ChromaDB chunks carry only `subject_id`/`source_file`/`parser`/
`file_path`/`chunk_index` — no page numbers, no topic_id, no content_type, no provenance.
A straight copy into the new schema would leave most new fields null.
**Mitigation:** Phase 3 re-ingests from the original source files through the new pipeline
(re-chunk, re-embed, re-label) rather than migrating the old vector store directly. Slower
but produces complete, correctly-typed rows.

### RISK-05 — `upsc_epfo_apfc_eo_ao` has no quantitative-aptitude topic {#risk-05}
**Date:** 2026-09-12 | **Session:** S8 | **Status:** Partially resolved same session
(DECIDE-29 added `epfo_quant_stats_mental_ability`) — the specific 6 flagged 2023 GAT
questions (Q115-120) and any other content silently lost to this gap across the other 4
years still need re-processing now that the topic exists; not yet done.

**Risk:** The 2023 EO/AO GAT paper's questions 115-120 (speed/distance, ages, coding-
decoding, averages, probability — real quantitative aptitude content) extracted zero PYQs:
`enrich.load_topics()`'s valid set (seeded from the 2025 paper's 14 topics) has no matching
topic, so Haiku correctly returned `topic_id: null` rather than force a bad match, and those
6 questions were flagged, not persisted. The 2025 paper apparently didn't include this
subject, so the gap wasn't visible until a second year was ingested.
**Mitigation:** Add a `quantitative_aptitude`/`numerical_ability` topic (or a small set of
sub-topics) to `exam_topics` for `upsc_epfo_apfc_eo_ao` before re-attempting these 6
questions — a `scripts/seed_topics.py` addition, not a schema change. Check other ingested
years for the same subject once the topic exists, in case any of them lost content to the
same gap silently before this was noticed.

### RISK-07 — PFRDA Paper-2 topic weights are honest placeholders, not real {#risk-07}
**Date:** 2026-09-15/16 | **Session:** external (Mission 2027) | **Status:** PARTIALLY RESOLVED 2026-09-16 (DECIDE-31)

**Risk:** DECIDE-30 seeded all 23 General/Research Paper-2 topics at a flat weight of 1.0 —
no real per-subject frequency exists (the 3 real PFRDA paper-books on disk haven't been
ingested). Any tooling that treats these weights as real priority signal will be wrong.
**Mitigation:** Ingest the 3 real paper-books (`~/Desktop/PFRDA/*.pdf`, 2021/2022/2025) and
recompute weights from observed frequency, same pattern as DECIDE-29's EPFO fix for RISK-04.
**Resolution (General stream only):** DECIDE-31 ingested all 3 books (454 real MCQs) and
recomputed `exam_topics.weight` for the 7 tested General-stream subjects + their 50 new
subtopics, and for Phase-1-Paper-1's 4 aptitude sections + their 42 new subtopics, as a real
recency-decayed frequency count. **Still open for Research stream** — none of the 3 books
contain Research-stream content, so `phase1_p2_research`/`phase2_p2_research` still carry
the original flat 1.0 placeholder; needs a real Research-stream paper-book to resolve.
**Escalation trigger:** Before any PFRDA Research-stream feature ships using these weights
as if they were real.

### RISK-08 — PFRDA Budget/Economic-Survey cross-link deferred, not decided {#risk-08}
**Date:** 2026-09-15/16 | **Session:** external (Mission 2027) | **Status:** Open

**Risk:** DECIDE-30 rejected cross-linking `pfrda_budget_economic_survey` to the canonical
Indian-Economy/current-affairs topic in a rushed pass, but flagged it as a plausible real
match worth revisiting — leaving it un-cross-linked means a future cross-exam overlap query
will undercount how much this topic actually serves Rahul's broader prep.
**Mitigation:** Revisit with a real depth/scope comparison (same method DECIDE-29 used)
before the next PFRDA-related session closes.
**Escalation trigger:** None urgent — low cost either way until cross-exam topic linking
(the real unbuilt task named in DECIDE-19/RESEARCH-06) is actually built.
