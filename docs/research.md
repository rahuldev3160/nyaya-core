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

### RESEARCH-09 — EPFO exam family PYQ patterns (APFC/EO-AO/SSA/Steno), real sources {#research-09}
**Date:** 2026-09-09 | **Session:** S5

**Question:** Before registering `upsc_apfc` (deferred at end of S4 pending Rahul's
go-ahead), what do real previous-year papers say about subject weightage, question style,
and recurring sub-topics — and how much of this generalizes across the wider EPFO exam
family? Answered via 3 parallel forks (APFC-specific, EO/AO-specific, wider-family).

**Structural finding (corrects an assumption made mid-session):** APFC and EO/AO have been
conducted as **one combined paper** since the 2025 cycle — same syllabus, same pattern,
same sitting (UPSC's own stated position: "EPFO and APFC exams are going to have the same
syllabus and exam pattern"). 120 MCQs, 2.5 marks each, 300 total, 1/3 negative marking, 2
hrs, English+Hindi — confirmed consistent across cycles. This means the EO/AO-labeled PYQ
research is directly reusable for APFC prep, not a separate body of content.

**Time-sensitive fact, more consequential than the pattern question:** EPFO withdrew its
separate 311-post EO/AO requisition to UPSC on 2026-06-08; UPSC has confirmed EO/AO will
NOT be notified in 2026. Only APFC (80 posts, Special Advertisement 52/2026) is live this
cycle — closing 2026-09-11. If EO/AO returns in a future cycle, it will likely again be
bundled into the same combined paper, not a separate exam with separate content.

**Subject-wise weightage — real but genuinely volatile, not a fixed table:**
| Subject | 2023 | 2025 | Confidence |
|---|---|---|---|
| General English | 20 | 20 | High |
| Accountancy/Auditing | 15 | 10 | Medium (declining trend, magnitude disputed) |
| IR & Labour Laws | 14 | 6 | Medium (real, sharp decline; magnitude disputed) |
| Quant/Reasoning | 15 | 14 | High |
| Current Affairs | 8 | 16 | Low (sources disagree even on direction) |
| History & Culture | 10 | 9 | Low |
| Indian Polity | 9 | 9 | Medium |
| General Science/Computer | 10 | 14 | Medium |
| Social Security | 5 | 14 | Low (wildly disputed: 5 vs 14 vs 3-5 depending on source) |
| Economy | 1 | 2 | Low |

No official UPSC subject-tagged answer key exists — every number above is a coaching-site
reconstruction from candidate recall, not ground truth. Year-to-year swings are real
(confirmed independently by 2+ sources), not noise — but exact 2026 figures are
unverifiable in advance. Treat as a prioritization signal, not a spec.

**Question style (higher-confidence, consistent across sources):**
- Polity: statement-based ("how many of the following statements are correct"), same
  format as UPSC CSE Prelims — already modeled by `MCQQuestion.statements` (DECIDE-23).
- Accountancy: mixed conceptual + numerical + case-study (Trial Balance, Final Accounts
  recur).
- IR/Labour Laws: provision/Act-specific (Factories Act 1948, Trade Unions Act 1926,
  Minimum Wages Act 1948, the 4 new Labour Codes, statutory definitions like
  workman/strike/lockout/closure), not general awareness.
- Computer Applications: conceptual (translators, output devices, file formats, memory
  types), not applied/practical.
- Social Security: provision-based, with an explicit schemes-vs-Acts split noted by one
  source.
- EO/AO-specific style note: fully fact-based/direct, no statement-based reasoning —
  contrasts with the Polity finding above; style appears to vary by subject, not be uniform
  across the whole paper.

**No verbatim PYQ text recovered.** Real PYQ PDFs exist for multiple cycles (2002/2004/
2012/2015/2023/2025) on coaching sites but are gated behind downloads/paywalls, not
scrapeable via search/fetch. This is a real content-sourcing gap, same shape as ASSUME-01
(Law/Econ Optional) — needs Rahul to source the actual PDFs before `pyq_bank` can be
populated for real, not reconstructed from analysis articles.

**Wider EPFO family (SSA, Stenographer) — thinner overlap than expected:** SSA/Steno are
**IBPS-conducted** (not UPSC), single-phase CBT + qualifying skill test (no interview,
skill marks don't count), 1/4 negative marking (not APFC's 1/3 — marking schemes are NOT
uniform across the family). Syllabus is generic bank-clerk-style aptitude (English/Quant/
General Awareness/Computer) with **no evidence of APFC's specialized domain subjects** —
no Labour Codes, no Accountancy/Auditing/Insurance, no Constitution/Governance, no Culture/
Heritage. These are Group-B-officer-level subjects specific to APFC/EO-AO, not present at
SSA/Steno's staff level. Shared core across the full family: English, Quant, General
Awareness, Computer basics only — same junction-table pattern as DECIDE-19 applies to that
shared core, but APFC's domain-specific topics should NOT be assumed to transfer to SSA/
Steno prep.

**Applied to:** informs the pending `upsc_apfc` registration decision — naming (should
APFC/EO-AO share one exam_id given they're one combined paper?) and weight-modeling
(seed a disputed coaching-site number vs. defer real weight to post-ingestion PYQ-tag
frequency) presented to Rahul as open decisions in-session, not yet resolved.

Sources: [pw.live EPFO pattern](https://www.pw.live/upsc/exams/upsc-epfo-exam-pattern), [careerpower.in EPFO syllabus](https://www.careerpower.in/upsc-epfo-syllabus.html), [bankersadda.com EO/AO syllabus](https://www.bankersadda.com/upsc-epfo-eo-ao-syllabus/), [edutap.in recruitment chances](https://edutap.in/upsc-epfo/notification/recruitment-chances/), [edutap.in notification](https://edutap.in/upsc-epfo/notification/), [padhai.ai](https://padhai.ai/upsc-update/notifications/upsc-epfo-notification-2026), [testbook.com syllabus](https://testbook.com/upsc-epfo/syllabus), [testbook.com exam analysis](https://testbook.com/upsc-epfo/exam-analysis), [testbook.com APFC PYPs](https://testbook.com/upsc-apfc/previous-year-papers), [edutap.in exam analysis](https://edutap.in/upsc-epfo/exam-analysis/), [edutap.in PYQs](https://edutap.in/upsc-epfo/previous-year-questions/), [edutap.in labour law prep](https://edutap.in/upsc-epfo/how-to-prepare-labour-law-in-upsc-epfo/), [sleepyclasses.com APFC analysis](https://sleepyclasses.com/upsc-epfo-apfc-previous-year-paper-analysis-upsc-apfc-exam-pattern-pyqs-preparation-strategy-qs/), [bankersadda.com SSA syllabus](https://www.bankersadda.com/epfo-ssa-syllabus/), [careerpower.in SSA syllabus](https://www.careerpower.in/blog/epfo-ssa-syllabus), [ixambee.com SSA pattern](https://www.ixambee.com/exams/epfo-ssa-exam-pattern), [testbook.com SSA syllabus](https://testbook.com/epfo-ssa/syllabus-exam-pattern)

### RESEARCH-10 — Real 2025 APFC/EO-AO paper, transcribed in full — supersedes RESEARCH-09's disputed weightage {#research-10}
**Date:** 2026-09-09 | **Session:** S5

**Question:** RESEARCH-09 found only coaching-site reconstructions of subject weightage
(disputed, self-contradicting across sources). Rahul already had the actual 2025 combined
APFC/EO-AO question booklet (Set A, dated 30-11-2025, "CRT-IX APFC/EO/AO 2025") sitting in
`Desktop/opportunities/govt notifications/epfo_apfc_eoao_2025_question_paper.pdf` — a real
44-page bilingual (Hindi+English) scanned test booklet, not a coaching-site summary. Read in
full (all 120 items) rather than asking Rahul to source PYQs separately, since the file was
already present and this directly resolves RESEARCH-09's biggest gap (no verbatim PYQs
found).

**Verified structure:** 120 items, Part A (Q1-20) + Part B (Q21-120, printed in both Hindi
and English), 2 hours, 300 marks, 1/3 negative marking — matches the notification exactly.

**Real, exact subject-wise question counts (ground truth for the 2025 cycle, not an
estimate):**
| Subject | Q range | Count |
|---|---|---|
| General English | 1-20 | 20 |
| Indian Culture/Heritage/Freedom Movements | 21-29 | 9 |
| Developmental Issues & Indian Economy | 30-38 | 9 |
| Governance & Constitution of India | 39-50 | 12 |
| General Science & Computer Applications | 51-65 | 15 |
| Elementary Maths/Statistics/GMA | 66-80 | 15 |
| Industrial Relations, Labour Codes & Social Security | 81-95 | **15** |
| Principles of Accountancy, Auditing & Insurance | 96-110 | **15** |
| Current Events (national/international + EPFO-specific) | 111-120 | 10 |

**This corrects RESEARCH-09's disputed numbers materially** — Labour Codes was estimated at
3-14 depending on source; the real 2025 count is 15, tied for the single largest bucket
alongside Science/Computer and Accountancy/Auditing/Insurance. Coaching-site "declining
trend" claims for Labour Codes/Accountancy are not supported by this real data point.
**Caveat, still real:** this is one verified year (2025), not proof next year repeats
these exact counts — RESEARCH-09's point about genuine year-to-year volatility stands; what
changes is that we now have one confirmed ground-truth anchor instead of zero.

**Question style, subject-specific (more precise than RESEARCH-09's single "fact-based vs
statement-based" split):** English (RC + vocabulary + grammar-correctness, no
statement-based items), History/Culture/Economy/Governance/Current-Events (heavily
statement-based, "which of the following is/are correct," assertion-reason, match-the-list
— same format as UPSC CSE Prelims), Labour Codes (mixed — many direct single-best-answer
recall items plus real computation items, e.g. compensation payable under the Employees'
Compensation Act 1923 using a stated "relevant factor"), Accountancy (direct
concept/definition recall plus journal-entry and formula application), Science/Computer
(direct factual recall, no statements).

**Real recurring statutory content confirmed** (not coaching-site paraphrase, read directly
off real questions): EPF & Miscellaneous Provisions Act 1952 (existing schemes — EPF 1952,
EDLI 1976, EPS 1995, Family Pension 1971 — and its Cooperative Societies Act 1912
exemption threshold), ESI Act 1948 (contribution computation, 4 named benefits), Payment of
Wages Act 1936 (payment-in-coin, wage period, deduction categories), Employees'
Compensation Act 1923 (disablement classification, compensation computation), Industrial
Disputes Act 1947 (the *Bangalore Water Supply v. Rajappa* "triple test" for `industry`,
public-utility-service notice periods, First Schedule exclusions), Trade Unions Act 1926
(registered-TU rights), Maternity Benefit Act 1961 (nursing breaks, commissioning-mother
provisions), Payment of Gratuity Act 1972 (eligibility scenarios). Current Events skewed
heavily toward EPFO's own recent policy moves (SPREE 2025, Employment Linked Incentive
Scheme, EPFO's auto-settlement limit increase to ₹3 lakh) alongside generic national/
international GK — a real EPFO-specific current-affairs sub-theme, not just generic
Current Affairs.

**Applied to:** directly answers the open "do you have real PYQ PDFs" question from the
architecture discussion — yes, at least one real cycle's full paper is already on disk.
This paper itself is real ingestible content for `pyq_bank` once `upsc_apfc` (naming still
pending Rahul's confirmation) is registered — no further sourcing needed to get started,
though only one year's worth exists so far. Does not resolve the weight-modeling open
question from RESEARCH-09/the architecture proposal (a single real year still isn't the
same as a stable multi-year average) but gives it a real anchor point instead of zero data.

Source: `epfo_apfc_eoao_2025_question_paper.pdf` (Rahul's own file, UPSC's official 2025
CRT-IX test booklet, Set A) — read in full, all 44 pages / 120 items.

### RESEARCH-11 — PFRDA Research stream real signal + cross-exam economics/statistics topic-sync plan {#research-11}
**Date:** 2026-09-16 | **Session:** external

**Question:** What real PYQ/depth/style signal exists for PFRDA Grade A's Research stream
(zero content ingested — DECIDE-31 only covered General stream), and where does it, UPSC
CSE's Economics Optional, RBI DEPR, and UPSC IES genuinely overlap enough to cross-link
canonical topics (DECIDE-19's mechanism) rather than each carrying a separate vocabulary?
**Finding:** Checked 6 major coaching sources (Adda247, careerpower, Oliveboard, ixamBee,
Testbook, EduTap) — **none carry any PFRDA Research-stream PYQ content**, all stop at
General/Finance/Rajbhasha streams. Likely cause: the stream has only ~2 vacancies nationally,
too small a market for a coaching-site PYQ product to exist. Real syllabus (11 topics, not
10 — Statistical Quality Control is a genuine 11th item) confirmed against the official
notification, but actual tested depth/style is honestly unverifiable, not guessed at.
Built a full cross-exam overlap/depth-mismatch table across PFRDA Research, UPSC Eco
Optional, RBI DEPR (found to be just a placeholder registration, no real paper/topic
structure — see DECIDE-32), and IES's existing 156-topic taxonomy (spot-checked, still
accurate). Proposed reusing `rbi_gradeb`'s existing-but-unlinked canonical topics
(`macro`/`micro`/`is_lm`/`growth`/`pub_finance`/`intl_econ`/`env_econ`) across eco_optional_1,
IES, and DEPR; a new `indian_economy_structural` topic (deliberately separate from
`rbi_gradeb`'s thinner, data-tracking-flavored `indian_econ`) for eco_optional_2 + IES
`ge_04`; and flagged PFRDA Research ↔ RBI DSIM as a plausible but *unverified* depth match
(near 1:1 syllabus-name overlap) — recommended notes-only, not a hard link, given zero real
PFRDA Research PYQ evidence exists to confirm it.
**Applied to:** DECIDE-32 executed this plan directly — registered real RBI DEPR + a new RBI
DSIM exam (the notification RBI's own CAPTCHA-gated page had blocked this research pass from
finding), reused `rbi_gradeb`'s canonical topics as proposed, and confirmed the
`indian_economy_structural` split was correct (`indian_econ`'s real existing children turned
out to be exactly "current-developments" flavored, not structural — the DECIDE-29 depth trap,
caught before it happened). PFRDA Research ↔ DSIM left unlinked, notes-only, per this
research's own recommendation.

Full detail (per-topic PYQ-search log, the complete overlap table, and the original DEPR
Phase-II structural-dispute finding this research couldn't resolve on its own):
`docs/research/RESEARCH-11-pfrda-research-stream-sync.md`
