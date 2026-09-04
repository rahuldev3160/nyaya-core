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
flag, browse endpoints) directly — no real tradeoff. **3 open questions need Rahul's
decision before Phase 2 is finalized: adopt Contextual Retrieval? adopt parent-document/
auto-merging retrieval? how aggressive should citation verification be?** See AUDIT-001
bottom section. PLAN.md updated to reflect all of the above.

**2026-09-04 (S1):** Project created from scratch this session. Investigated Recall
(Devthorium) and Scribe (Descriptive-exams) codebases to ground a spec doc's gap analysis;
scope expanded during planning into this standalone platform. Plan approved via plan mode
(`~/.claude/plans/sequential-herding-scone.md`). Mid-Phase-0, Rahul asked three sharpening
questions (topic+PYQ composite query, nomenclature reference, adaptability/freshness) —
answered and folded in as DECIDE-04/05/06/07 + RISK-01/02 before continuing scaffold.
Repo directory structure, docs/ audit system, FOUNDATION.md, DATA_DICTIONARY.md, PLAN.md
written. Next: schema code + DB init + parser port (see above).
