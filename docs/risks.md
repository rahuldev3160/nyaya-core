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

### RISK-02 — Old Chroma metadata too sparse for direct migration {#risk-02}
**Date:** 2026-09-04 | **Session:** S1 | **Status:** Open

**Risk:** Recall's existing ChromaDB chunks carry only `subject_id`/`source_file`/`parser`/
`file_path`/`chunk_index` — no page numbers, no topic_id, no content_type, no provenance.
A straight copy into the new schema would leave most new fields null.
**Mitigation:** Phase 3 re-ingests from the original source files through the new pipeline
(re-chunk, re-embed, re-label) rather than migrating the old vector store directly. Slower
but produces complete, correctly-typed rows.
