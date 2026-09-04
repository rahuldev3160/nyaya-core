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

## Bugs
- [BUG-01](bugs.md#bug-01) — Scribe's `generate_answers.py` truncates grounding chunks to 400 chars (found, not yet fixed — scheduled for Phase 4)

## Research
- [RESEARCH-01](research.md#research-01) — LanceDB reliability & concurrency
- [RESEARCH-02](research.md#research-02) — Anthropic Contextual Retrieval technique
- [RESEARCH-03](research.md#research-03) — Embedding model choice (nomic-embed-text vs alternatives)
- [RESEARCH-04](research.md#research-04) — Parent-document / auto-merging retrieval
- [RESEARCH-05](research.md#research-05) — Hallucination/citation grounding practice 2026

## Risks
- [RISK-01](risks.md#risk-01) — Scribe's grounding freshness lags until sync is re-run (inherent to DECIDE-03)
- [RISK-02](risks.md#risk-02) — Old Chroma metadata too sparse to carry over; full re-ingest required at cutover
- [RISK-03](risks.md#risk-03) — LanceDB's concurrency model won't hold at multi-user "publish it later" scale

## Assumptions
- [ASSUME-01](decisions.md#assume-01) — Law Optional / Econ Optional source PDFs will be supplied by Rahul later; schema is ready now, ingestion deferred

---

**Next available IDs:** DECIDE-16 · BUG-02 · RESEARCH-06 · RISK-04 · ASSUME-02
