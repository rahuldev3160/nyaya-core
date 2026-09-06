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

### RESEARCH-06 — Cross-exam shared taxonomy architecture {#research-06}
**Date:** 2026-09-06 | **Session:** S4

**Question:** Rahul asked whether the same topic content can be "meta-indexed" for reuse
across multiple exams — should `topics` be shared/canonical rather than siloed per exam?
This directly resolves Descriptive-exams' `AUDIT-008` `DECIDE-32`, pending since 2026-06.
**Finding:** O*NET (US Dept of Labor's occupational taxonomy) is the closest real precedent
— one canonical taxonomy plus explicit crosswalk tables to other classification systems
(e.g. O*NET↔ESCO), never duplicated entities per system. General relational-DB practice
converges on the same mechanism for any many-to-many relationship: a junction/bridge table
carrying the relationship's own attributes (here: per-exam weight/relevance), not entity
duplication. Current (2026) RAG knowledge-base practice independently agrees: a controlled
hierarchical taxonomy for tagging, with relationship/crosswalk layers added only where
cross-cutting retrieval is needed — not duplicated per source. A full ontology/graph model
was considered and rejected as overkill: no query pattern here needs graph traversal or
typed relationships, just "which exams care about this topic, how much."
**Applied to:** DECIDE-19 — `topics` made exam-agnostic, new `exam_topics` junction table
(exam_id, topic_id, weight, is_core) added, migrated same session with zero data loss.
Sources: [O*NET Crosswalks](https://www.onetcenter.org/crosswalks.html), [O*NET↔ESCO crosswalk](https://esco.ec.europa.eu/en/about-esco/escopedia/escopedia/crosswalk-between-onet-and-esco), [Many-to-many DB relationships](https://www.datacamp.com/blog/many-to-many-relationship), [Many-to-many guide](https://www.beekeeperstudio.io/blog/many-to-many-database-relationships-complete-guide), [RAG knowledge-base optimization](https://unstructured.io/insights/knowledge-base-optimization-for-enterprise-rag-pipelines)

### RESEARCH-07 — EPFO-APFC 2026 + State PCS exam pattern/syllabus {#research-07}
**Date:** 2026-09-06 | **Session:** S4

**Question:** How do we get a real, official-source-grounded topic taxonomy for exams with
no internal source (EPFO-APFC, State PCS), rather than guess from training memory (exam
patterns change — Rule 2)?
**Finding:** **EPFO-APFC 2026** — real, live notification, applications open until 11 Sept
2026 (imminent). 300-mark, 120-question objective Recruitment Test (2 hrs) + 100-mark
interview, 75:25 weighted merit. Syllabus is a **flat subject list**, not a granular
topic/subtopic breakdown, in the official notification itself: General English, Indian
Polity, Economy, Labour Laws, Social Security, General Science, Current Affairs,
Accounting, Statistics, Auditing, Insurance. Several subjects (Polity, Economy, Current
Affairs) directly overlap with the existing `upsc_prelims_gs` canonical topics — DECIDE-19
means these can be linked via new `exam_topics` rows with **zero new topics needed**.
Labour Laws/Social Security/Accounting/Statistics/Auditing/Insurance are genuinely new
branches requiring real curation (official syllabus is flat; granular subtopics would need
either a sourced coaching breakdown cross-checked against real PYQs, or Haiku-assisted
decomposition of the flat list with human review — same method IES/RBI's existing internal
taxonomies were likely built by).
**State PCS (UPPSC example)** — 3-stage structure (Prelims/Mains/Interview) is structurally
near-identical to UPSC: Prelims = GS + qualifying CSAT (400 marks), Mains = compulsory GS
papers + Essay + Ethics, optional subjects removed. Confirms **heavy syllabus overlap with
UPSC Prelims GS** — most State PCS content can reuse existing canonical topics via
`exam_topics`, not rebuild from scratch. "State PCS" is not one exam (UPPCS/BPSC/MPPCS etc.
all differ) — general finding only, a specific state needs naming before real per-state work.
**Repeatable process for a future new exam:** (1) find the real official notification/
syllabus (never assume), (2) check whether it's flat (most are) or already hierarchical,
(3) for subjects that overlap an existing canonical topic tree, add `exam_topics` rows only
— no new topics, (4) for genuinely new subjects, curate a real topic/subtopic breakdown
(sourced or Haiku-assisted-with-review) and seed via a generalized `scripts/seed_topics.py`.
**Applied to:** Informs Phase 1's remaining taxonomy-sourcing open item; no code changed by
this research itself.
Sources: [UPSC EPFO APFC Notification 2026](https://www.adda247.com/exams/upsc/upsc-epfo-apfc-notification-2026/), [UPSC APFC Syllabus 2026](https://www.careerpower.in/upsc-epfo-apfc-syllabus.html), [UPPSC Syllabus 2026](https://www.pw.live/state-psc/exams/uppsc-syllabus), [UPPSC Syllabus & Pattern](https://testbook.com/uppcs/syllabus-exam-pattern)

### RESEARCH-08 — State PCS eligibility (domicile/language) + syllabus for Rahul's 8 target states {#research-08}
**Date:** 2026-09-06 | **Session:** S4

**Question:** Rahul named 8 State PCS targets (Rajasthan, Haryana, UP, Himachal,
Uttarakhand, Gujarat "if Gujarati not mandatory", Maharashtra, MP). Real eligibility facts
(domicile, language) needed verification before any taxonomy work — these are exactly the
kind of "facts that change" Rule 2 says never to answer from training memory.
**Finding, per state:**
- **Rajasthan (RAS):** Open to non-domicile (General category; Rajasthan domicile only
  gives selection-process priority, not exclusivity). But the live 2026 cycle's application
  window opened June 2026 and is almost certainly already closed — consistent with Rahul's
  own earlier-confirmed missed RAS application (memory: 2026-08-29). Feasible for a future
  cycle, not this one.
- **Haryana (HCS):** Open to non-domicile (verified with a second search after an initial
  misleading result — corrected in-session, not silently left wrong). Mains structure is
  **genuinely disputed** across sources: one says optional subjects removed (Jan 2026
  amendment, 4 GS papers like UPSC), another says English/Hindi/GS/1-optional still stands.
  Not resolved — needs the actual HPSC notification.
- **UP (UPPCS):** Open to non-domicile, General category. Prelims GS Paper 1 has 7 domains
  matching UPSC almost exactly; UP-specific content is ~16-19% of the paper (15-18 direct +
  7-10 embedded questions), covering UP history/culture/festivals/languages/heritage plus
  geography/resources/economy (rivers, agriculture, minerals, forests).
- **Himachal (HPAS):** Open to non-domicile; domicile only affects reservation, not general
  eligibility. Prelims/Mains cover History/Geography/Polity/Culture/Socio-economic
  Development of Himachal Pradesh alongside standard national GS. Least granular source
  material found of the 4 feasible states.
- **Uttarakhand (UKPSC):** Open to non-domicile; domicile only affects reservation. **Most
  heavily state-weighted of any exam researched** — official material states ≥1/3 of
  Prelims questions reference Uttarakhand directly. Real named-entity detail found: Katyuri/
  Parmar/Chand dynasties, Gorkha invasion, Tehri State, and 5 named popular movements
  (Chipko, Coolie Begar, Dola Palki, Anti-Liquor, statehood).
- **Gujarat (GPSC):** Rahul's condition ("if Gujarati not mandatory") is **not met**.
  Gujarati isn't required for Prelims (English is fine), but Mains has a compulsory
  *qualifying* Gujarati paper (300 marks, 30% pass bar) alongside an English one — real
  functional Gujarati is needed to clear Mains, not just to apply.
- **Maharashtra (MPSC):** Sources state Marathi-at-10th-standard as a stated eligibility
  criterion (stricter than Gujarat's qualifying-paper model), but this needs the actual
  MPSC notification to confirm — the search result may be conflating rules across different
  post categories. Deliberately left unresolved rather than asserted either way.
- **MP (MPPSC):** Open to non-domicile, General category, no language bar found. Prelims/
  Mains cover MP dynasties/tribes/festivals/arts/freedom-movement-contribution alongside
  standard national GS.
**Applied to:** DECIDE-20 — the 4 confirmed-feasible exams (UP, Himachal, Uttarakhand, MP)
registered and seeded; Gujarat excluded per Rahul's own condition; Haryana/Maharashtra/
Rajasthan left open pending the specific unresolved question for each.
**Process note:** the first fork launched for part of this research malfunctioned (kept
echoing a sibling fork's findings instead of its own, on two attempts) — abandoned and
redone via direct WebSearch. Logged as product feedback separately.
Sources: [RPSC RAS 2026](https://www.examdetail.in/exams/rpsc-ras-2026), [HPSC HCS 2026](https://o2iasacademy.in/hcs-notification-2026-eligibility-syllabus-age-limit-9644/), [UPPSC Eligibility](https://lotusarise.com/uppsc/uppsc-exam-eligibility/), [UPPCS Syllabus Weightage](https://www.legacyias.com/uppcs-prelims-syllabus-gs-paper-1-pyq-analysis-topic-weightage/), [HPPSC HPAS Syllabus](https://www.studyiq.com/articles/hppsc-syllabus/), [UKPSC Prelims Syllabus](https://www.drishtiias.com/state-pcs/ukpsc-prelims-syllabus), [UKPSC Mains Syllabus](https://www.drishtiias.com/state-pcs/ukpsc-mains-syllabus), [GPSC Syllabus](https://www.oliveboard.in/blog/gpsc-syllabus/), [MPSC Eligibility](https://www.pw.live/state-psc/exams/mpsc-eligibility-criteria), [MPPSC Syllabus 2026](https://www.pw.live/state-psc/exams/mppsc-syllabus)
