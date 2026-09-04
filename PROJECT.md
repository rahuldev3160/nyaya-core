# Nyaya Core

Unified, exam-agnostic RAG data platform. Owns all raw content ingestion, indexing, and
retrieval for the Nyaya product family. Nyaya Recall (MCQ practice) and Nyaya Scribe
(descriptive/Mains practice) ground themselves on this instead of each running its own
siloed, weaker pipeline.

**Core goal:** adding a new exam should mean "add a registry row + drop PDFs in a folder +
run ingest" — zero code changes.

**Status:** Phase 0 — foundation. Not yet ingesting real content.

**Full architecture + phased plan:** `docs/FOUNDATION.md` and `PLAN.md`.

**Siblings:**
- `../Devthorium` — Nyaya Recall (consumes this platform's API live, same machine)
- `../Descriptive-exams` — Nyaya Scribe (consumes via batch sync export, Railway-deployed)
