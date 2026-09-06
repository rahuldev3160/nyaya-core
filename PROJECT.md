# Nyaya Core

Unified, exam-agnostic RAG data platform. Owns all raw content ingestion, indexing, and
retrieval for the Nyaya product family. Nyaya Recall (MCQ practice) and Nyaya Scribe
(descriptive/Mains practice) ground themselves on this instead of each running its own
siloed, weaker pipeline.

**Core goal:** adding a new exam should mean "add a registry row + drop PDFs in a folder +
run ingest" — zero code changes.

**Status:** Phase 0+1 complete — full ingestion pipeline (parse → chunk → enrich → embed →
LanceDB) built and tested. 8 exams registered (`upsc_cse`, `upsc_ies`, `rbi_gradeb`,
`rbi_depr`, `uppcs`, `hpas`, `ukpsc`, `mppsc`) — naming finalized as `{institution}_{exam}`,
papers scoped by a composite key (DECIDE-21). 7 have real seeded topic taxonomies. Real
content ingestion not yet run — see `HANDOFF.md`.

**Full architecture + phased plan:** `docs/FOUNDATION.md` and `PLAN.md`.

**Siblings:**
- `../Devthorium` — Nyaya Recall (consumes this platform's API live, same machine)
- `../Descriptive-exams` — Nyaya Scribe (consumes via batch sync export, Railway-deployed)
