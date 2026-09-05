# Project HANDOFF

## Exact next step
Phase 0 is complete. Phase 1 (Ingestion + auto-labeling, PLAN.md) starts next: build the
header-aware two-stage chunker (`SyllabusChunker` — markdown-header split + recursive
fallback, persisting Stage-1 sections to the `sections` table), then the combined
Haiku-per-chunk enrichment call (classify + Contextual Retrieval blurb + PYQ extraction,
DECIDE-13), then Ollama `nomic-embed-text` embedding of `context_prefix + content`.

## Open items
- **DECIDE-16, needs Rahul's confirmation:** is `upsc_eco_optional` (ASSUME-01 placeholder
  in the original plan) the same exam as `upsc_eco_opt` (seeded as already-existing) or a
  distinct one? Only `upsc_eco_opt` was seeded — add a second registry row if they're
  different, before Phase 1 ingestion touches Economics Optional content.
- Ollama must be installed + `nomic-embed-text` pulled locally before Phase 1 embedding work
  starts (`ollama pull nomic-embed-text`) — not yet verified as installed.
- Law/Econ Optional content sourcing is on Rahul (ASSUME-01) — no action needed from this
  project until he supplies PDFs.
- Naming: repo is currently `nyaya-core` as a placeholder — confirm with Rahul or leave as-is.

## Session log
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
