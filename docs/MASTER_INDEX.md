# Master Index — Nyaya Core

Pointer catalogue. One line per artefact. Full entries live in the linked files.

## Audits
- [AUDIT-001](AUDIT-001-architecture-review.md) — Architecture review vs. Rahul's 6 stated criteria (universal/navigable, retrieval size, extensible indexing, vector reliability, latency, hallucination). 3 open questions (Q1-Q3) pending his decision.

## Decisions
- [DECIDE-01](decisions.md#decide-01) — New standalone repo, not built inside Recall or Scribe
- [DECIDE-02](decisions.md#decide-02) — Recall's ChromaDB pipeline replaced outright, not run in parallel
- [DECIDE-03](decisions.md#decide-03) — Scribe consumes via batch export/sync, not a live API call
- [DECIDE-04](decisions.md#decide-04) — `topic_id` is a shared FK across chunks and pyq_bank, not free text
- [DECIDE-05](decisions.md#decide-05) — LanceDB over ChromaDB for native hybrid search
- [DECIDE-06](decisions.md#decide-06) — Ollama `nomic-embed-text` over Recall's sentence-transformers
- [DECIDE-07](decisions.md#decide-07) — Recency signal added to ranking for time-sensitive content types
- [DECIDE-08](decisions.md#decide-08) — Retrieval budget is caller-supplied, never hardcoded; never truncate mid-chunk
- [DECIDE-09](decisions.md#decide-09) — Extensible tagging via JSON field + EAV side table, not schema migration
- [DECIDE-10](decisions.md#decide-10) — Score floor + explicit "insufficient grounding" signal, no silent hallucination fallback
- [DECIDE-11](decisions.md#decide-11) — `is_current`/`superseded_by` hard flag for time-sensitive content
- [DECIDE-12](decisions.md#decide-12) — Browse endpoints (`/topics`, `/papers` by exam) added to API

- [DECIDE-13](decisions.md#decide-13) — Adopt Contextual Retrieval (Q1: yes)
- [DECIDE-14](decisions.md#decide-14) — Adopt parent-document/auto-merging retrieval from Phase 2 (Q2: yes)
- [DECIDE-15](decisions.md#decide-15) — Citation verification sampled, high-stakes only (Q3)
- [DECIDE-16](decisions.md#decide-16) — `upsc_eco_opt`/`upsc_eco_optional` confirmed same exam; renamed to `upsc_eco_optional` for consistency with `upsc_law_optional` (closed)
- [DECIDE-17](decisions.md#decide-17) — `exam_id` is ingestion-run-scoped (caller-supplied), never Haiku-classified per chunk
- [DECIDE-18](decisions.md#decide-18) — `topics` seeded from Devthorium's real syllabus.json (271 rows, upsc_prelims_gs only), not Haiku-invented strings; other 7 exams still unseeded (superseded in part by DECIDE-19 — IES/RBI already have real taxonomies elsewhere)
- [DECIDE-19](decisions.md#decide-19) — `topics` made exam-agnostic + `exam_topics` junction table added, resolving DECIDE-32 (pending since 2026-06); real precedent researched (O*NET crosswalks, RAG taxonomy practice)
- [DECIDE-20](decisions.md#decide-20) — 4 State PCS exams registered (uppcs/hpas/ukpsc/mppsc) per confirmed feasibility; `seed_topics.py` extended for reuse-plus-new-branch; "polity" etc. now shared across 5 exams via exam_topics, not duplicated
- [DECIDE-21](decisions.md#decide-21) — Finalized exam_id/paper_id naming (institution_exam, paper scoped by composite key); restructured Essay/Ethics/GS/Optionals from separate exams into `upsc_cse` papers; IES/RBI real taxonomies imported
- [DECIDE-22](decisions.md#decide-22) — Added `institutions` table + `exams.institution_id` FK — real join target for "institution," not just an unqueryable exam_id string prefix; naming grammar itself stays documentation, not data
- [DECIDE-23](decisions.md#decide-23) — `pyq_explanations` schema designed against Recall's real BUG-04 failure: format-aware (statement-based vs standalone), validated discriminated union, elimination-strategy field, grounding citations; generation script itself deferred (on-demand batch job)
- [DECIDE-24](decisions.md#decide-24) — Registered `upsc_epfo_apfc_eo_ao` (one exam, not two); real per-subject weights from RESEARCH-10 seeded via a backward-compatible `seed_topics.py` extension (`reused_topics` can now carry a weight, not just an id)
- [DECIDE-25](decisions.md#decide-25) — Split `eco_optional`/`law_optional` into Paper I/II (`_1`/`_2`) — each UPSC Optional is 2 papers/year with disjoint syllabi, same gap DECIDE-21 already fixed for mains_gs; zero dependent data, clean split via `migrate_004_split_optional_papers.py`

## Bugs
- [BUG-01](bugs.md#bug-01) — Scribe's `generate_answers.py` truncates grounding chunks to 400 chars (found, not yet fixed — scheduled for Phase 4)
- [BUG-02](bugs.md#bug-02) — Ported parsers discarded page boundaries, breaking `page_number`/`sections.page_start/end` (found and fixed same session, before any consumer existed)
- [BUG-03](bugs.md#bug-03) — `\b(19|20)\d{2}\b` never matched a year after `_` (e.g. "report_2023") — `\b` doesn't fire between two word chars; fixed with a digit-lookaround, caught by a unit test
- [BUG-04](bugs.md#bug-04) — Recall's PYQ explanation feature: 100% of wrong-option fields silently empty (statement-based MCQ schema mismatch, unvalidated LLM output) — informs `pyq_explanations` design, not a bug in this repo
- [BUG-05](bugs.md#bug-05) — `sections.topic_id` FK pointed at `topics_old` (dropped by migrate_002) since S4 — invisible until the first real (non-synthetic) ingestion run; fixed via `migrate_004_fix_sections_topic_fk.py`, zero data loss
- [BUG-06](bugs.md#bug-06) — `ingest.py` never called `load_dotenv()` despite `.env` existing since S4; API key only worked when manually exported in-shell — fixed, cost nothing (failed before any request was sent)
- [BUG-07](bugs.md#bug-07) — `enrich_chunk` assumed ≤1 PYQ per chunk; crashed on a real dense-MCQ chunk (Haiku returned a list, code expected an object) — contract changed to always-a-list (`pyqs`), `build_pyqs` returns `list[PYQQuestion]`, 20/20 tests passing
- [BUG-08](bugs.md#bug-08) — PYQ `year` never backfilled from `--published-date`; 17 of 33 real flagged chunks were this alone — fixed, `build_pyqs` now falls back to the caller-supplied date
- [BUG-09](bugs.md#bug-09) — one bad question discarded valid siblings in the same chunk (confirmed: one real chunk lost 6 good questions to 1 bad one); topic_id was chunk-level not question-level — both fixed, per-item flagging + per-question topic with FK validation, 32/32 tests passing
- [BUG-10](bugs.md#bug-10) — chunk-level topic failure still discarded question-level topic successes (6 real content chunks lost after BUG-09's fix) — `enrich_chunk` now extracts chunk metadata and per-question PYQs independently, 33/33 tests passing
- [BUG-11](bugs.md#bug-11) — `PLAN.md` cited DECIDE-16 as still open 3 sessions after it resolved (superseded by DECIDE-21/25 too) — caused a wrong answer to Rahul; fixed, lesson: trust decisions.md's own status, not a citing doc's framing

## Research
- [RESEARCH-01](research.md#research-01) — LanceDB reliability & concurrency
- [RESEARCH-02](research.md#research-02) — Anthropic Contextual Retrieval technique
- [RESEARCH-03](research.md#research-03) — Embedding model choice (nomic-embed-text vs alternatives)
- [RESEARCH-04](research.md#research-04) — Parent-document / auto-merging retrieval
- [RESEARCH-05](research.md#research-05) — Hallucination/citation grounding practice 2026
- [RESEARCH-06](research.md#research-06) — Cross-exam shared taxonomy architecture (O*NET crosswalks, junction-table pattern) — feeds DECIDE-19
- [RESEARCH-07](research.md#research-07) — EPFO-APFC 2026 + State PCS (UPPSC) exam pattern/syllabus, real sources
- [RESEARCH-08](research.md#research-08) — State PCS eligibility (domicile/language) + syllabus for Rahul's 8 target states — 4 feasible, 1 excluded, 3 open
- [RESEARCH-09](research.md#research-09) — EPFO family PYQ patterns (APFC/EO-AO combined paper since 2025, SSA/Steno thinner overlap) — weightage volatile/disputed, no verbatim PYQs recovered (gated PDFs)
- [RESEARCH-10](research.md#research-10) — Real 2025 APFC/EO-AO paper (120 items) transcribed in full from Rahul's own file — verified exact subject weightage, supersedes RESEARCH-09's disputed estimates

## Risks
- [RISK-01](risks.md#risk-01) — Scribe's grounding freshness lags until sync is re-run (inherent to DECIDE-03)
- [RISK-02](risks.md#risk-02) — Old Chroma metadata too sparse to carry over; full re-ingest required at cutover
- [RISK-03](risks.md#risk-03) — LanceDB's concurrency model won't hold at multi-user "publish it later" scale
- [RISK-04](risks.md#risk-04) — `upsc_epfo_apfc_eo_ao` topic weights seeded from a single verified year (2025); recompute from real data once a second year is ingested

## Assumptions
- [ASSUME-01](decisions.md#assume-01) — Law Optional / Econ Optional source PDFs will be supplied by Rahul later; schema is ready now, ingestion deferred

---

**Next available IDs:** DECIDE-26 · BUG-12 · RESEARCH-11 · RISK-05 · ASSUME-02
