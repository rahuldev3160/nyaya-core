---
id: AUDIT-001
type: audit
project: nyaya-core
date: 2026-09-04
status: findings ready — 3 items need Rahul's decision (see bottom)
---

# Architecture Review — against Rahul's 6 stated criteria

Audit of Phase 0's docs (FOUNDATION.md, DATA_DICTIONARY.md, decisions.md) against the
criteria Rahul gave directly: universal/adaptable/navigable, sufficient retrieval size,
extensible indexing, reliable vector storage, minimized latency, minimized noise/hallucination.

## 1. Universal, adaptable, navigable — mostly PASS, one real gap

Data-driven `exams`/`papers`/`topics`/`content_types` registries (DECIDE-01/04) make this
genuinely universal — a new exam is a row. **Gap:** "navigable" needs a browse API, and the
plan only had `/exams` + the composite `/topic/{id}/brief`. **Fix:** add `/topics?exam_id=`
and `/papers?exam_id=` to Phase 2's API list — done, see PLAN.md update below.

## 2. Sufficient retrieval size — CONFIRMED BUG, root cause found

This already happened in Recall exactly as Rahul described. Root cause, verified in code:

- `scripts/generate_answers.py` (Descriptive-exams) truncates each retrieved chunk to
  **400 characters** (~100 tokens) before injecting into the prompt — 4 chunks ≈ 400 tokens
  of total grounding for generating a full model answer. That's the bug.
- `backend/routes/quiz.py`'s `_chunk_k()` caps retrieval at `min(8, max(3, q+2))` chunks
  regardless of what the generation task actually needs — the same fixed budget serves a
  quick MCQ explanation and a full Mains answer.

