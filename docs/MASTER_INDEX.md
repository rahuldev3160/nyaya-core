# Master Index — Nyaya Core

Pointer catalogue. One line per artefact. Full entries live in the linked files.

## Decisions
- [DECIDE-01](decisions.md#decide-01) — New standalone repo, not built inside Recall or Scribe
- [DECIDE-02](decisions.md#decide-02) — Recall's ChromaDB pipeline replaced outright, not run in parallel
- [DECIDE-03](decisions.md#decide-03) — Scribe consumes via batch export/sync, not a live API call
- [DECIDE-04](decisions.md#decide-04) — `topic_id` is a shared FK across chunks and pyq_bank, not free text
- [DECIDE-05](decisions.md#decide-05) — LanceDB over ChromaDB for native hybrid search
- [DECIDE-06](decisions.md#decide-06) — Ollama `nomic-embed-text` over Recall's sentence-transformers
- [DECIDE-07](decisions.md#decide-07) — Recency signal added to ranking for time-sensitive content types

## Bugs
_(none yet — Phase 0, no code running)_

## Research
_(none yet)_

## Risks
- [RISK-01](risks.md#risk-01) — Scribe's grounding freshness lags until sync is re-run (inherent to DECIDE-03)
- [RISK-02](risks.md#risk-02) — Old Chroma metadata too sparse to carry over; full re-ingest required at cutover

## Assumptions
- [ASSUME-01](decisions.md#assume-01) — Law Optional / Econ Optional source PDFs will be supplied by Rahul later; schema is ready now, ingestion deferred

---

**Next available IDs:** DECIDE-08 · BUG-01 · RESEARCH-01 · RISK-03 · ASSUME-02
