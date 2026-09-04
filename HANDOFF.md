# Project HANDOFF

## Exact next step
Phase 0 continuing: write `src/schema/models.py` (Pydantic — `ChunkMetadata`, `TextChunk`,
`PYQQuestion`), then `scripts/init_db.py` (creates `data/core.db` with `exams`/`papers`/
`topics`/`content_types`/`pyq_bank`, seeds the registry rows listed in PLAN.md Phase 0),
then port `scripts/parsers/` from `../Devthorium/scripts/parsers/` verbatim.

## Open items
- Phase 0 not yet complete — no schema code, no DB, no parsers ported yet as of this entry.
- Naming: repo is currently `nyaya-core` as a placeholder — confirm with Rahul or leave as-is.
- Ollama must be installed + `nomic-embed-text` pulled locally before Phase 1 embedding work
  starts (`ollama pull nomic-embed-text`) — not yet verified as installed.
- Law/Econ Optional content sourcing is on Rahul (ASSUME-01) — no action needed from this
  project until he supplies PDFs.

## Session log
**2026-09-04 (S1):** Project created from scratch this session. Investigated Recall
(Devthorium) and Scribe (Descriptive-exams) codebases to ground a spec doc's gap analysis;
scope expanded during planning into this standalone platform. Plan approved via plan mode
(`~/.claude/plans/sequential-herding-scone.md`). Mid-Phase-0, Rahul asked three sharpening
questions (topic+PYQ composite query, nomenclature reference, adaptability/freshness) —
answered and folded in as DECIDE-04/05/06/07 + RISK-01/02 before continuing scaffold.
Repo directory structure, docs/ audit system, FOUNDATION.md, DATA_DICTIONARY.md, PLAN.md
written. Next: schema code + DB init + parser port (see above).
