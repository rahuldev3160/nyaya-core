# RESEARCH-11 — PFRDA Grade A Research stream: real depth/PYQ signal + cross-exam topic-sync plan for 4 economics/statistics exams

**Date:** 2026-09-16 | **Session:** external (research-only pass) | **Status:** Proposal, not yet actioned

**Scope:** Research-only. No writes to `core.db`, no seed/migration script run, no new
`topics`/`exam_topics` rows created. This document is a proposal for Rahul to review before
any schema/data change.

**Exams covered:** `pfrda_gradea` (Research stream, papers `phase1_p2_research`/
`phase2_p2_research`), `upsc_cse` (Economics Optional, papers `eco_optional_1`/
`eco_optional_2`), `rbi_depr` (registered exam row, zero papers/topics), `upsc_ies`
(papers `ge_01`–`ge_04`, 156 topics, used as comparison ground truth).

**DB state confirmed before researching (read-only queries against `data/core.db`):**
- `pfrda_gradea`/`phase1_p2_research` and `phase2_p2_research`: **11** flat topics (not 10 —
  the real syllabus has 11 lines; "Statistical Quality Control" is a distinct 11th item),
  all `weight = 1.0` placeholder, no children/subtopics. Topic ids: `pfrda_probability_theory`,
  `pfrda_descriptive_statistics`, `pfrda_probability_distributions`,
  `pfrda_statistical_inference`, `pfrda_sampling_techniques`, `pfrda_hypothesis_testing`,
  `pfrda_economic_statistics`, `pfrda_time_series_analysis`, `pfrda_operations_research`,
  `pfrda_statistical_quality_control`, `pfrda_statistical_computing`.
- `upsc_cse`: `papers` already has rows for `eco_optional_1`/`eco_optional_2` (registered),
  but **zero** `exam_topics` rows exist for either — confirmed empty.
