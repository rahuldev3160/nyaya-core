# Nyaya Core

Unified, exam-agnostic RAG data platform. Owns all raw content ingestion, indexing, and
retrieval for the Nyaya product family. Nyaya Recall (MCQ practice) and Nyaya Scribe
(descriptive/Mains practice) ground themselves on this instead of each running its own
siloed, weaker pipeline.

**Core goal:** adding a new exam should mean "add a registry row + drop PDFs in a folder +
run ingest" — zero code changes.

**Status:** Phase 0+1+2 complete — full ingestion pipeline (parse → chunk → enrich → embed
→ LanceDB) AND hybrid retrieval + FastAPI (`src/retrieval/`, `src/api/`) built, tested,
and validated against real content (127/127 tests). `scripts/inventory.py` found PFRDA
has zero indexed chunks and EPFO only 125 thin ones — `/pyq` (structured) is the real
foundation for both, not `/search` (see DECIDE-37). 10 exams registered
(`upsc_cse`, `upsc_ies`, `rbi_gradeb`, `rbi_depr`, `uppcs`, `hpas`, `ukpsc`, `mppsc`,
`upsc_epfo_apfc_eo_ao`, `pfrda_gradea`) — naming finalized as `{institution}_{exam}`, papers
scoped by a composite key (DECIDE-21). `upsc_cse`'s Optional papers are split into Paper I/II
(`eco_optional_1/2`, `law_optional_1/2` — DECIDE-25). `pfrda_gradea` (DECIDE-30) has a fresh
28-topic taxonomy for General+Research streams but zero content ingested yet (real weights
pending — RISK-07). 9 exams have real seeded topic taxonomies (`upsc_cse`'s non-prelims/
non-optional papers and `rbi_depr` don't yet). First real ingestion run
(`upsc_epfo_apfc_eo_ao`'s 2025 paper) yielded 36 verified questions across 14 topics; total
now 608 verified EPFO questions across 6 paper-instances — see `HANDOFF.md` for what's next.

**Full architecture + phased plan:** `docs/FOUNDATION.md` and `PLAN.md`.

**Siblings:**
- `../Devthorium` — Nyaya Recall (consumes this platform's API live, same machine)
- `../Descriptive-exams` — Nyaya Scribe (consumes via batch sync export, Railway-deployed)