**Fix (already reflected in this audit's plan update):**
1. `k`/token-budget becomes a **caller-supplied parameter** on `/search` and
   `/topic/{id}/brief`, never a hardcoded engine default. A live MCQ-explanation call and a
   batch Mains-model-answer call should not share one budget — the batch call is cheap to
   make generous (it runs once, gets cached forever).
2. Never truncate a chunk mid-content to fit a budget (the 400-char bug). If budget-constrained,
   drop whole lower-ranked chunks instead.
3. **Parent-document/auto-merging retrieval** (RESEARCH-04) — search on small chunks for
   precision, but return the merged parent section when multiple top hits share one, so
   generation sees coherent context instead of disjoint fragments. **This is the structural
   fix for "content too short" — needs Rahul's go-ahead, see Q2.**

## 3. Extensible indexing (additive, non-breaking) — real gap, fix proposed

Current schema (Phase 0 as written) has fixed columns for known dimensions (`exam_id`/
`topic_id`/`content_type`/`source_type`). Adding a genuinely new dimension later (e.g.
"difficulty_level", "committee_name" for a report, "case_citation" for a law chunk) would
mean a schema migration on both stores — disruptive on LanceDB specifically, where adding a
field to an existing columnar table isn't a clean additive operation.

**Fix:** hybrid schema —
- Keep today's known-important dimensions as real columns (fast, filterable) — no change.
- Add **one `tags` JSON/dict field** to both `chunks` and `pyq_bank` from Phase 0, for
  anything ad hoc added later with zero migration.
- Add a companion SQLite `chunk_tags(chunk_id, tag_key, tag_value)` EAV table for any tag
  that needs fast indexed lookup (not just "stored," but "searchable" — the JSON field alone
  is fine for storage, not for filtering at scale).
- One thing to verify during Phase 1 build, not assumed here: LanceDB's exact support for
  filtering on a JSON/struct column vs. a flat string — confirm before relying on it
  (flagged as an implementation-time check, not a design blocker).

This directly answers "can I add subtopic name or exam name as a new index without changing
existing code" — yes, via the tags field/table, additive by construction.

## 4. Vector storage/retrieval reliability — sound for current scale, flagged for later

RESEARCH-01: LanceDB is a legitimate, fast, reliable choice for a **single local writer,
single-machine reader** setup — which is exactly Rahul's situation now. Its known limitation
(concurrent-write failures under high multi-writer load) doesn't apply here. Logged as
**RISK-03**: if this platform is ever opened to other users concurrently (Rahul's stated
"publish it later" goal), LanceDB's embedded single-machine model won't hold — would need a
server-backed vector DB (Qdrant, pgvector, or LanceDB Cloud) at that point. Not a concern
for personal use; worth knowing before building on an assumption that silently breaks later.

## 5. Latency — right-sized, one distinction added

Recall's own CLAUDE.md already establishes "zero API calls during quiz sessions — content is
batch-generated beforehand." So most of this platform's calls are **batch/pregeneration**
(session generation, model-answer generation) — seconds of latency is fine, there's no live
UI waiting on it.

**Gap found:** the "read a concept" browse feature Rahul described (Scribe, Phase 5) IS a
live, interactive call — a user tapping a topic while studying expects a fast response, not
batch latency. The plan hadn't separated these two patterns.

**Fix:** two latency budgets, not one — batch calls favor larger context/quality (per §2),
interactive browse calls favor a smaller `k` + caching (topic content changes rarely, so
`/topic/{id}/brief` responses and the query embeddings behind common lookups can be cached
and reused rather than recomputed on every view).

## 6. Noise/hallucination minimization — real gap, fix proposed

Recall's current fallback when no chunks match is literally: *"Generate from canonical
syllabus knowledge"* (`quiz.py:466-469`) — an explicit invitation to hallucinate, not a
guardrail.

**Fix (RESEARCH-05):**
1. A similarity/rerank **score floor** — chunks below threshold aren't used; if nothing
   clears it, the caller gets an explicit "insufficient grounding" signal instead of a
   silent green light to freewheel.
2. A **citation contract**: every factual claim in generated output must reference a
   `chunk_id`; the model must abstain from claims it can't ground. Sampled entailment
   verification (does the cited passage actually support the claim) for high-stakes
   generation (Mains model answers) — skipped for cheap/low-stakes calls to control cost.
   **Aggressiveness here is a real cost/quality trade-off — see Q3.**
3. **Trust-weighted grounding**: chunks with `source_type = ai_generated` shouldn't silently
   become "ground truth" for further generation (hallucination compounding) — deprioritize
   or exclude them from grounding by default unless explicitly allowed.
4. The "valid citation, outdated fact" pitfall (a real 2026 source flagged in research):
   extends DECIDE-07's soft recency boost into something harder where it matters — a
   `superseded_by`/`is_current` flag so an old Economic Survey doesn't just rank lower than
   a new one, it gets excluded once a newer one exists for the same indicator/topic.

## Additional ideas surfaced (not decided, for awareness)

- **Evaluation harness**: a small hand-labeled query→expected-chunk set, tracked over
  sessions, so retrieval quality is measured, not eyeballed. Formalizes what Phase 2's
  verification note already gestured at.
- **Cost/usage tracking on ingestion**: contextual retrieval + auto-labeling both add Haiku
  calls at ingest time. Scribe already has this instinct (`MainsEvaluator`'s ₹ cost
  telemetry) — Nyaya Core's ingestion should log the same, so a large batch ingest never
  produces a surprise bill.
- **Query expansion (HyDE, etc.)** for vague queries — lower priority, noted as a future
  enhancement, not core.
- Everything above is compatible with "others' preparation" later — the registry-based
  design is exactly what would let a future multi-user version scale to other users/exams
  without re-architecture. Nothing built now is throwaway for that future.

---

## Three things that need your call before I build them in

**Q1 — Contextual Retrieval (RESEARCH-02).** Adopt Anthropic's own technique: one extra
Haiku call per chunk at ingest time to write a short context blurb before embedding. Proven
35-49% fewer retrieval failures, 67% combined with reranking (which we're already doing).
Adds ingest-time cost and time, zero query-time cost.

**Q2 — Parent-document/auto-merging retrieval (RESEARCH-04).** The structural fix for the
"content too short" bug — search small chunks, return merged parent sections. Real schema
commitment (a documents/sections hierarchy, two storage layers) and more tokens per
generation call, in exchange for coherent (not fragmented) context.

**Q3 — Citation-verification aggressiveness (RESEARCH-05).** How hard should the platform
work to catch a hallucinated citation before it reaches you? Full entailment-check on every
claim is the safest but adds real LLM cost per generation; sampling only high-stakes content
is cheaper but leaves more to trust.
