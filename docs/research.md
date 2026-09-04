# Research

### RESEARCH-01 — LanceDB production reliability & concurrency {#research-01}
**Date:** 2026-09-04 | **Session:** S2

**Question:** Is LanceDB a reliable choice, and does its concurrency model hold up?
**Finding:** LanceDB supports concurrent writes but too many concurrent writers can cause
failing commits (limited retry count); it's explicitly positioned for edge/desktop/embedded
use, not high-concurrency production at scale — for that, purpose-built server DBs
(Qdrant, pgvector) are the more proven path. Ingestion is fast (fastest of LanceDB/Chroma/
pgvector in one benchmark) and it handles larger-than-memory datasets via disk-based Lance
format, with native hybrid (vector + Tantivy FTS) + reranking in one query.
**Applied to:** DECIDE-05 stands for now (single local writer, single-machine reads — the
concurrency caveat doesn't apply at Rahul's current scale). Logged as RISK-03: revisit at
multi-user "publish it" scale.
Sources: [LanceDB FAQ](https://docs.lancedb.com/faq/faq-oss), [Vector DB Comparison 2026](https://4xxi.com/articles/vector-database-comparison/), [LanceDB vs ChromaDB](https://aicoolies.com/comparisons/lancedb-vs-chromadb)

### RESEARCH-02 — Anthropic Contextual Retrieval {#research-02}
**Date:** 2026-09-04 | **Session:** S2

**Question:** Is there a proven technique to reduce retrieval failures / improve chunk
quality beyond hybrid search + reranking?
**Finding:** Anthropic's own published technique — prepend a short (50-100 token),
LLM-generated context blurb to each chunk before embedding ("this section discusses X
within document Y about Z"). Cuts top-20 retrieval failure rate by 35% alone, 49% combined
with contextual BM25, **67% combined with reranking** (which this platform already plans).
Cheap at scale via prompt caching of the source document.
**Applied to:** Proposed addition to Phase 1 (see Q1 below — needs Rahul's go-ahead, adds
one more LLM call per chunk at ingest time).
Source: [Anthropic — Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval)

### RESEARCH-03 — Embedding model choice (nomic-embed-text vs alternatives) {#research-03}
**Date:** 2026-09-04 | **Session:** S2

**Question:** Is `nomic-embed-text` (the spec's choice, DECIDE-06) actually good, or is
there a better local option?
**Finding:** nomic-embed-text (137M) is the smallest/fastest in its tier, Ollama-native,
and actually *outperforms* mxbai-embed-large on short/direct queries (57.5% vs 63.75% is
reversed in the source — nomic wins short queries). mxbai-embed-large (335M) does better on
long, context-heavy, implied questions. Both degrade meaningfully past ~4-8K token context
per chunk (not a concern here — chunks are far smaller than that).
**Applied to:** DECIDE-06 stands. For UPSC content, most queries are short/direct (topic
names, question stems) where nomic already wins — no change recommended. Flag mxbai as a
documented fallback if retrieval quality on long/implied queries proves weak in Phase 2
verification.
Source: [Embedding model benchmark 2026](https://zc277584121.github.io/rag/2026/03/20/embedding-models-benchmark-2026.html)

### RESEARCH-04 — Parent-document / auto-merging retrieval {#research-04}
**Date:** 2026-09-04 | **Session:** S2

**Question:** How do production RAG systems avoid the "context too short/fragmented"
failure Recall actually hit (see AUDIT-001)?
**Finding:** Standard pattern — embed and search on *small* chunks (precision), but when
multiple top-ranked chunks share the same parent section, return the merged parent section
to the LLM instead of disjoint fragments ("auto-merging retrieval"). Fixes fragmentation
without sacrificing search precision. Trade-off: more token cost per generation, more
complexity (two storage layers — chunk index + parent/section store), added latency for
the merge step.
**Applied to:** Proposed addition to Phase 1/2 schema (needs Rahul's go-ahead — see Q2
below, real schema commitment).
Sources: [Auto-Merging RAG](https://dev.to/rushanksavant/auto-merging-rag-hierarchical-retrieval-4dp1), [Parent Document Retrieval](https://dzone.com/articles/parent-document-retrieval-useful-technique-in-rag)

### RESEARCH-05 — Hallucination/citation grounding in 2026 RAG practice {#research-05}
**Date:** 2026-09-04 | **Session:** S2

**Question:** How should citation contracts and grounding checks actually be enforced to
minimize hallucination, without over-engineering?
**Finding:** Effective 2026 practice stacks *different* mitigations per failure mode rather
than one blanket rule: (1) a strict citation contract — every claim must cite a chunk_id,
model must abstain if nothing supports a claim; (2) sampled semantic-entailment checks
between a claim and its cited passage, for high-stakes generation only (cost-scaled); (3)
explicit handling of the "real citation, outdated fact" pitfall — a valid old source cited
as if current. Layered guardrails cut hallucination 71-89% vs. unguarded in cited studies.
**Applied to:** Proposed for Phase 2/4 (see Q3 below — aggressiveness/cost is Rahul's call).
Directly informs why RISK-01's `published_date`/recency design needs a harder
`is_current`/`superseded_by` flag, not just a soft ranking boost.
Sources: [Citation Grounding](https://arxiv.org/pdf/2606.00898), [Taming Hallucination 2026](https://futureagi.com/blog/taming-hallucination-beast-strategies-reliable-llms/)