- `rbi_depr`: the **exam row exists** (`institution_id='rbi'`, name "RBI DEPR (Department of
  Economic and Policy Research)") but **zero rows in `papers` and zero in `exam_topics`** —
  it's a placeholder exam registration only, no taxonomy or paper structure yet. Any linking
  plan for DEPR is blocked on registering its papers first (out of this doc's scope).
- `upsc_ies`: 156 real topics across `ge_01` (41, General Economics I — micro theory + math
  methods), `ge_02` (39, General Economics II — macro theory + international + national
  income), `ge_03` (23, General Economics III — public finance/industrial/environmental/
  planning), `ge_04` (53, Indian Economics — agriculture/industry/labour/poverty/trade/
  federal finance). Spot-checked against the real, long-standing official IES syllabus
  structure — still an accurate match, no drift found.
- `rbi_gradeb` (General/DR, NOT DEPR — checked for contrast per the task's warning that
  these are different exams): 29 topics, `_all` paper, real recency-weighted frequencies
  (0.01–1.0). Top-level topics use short unprefixed ids already following the canonical
  convention: `macro`, `micro`, `is_lm`, `mundell_fleming`, `growth`, `pub_finance`,
  `intl_econ`, `env_econ`, `indian_econ`, `quant`, `welfare_game`, `market_structures`,
  `consumer_theory`, `production_theory`, `money_banking`, `qtm_monetary`,
  `phillips_lucas`. **Important, corrects an assumption in the task brief and in
  HANDOFF.md's own wording:** none of these are currently linked to any other exam via
  `exam_topics` — `rbi_gradeb`'s macro/micro cluster is *not* actually shared with
  `upsc_cse`/`upsc_ies` today; it only sounds shared because the ids are named in the
  unprefixed canonical style. The only real existing cross-exam linking in the whole DB is
  the 10-topic Prelims-GS cluster (`polity`, `economy`, `csat`, etc.) across
  `upsc_cse`+4 State PCS exams. This changes the size of the task: there is no existing
  postgrad-econ link to audit for correctness — it has to be built from nothing.

---

## 1. PFRDA Research stream — real findings (per-topic depth/style/PYQ availability)

**Headline finding: real PYQ content for this stream does not exist on any of the 6
coaching sources checked (Adda247/careerpower, Oliveboard ×2 pages, ixamBee ×2 pages,
Testbook, EduTap), and this isn't a search-technique failure — every one of these sources
explicitly documents PFRDA Grade A PYQs by stream and stops at General/Finance/Rajbhasha.**
This is the same conclusion DECIDE-31 already reached from the supply side (all 3 real
paper-books on disk are General-stream) — this pass confirms it from the demand side too:
the coaching industry itself has not produced Research-stream PYQ compilations. The
`ixamBee` page for this stream is even titled "Research (Economics **and** Statistics)"
and describes only 2 total vacancies (1 SC + 1 UR) for the entire stream nationally — a
candidate pool small enough that it plausibly doesn't justify a coaching site building a
dedicated recollection product, unlike General stream's much larger applicant base. Given
this, the honest position for every one of the 11 topics below is: **syllabus and format
are real and verifiable; per-topic PYQ depth/style is not verifiable from any source found
and should not be asserted as known.**

**What is real and verifiable (from the notification, echoed consistently by Oliveboard's
Research-stream syllabus page and careerpower's separate breakdown):**
- Research is **one combined stream** covering both Economics and Statistics backgrounds at
  the eligibility level (Master's degree in Economics, Statistics, Commerce, Business
  Administration, Econometrics, Finance, or Mathematics, plus a related PG diploma) — not
  two separate posts with separate syllabi. The 11-topic list already in the DB **is** the
  real, complete Phase 1 Paper 2 / Phase 2 Paper 2 syllabus (same syllabus both phases,
  matching DECIDE-30's framing) — no missing topics found, no extra topics found.
- **Format, both phases:** 50 MCQs, 100 marks, 40 minutes, 1/4 negative marking. This is a
  hard, real constraint: 48 seconds per question on average. Whatever the real cognitive
  depth of the syllabus wording, the actual tested format is fast objective recall/
  computation, not derivation or proof — structurally closer to PFRDA General's MCQ format
  than to IES's or RBI DEPR's descriptive answer format, **regardless of topic overlap**.
  This is a second axis (format), separate from DECIDE-29's depth axis, worth tracking
  independently in the linking plan below.
- **Eligibility floor is genuinely postgraduate** (Master's degree required) — this is the
  one concrete piece of evidence that rules out a repeat of the exact PFRDA-General trap
  (DECIDE-29's UG-101 finding). It does not *prove* the tested depth matches IES/RBI/CSE's
  postgrad theory papers — a Master's-eligibility, 48-second-MCQ exam can still test at a
  shallower operational level than a 3-hour descriptive paper — but it removes the strongest
  reason to assume a UG/PG mismatch outright.

**Per-topic notes (syllabus-real, PYQ-unverified for all 11):**
| Topic (DB id) | Real syllabus scope | PYQ signal found |
|---|---|---|
| `pfrda_probability_theory` | Basic probability, conditional probability, Bayes' theorem, random variables | None |
| `pfrda_descriptive_statistics` | Central tendency, dispersion, skewness/kurtosis | None |
| `pfrda_probability_distributions` | Binomial, Poisson, Normal and other standard distributions | None |
| `pfrda_statistical_inference` | Point/interval estimation | None |
| `pfrda_sampling_techniques` | Probability/non-probability sampling methods | None |
| `pfrda_hypothesis_testing` | Z, t, chi-square, F-tests | None |
| `pfrda_economic_statistics` | Index numbers, national income statistics (per general Economic Statistics usage — not confirmed PFRDA-specific) | None |
| `pfrda_time_series_analysis` | Time series components/methods | None |
| `pfrda_operations_research` | Not itemized further in any source found (no LP/transportation/queuing breakdown recovered) | None |
| `pfrda_statistical_quality_control` | Not itemized further in any source found | None |
| `pfrda_statistical_computing` | Not itemized further in any source found | None |

No fabricated depth claims are made for any of the 11 — where a row says "None," that is
the real state of available evidence, not an oversight.

**Sources:** [careerpower.in PFRDA Grade A syllabus](https://www.careerpower.in/pfrda-grade-a-syllabus.html), [ixamBee Research Economics & Statistics](https://www.ixambee.com/exams/pfrda-assistant-manager-research-economics-and-statistics), [Oliveboard PFRDA syllabus](https://www.oliveboard.in/blog/pfrda-assistant-manager-syllabus/), [EduTap PFRDA PYQs](https://edutap.in/pfrda-grade-a/previous-year-paper/), [Testbook PFRDA PYQs](https://testbook.com/blog/pfrda-assistant-manager-previous-year-question-paper/), [Oliveboard PFRDA PYQs](https://www.oliveboard.in/blog/pfrda-assistant-manager-previous-year-paper/), [ixamBee PFRDA PYQs](https://www.ixambee.com/previous-year-question-paper/pfrda-grade-a).

---

## 2. UPSC CSE Economics Optional — findings

Real, well-documented, decades-old syllabus (Vajiram & Ravi's syllabus page, cross-checked
against long-standing knowledge of UPSC's own syllabus text — stable subject, low drift
risk). **Zero topics currently in the DB** for `eco_optional_1`/`eco_optional_2` despite
both papers already being registered rows in `papers`.

**Paper I — Advanced Economic Theory** (postgrad depth, descriptive/derivation format):
- Advanced Microeconomics: Marshallian/Walrasian price determination, distribution theories
  (Ricardo/Kaldor/Kalecki), market structures (monopolistic competition/duopoly/oligopoly),
  welfare criteria (Pareto, Hicks-Kaldor, Scitovsky, Arrow's theorem, Sen's social welfare
  function)
- Advanced Macroeconomics: Classical/Keynesian (IS-LM)/neoclassical-synthesis/new-classical,
  interest rate theories
- Money, Banking & Finance: money demand/supply, quantity theory (Fisher/Pigou/Friedman),
  Keynesian money demand, monetary management, central bank-treasury relations, public
  finance stabilization/allocation/distribution roles, taxation/crowding-out/public debt
- International Economics: comparative advantage, terms of trade, product-cycle/strategic
  trade theory, trade-as-growth-engine, tariffs/quotas, BoP adjustment, fixed/floating
  exchange rates, WTO (TRIMS/TRIPS)
- Growth & Development: Harrod/Lewis/Solow/Romer models, balanced/unbalanced growth, human
  capital, structural change (Myrdal/Kuznets), HDI, environmental sustainability

**Paper II — Indian Economy** (structural/historical depth, India-specific):
- Pre-independence: land systems, commercialization of agriculture, drain theory, railways
- Post-independence pre-1991: Vakil/Gadgil/V.K.R.V. Rao, land reforms, Green Revolution,
  industrial composition, poverty/inequality
- Post-1991: agricultural reforms, WTO/TRIPS/TRIMS/GATS/EXIM, FDI, exchange rate regimes,
  FRBM, RBI's evolving role, 73rd/74th amendment decentralization, MGNREGA

**Format:** fully descriptive, 250 marks/paper, 500 total — same descriptive-derivation
format as IES's General Economics papers, unlike PFRDA Research's MCQ format.

Source: [Vajiram & Ravi — UPSC Economics Optional Syllabus](https://vajiramandravi.com/upsc-exam/upsc-economics-syllabus/).

---

## 3. RBI Grade B DEPR — findings (real but genuinely conflicting on Phase 2 structure)

**Phase 1 — consistent across both sources found:** two papers, Paper I Economics
(Objective, 100 marks, 120 min), Paper II English (Descriptive, 100 marks, 120 min).
**This is a separate, DEPR-specific Phase 1, not the same paper as `rbi_gradeb` General/
DR's Phase 1** (which is a 4-section GA/Quant/English/Reasoning objective screen) —
confirms the task brief's suspicion was right to check rather than assume.

**Phase 1 Economics syllabus (careerpower/adda247, consistent, and near-identical in
wording to `rbi_gradeb`'s already-seeded canonical topics):** Microeconomics, Theories of
employment/output/inflation, Monetary economics, IS-LM model, Schools of economic thought,
International Economics, Economic Growth & Development, Public Finance, Environmental
Economics, Quantitative Methods in Economics, Current Developments in the Indian Economy.

**Phase 2 — the two sources genuinely disagree, flagged honestly rather than picked
arbitrarily:**
- careerpower.in: Paper II Economics (100 marks, 180 min) + Paper III English (100 marks,
  90 min) — no separate Statistics paper, no Micro/Macro split.
- adda247.com: Paper I Microeconomics (100 marks, 120 min) + Paper II Macroeconomics (100
  marks, 120 min) — no English paper in Phase 2 at all, Micro/Macro split into two papers.

Neither source could be corroborated against a third; the official RBI notification PDF
was not reachable (opportunities.rbi.org.in serves a CAPTCHA to automated fetches; direct
guesses at rbi.org.in press-release URLs and several coaching-site DEPR-specific pages
returned 404s). **This is a real, open gap — do not treat either Phase 2 structure as
confirmed.** Before registering `rbi_depr`'s papers in the DB (a prerequisite for any
linking, since zero papers exist today), Rahul should source RBI's own official DEPR
recruitment notification directly rather than relying on either scraped variant.

**What both sources agree on regardless of exact paper split:** Phase 2 content is
Microeconomics + Macroeconomics at "based on the Master's Degree examination in Economics
of any Central University" depth — i.e., the same postgrad theory depth as UPSC CSE Eco
Optional Paper I and IES's `ge_01`/`ge_02`, described in almost the same vocabulary as
`rbi_gradeb`'s existing canonical `macro`/`micro`/`is_lm` topics. **This is the strongest,
most confidently real cross-exam signal found in this whole research pass** — independent
of the Phase 2 paper-count ambiguity.

Sources: [careerpower.in RBI Grade B syllabus](https://www.careerpower.in/rbi-grade-b-syllabus.html), [adda247.com RBI Grade B syllabus](https://www.adda247.com/jobs/rbi-grade-b-syllabus/), [bankersadda.com RBI Grade B syllabus](https://www.bankersadda.com/rbi-grade-b-syllabus/) (General/DR only, used for contrast).

---

## 4. UPSC IES — comparison spot-check (not re-researched from scratch, per task scope)

156 real topics, structure confirmed still accurate against the long-standing official IES
pattern:
- `ge_01` (41 topics) — General Economics I: consumer demand theory (7 children incl.
  `slutsky_theorem`, `revealed_preference`, `nash_equilibrium`), production/distribution/
  value theory, **`mathematical_methods`** (calculus, optimisation, linear
  algebra/matrices, **`linear_programming`**, **`input_output_model`**), **
  `statistical_econometric_methods`** (5 children: central tendency/dispersion/correlation/
  regression, time series/index numbers, multivariate analysis [ANOVA/Factor/PCA/
  Discriminant], income inequality [Lorenz/Gini], regression diagnostics
  [heteroscedasticity/autocorrelation/multicollinearity]), welfare economics.
- `ge_02` (39 topics) — General Economics II: growth/development theory, employment-
  output-inflation-money theory, international economics (incl. `mundell_fleming_model`,
  BoP disequilibrium/adjustment), national income accounting, economic thought.
- `ge_03` (23 topics) — General Economics III: public finance, industrial economics,
  environmental economics, state/market/planning.
- `ge_04` (53 topics) — Indian Economics: agriculture/rural development (4 children),
  industry, labour, poverty/unemployment/HD, foreign trade, federal finance, budgeting/
  fiscal policy, money & banking (India), urbanisation/migration, development planning
  history.

This is the deepest, most granular real taxonomy of the four exams by a wide margin (156
vs. PFRDA Research's 11, UPSC CSE's 0, RBI DEPR's 0) and the only one with real subtopic-
level structure already built. It functions as the natural depth benchmark for judging
whether other exams' content is "the same depth" — a topic only merits linking to an IES
node if it operates at IES's level of derivation/technique, not just shares a subject name.

---

## 5. Cross-exam overlap / depth-mismatch table

| Subject cluster | PFRDA Research | UPSC CSE Eco Optional | RBI DEPR | UPSC IES | Verdict |
|---|---|---|---|---|---|
| **Micro Theory** (value/production/distribution/consumer demand/welfare/market structures) | Not in syllabus at all | Paper I, full postgrad descriptive | Phase 1 objective + (likely) Phase 2 descriptive, "Master's degree" depth | `ge_01`, full postgrad descriptive, most granular of all four | **Link CSE+IES+DEPR.** PFRDA excluded — genuinely absent from its syllabus, not a depth question. |
| **Macro Theory** (IS-LM, growth, money/monetary, employment-output-inflation, international/BoP) | Not in syllabus at all | Paper I, full postgrad descriptive | Phase 1 objective (near-identical wording to `rbi_gradeb`'s canonical `macro`/`is_lm`/`mundell_fleming`/`growth`) + Phase 2 (structure uncertain, see §3) | `ge_02`, full postgrad descriptive | **Link CSE+IES+DEPR**, reusing `rbi_gradeb`'s already-existing canonical ids as the shared rows (see §6). PFRDA excluded, same reason as Micro. |
| **Public Finance / Environmental Economics** | Not in syllabus | Paper I (public finance stabilization/allocation/distribution) | Phase 1 objective explicitly lists both | `ge_03` | **Link CSE+IES+DEPR**, reuse `rbi_gradeb`'s `pub_finance`/`env_econ`. |
| **Indian Economy (structural/historical)** | `pfrda_economic_statistics` only touches India data as a statistical-technique example, not structural content | Paper II, full postgrad descriptive, India-specific history | Phase 1 objective mentions only "Current Developments in Indian Economy" — much thinner than CSE/IES's structural-history treatment | `ge_04`, full postgrad descriptive, most granular | **Link CSE Paper II + IES `ge_04` only.** DEPR's thin current-events framing and `rbi_gradeb`'s already-seeded, thinner `indian_econ` (3 data-tracking children) are a **depth trap of the same shape as DECIDE-29** — do NOT fold them into this cluster; keep separate. |
| **Probability / Statistical Inference / Distributions / Sampling / Hypothesis Testing** | 6 of the 11 syllabus topics, MCQ format, PYQ-unverified (§1) | Not tested | Uncertain — one Phase-2 variant found implies no separate Statistics paper at all (§3) | Only indirectly, folded into `statistical_econometric_methods`'s regression-diagnostics children — not a matching granularity | **Do NOT link yet.** This is exactly DECIDE-29's trap shape: plausible-sounding overlap, zero real PYQ evidence to confirm actual tested depth for PFRDA's side, and the one exam most likely to share it (RBI DEPR) has an unconfirmed Phase 2 structure. Revisit once a real Research-stream paper-book exists (same open item HANDOFF.md already flags) and once DEPR's Phase 2 is confirmed from the official notification. |
| **Time Series Analysis** | `pfrda_time_series_analysis`, MCQ format | Not a dedicated topic | Unconfirmed | `time_series_index_numbers` child of `statistical_econometric_methods`, descriptive format | **Tentative link, low confidence** — same underlying statistical topic, but format differs (MCQ speed-recall vs. descriptive derivation) and PFRDA's real tested depth is unverified. Reasonable to link now for retrieval-grounding purposes (a real IES time-series explanation chunk is genuinely useful PFRDA-Research prep material) but flag the caveat inline via `notes` rather than treating it as equivalent-depth. |
| **Operations Research (LP/transportation/queuing/SQC)** | `pfrda_operations_research`, `pfrda_statistical_quality_control` — full syllabus items, no further breakdown found | Not tested | Not tested | Only `linear_programming`/`input_output_model` (children of `mathematical_methods`), narrow "LP in economics" framing, not full OR | **Tentative, narrow link only** at the LP/input-output sub-concept — PFRDA's broader OR/SQC scope (queuing, simulation, control charts, PERT/CPM presumably) has no real match anywhere in these four exams; leave the rest unlinked and genuinely unique to PFRDA. |
| **Economic Thought / Schools of Thought** | Not tested | Implicit in Paper I's classical/Keynesian/neoclassical framing, not a standalone topic | Phase 1 objective explicitly lists "Schools of economic thought" | `economic_thought`, standalone topic, already an unprefixed canonical-shaped id | **Link DEPR + IES** to IES's existing `economic_thought` id; CSE's coverage is real but embedded inside other Paper I topics rather than standalone — link at a looser level or leave CSE out until its own taxonomy is built and a standalone node exists there. |
| **English / Descriptive Writing** | Phase 2 Paper 1, descriptive | Essay paper (separate from Eco Optional, same exam) | Phase 1 Paper II + Phase 2 (one variant), descriptive | Has its own English paper (outside `ge_01`-`04`) | Out of this task's economics/statistics scope — flagged only as a secondary future opportunity, not analyzed further here. |

---

## 6. Concrete proposed topic-linking plan

**Principle applied throughout:** reuse `rbi_gradeb`'s existing unprefixed canonical ids
(`macro`, `micro`, `is_lm`, `mundell_fleming`, `growth`, `pub_finance`, `intl_econ`,
`env_econ`) as the shared rows wherever content matches, per DECIDE-19's `reused_topics`
mechanism — mint new ids only where nothing suitable exists yet. No `pfrda_*`-prefixed
Research-stream id is proposed for linking (see the "do NOT link" row in §5) — all 11 stay
PFRDA-only pending real PYQ evidence.

**A — High confidence, recommend actioning once `rbi_depr` has real papers registered:**
1. `macro` (existing, currently `rbi_gradeb`-only) → add `exam_topics` rows for
   `upsc_cse`/`eco_optional_1`, `upsc_ies`/`ge_02`, `rbi_depr`/(its real Phase-1 and
   Phase-2 economics papers, once registered). *Justification: near-identical syllabus
   wording across all four sources found in §3, all four genuinely postgrad-descriptive
   depth except PFRDA which doesn't test this subject at all.*
2. `micro` (existing) → same treatment, linking to `eco_optional_1`, `ge_01`, `rbi_depr`.
   *Justification: same as macro — Marshallian/Walrasian price theory, distribution
   theories, welfare criteria all appear near-verbatim across CSE/IES/DEPR's real
   syllabi.*
3. `is_lm` and `mundell_fleming` (existing, currently only linked to `rbi_gradeb`) → link
   to `eco_optional_1`, `ge_02`, `rbi_depr`. *Note: IES currently has its own separate
   `mundell_fleming_model` child under `balance_of_payments` — recommend re-parenting that
   IES child under the shared `mundell_fleming` row in a later migration rather than
   maintaining two ids for the same concept, but that re-parenting is a bigger structural
   change than this research doc should decide unilaterally — flagged as a follow-up, not
   bundled into this proposal.*
4. `growth`, `pub_finance`, `intl_econ`, `env_econ` (all existing) → same link pattern to
   `eco_optional_1`, the matching `ge_0x` paper, and `rbi_depr`.
5. `indian_economy_structural` (**new id, deliberately distinct from `rbi_gradeb`'s
   existing thinner `indian_econ`** — do not reuse that id, see the depth-trap flag in §5)
   → link to `upsc_cse`/`eco_optional_2` and `upsc_ies`/`ge_04` only.

**B — Tentative, lower confidence, recommend flagging with a `notes` caveat rather than
linking silently if actioned:**
6. `time_series_analysis` (new id) → link `pfrda_gradea`/`phase1_p2_research`+
   `phase2_p2_research` and `upsc_ies`/`ge_01` (its existing `time_series_index_numbers`
   child could point up to this new parent, or link directly — Rahul's call). Caveat: MCQ-
   speed-recall vs. descriptive-derivation format difference, PFRDA depth unverified.
7. `linear_programming` (new id, narrow scope only — not the full PFRDA
   `pfrda_operations_research`/`pfrda_statistical_quality_control` breadth) → link
   `pfrda_gradea` Research papers and `upsc_ies`'s existing `linear_programming` child.
8. `economic_thought` (existing IES id) → link `rbi_depr` once its papers exist. Leave
   `upsc_cse` out for now — its coverage is real but not a standalone syllabus node yet.

**C — Explicitly rejected / do not link (documented so a future session doesn't
re-propose them without re-checking):**
- Any of PFRDA Research's other 9 topics (`pfrda_probability_theory`,
  `pfrda_descriptive_statistics`, `pfrda_probability_distributions`,
  `pfrda_statistical_inference`, `pfrda_sampling_techniques`, `pfrda_hypothesis_testing`,
  `pfrda_economic_statistics`, `pfrda_statistical_computing`,
  `pfrda_statistical_quality_control` minus the narrow LP link above) — no real PYQ
  evidence anywhere to confirm depth; same trap shape as DECIDE-29.
- `rbi_gradeb`'s existing `indian_econ` → CSE/IES Indian Economy content — real depth
  mismatch (3 data-tracking children vs. two full structural-history papers).
- `rbi_gradeb`'s `welfare_game` → IES's `welfare_economics` — scope mismatch (RBI's node
  bundles welfare theorems with game theory; IES keeps `nash_equilibrium` as a separate
  child elsewhere) — would misrepresent both exams' actual coverage if force-linked.

**Prerequisite blocking all `rbi_depr` links (A1–A4, C's DEPR mention):** `rbi_depr` has
zero rows in `papers` today. Before any of the above can be implemented for DEPR, its real
paper structure needs to be registered — and per §3, the two sources found disagree on
Phase 2's shape, so this needs the actual official RBI DEPR notification, not another
coaching-site scrape, before registration.

---

## Summary of what changed in understanding this session

The task brief's framing (and HANDOFF.md's own wording) assumed `rbi_gradeb`'s canonical-
shaped macro/micro topic ids were already "shared" across IES/RBI/CSE — DB verification
found they are not; only the Prelims-GS cluster is actually cross-linked today. This
research corrects that and gives the actual 8-topic reuse plan in §6-A as the real path to
delivering the sharing DECIDE-19 was built for, gated on Rahul's review before any write.
