# Data Dictionary

What every store, table, and field means. Read this whenever "what is X for" comes up.
For what's *actually* indexed right now (live counts), run `scripts/inventory.py` instead
of trusting this doc — this file explains structure and naming, not current contents.

---

## LanceDB — `data/lancedb/`, table `chunks`

Prose content: study material, official reports, current affairs, syllabus text. One row
per chunk (a few hundred words of source text + its embedding).

| Field | Meaning |
|---|---|
| `chunk_id` | `{exam_id}_{source_stem}_{page}_{idx}` — unique, human-readable, traceable back to the source file and page |
| `content` | The chunk's clean markdown text |
| `vector` | 768-dim embedding (Ollama `nomic-embed-text`) |
| `exam_id` | FK → `exams.exam_id` (e.g. `upsc_prelims_gs`, `ies_2026`) |
| `paper_id` | FK → `papers.paper_id` (nullable — not every exam has papers) |
| `topic_id` | FK → `topics.topic_id`. **Shared with `pyq_bank`** — this is what lets one topic query pull both explanation chunks and PYQs (see DECIDE-04) |
| `content_type` | FK → `content_types.type_id` (e.g. `study_material`, `official_report`, `current_affairs`) |
| `source_doc` | Original filename |
| `page_number` | 1-based page this chunk came from |
| `published_date` | When the source material was published/effective (nullable — evergreen content like NCERTs may not need this) |
| `source_type` | Provenance: `official_pyq` / `ai_generated` / `coaching_derived` / `self_notes` (same enum as Scribe's draft migrations m059-m063) |
| `verified_by` | Who confirmed this content is accurate (nullable until reviewed) |
| `reviewed_at` | When it was verified (nullable) |
| `section_id` | FK → `sections.section_id` — the parent this chunk belongs to (DECIDE-14) |
| `tags` | JSON dict — ad hoc extension metadata, no schema migration needed to add a new key (DECIDE-09) |
| `is_current` / `superseded_by` | Hard supersession flag for time-sensitive content (DECIDE-11) |
| `context_prefix` | The short LLM-written blurb prepended before embedding (DECIDE-13/Contextual Retrieval) — stored separately from `content` so citations point to real source text, not the blurb |

FTS index built on `content` (contextualized version, i.e. `context_prefix` + `content`) for
hybrid search (dense + BM25, fused via RRF).

### `sections` (in `core.db`, not LanceDB)
The parent-document layer for auto-merging retrieval (DECIDE-14). One row per Stage-1
markdown-header section (before the chunker's Stage-2 recursive sub-split) — NOT the whole
source document, to keep merged context within a sane token range.

| Field | Meaning |
|---|---|
| `section_id` | PK |
| `doc_id` | Which source document this section came from |
| `exam_id`, `topic_id`, `content_type` | Same FKs as `chunks` |
| `heading` | The markdown header text |
| `full_text` | The complete section text — what gets returned when chunks are auto-merged |
| `page_start`, `page_end` | Page range this section spans |

At retrieval: if ≥2 top-ranked chunks share a `section_id`, the engine substitutes this
section's `full_text` for those chunks (budget permitting) instead of returning disjoint
fragments.

---

## SQLite — `data/core.db`

### `institutions`
The real, queryable conducting-body dimension (DECIDE-22). `institution_id` (PK), `name`.
`exam_id`'s `{institution}_{exam}` naming (DECIDE-21) is a convention for humans reading an
id — this table is what makes "every exam UPSC conducts" a real `JOIN`, not a fragile
`exam_id LIKE 'upsc_%'` string match:
```sql
SELECT e.exam_id, e.name FROM exams e
JOIN institutions i ON e.institution_id = i.institution_id
WHERE i.institution_id = 'upsc';
```

### `exams`
One row per exam. `exam_id` (PK), `institution_id` (FK → `institutions`), `name`,
`created_at`. Adding a new exam = one INSERT, no code change.

### `papers`
One row per paper within an exam. PK is the **pair** `(exam_id, paper_id)` (DECIDE-21) —
`paper_id` alone is deliberately not globally unique, so "essay" can mean UPSC CSE's Essay
paper and, later, some other exam's Essay paper without collision — a child entity's key
shouldn't have to repeat its parent's identity. Not every exam has papers registered yet
(e.g. the 4 State PCS exams and `rbi_gradeb`/`upsc_ies`'s non-GE papers) — that's fine,
`exam_topics.paper_id` just stays at the `'_all'` sentinel until real paper-level content
shows up.

### `topics`
The shared, **exam-agnostic** topic vocabulary (DECIDE-19 — resolves DECIDE-32). `topic_id`
(PK), `name`, `parent_topic_id` (nullable, for subtopic nesting), `notes` (nullable
free-text — curator observations a source had, e.g. "Mundell-Fleming appeared TWICE in
2024"; NOT the `chunk_tags` EAV table, which is keyed by real chunk_id, a different
entity). A topic is a canonical real-world concept, not owned by any one exam — this is the
join key between `chunks` and `pyq_bank` (DECIDE-04), and it's what lets one RBI
monetary-policy chunk also ground IES prep, once both exams' `exam_topics` link to the same
`topic_id`.

### `exam_topics`
Junction table: which exam (and optionally which paper within it) a topic is relevant to,
and how much. `exam_id` + `paper_id` + `topic_id` (composite PK), `weight` (e.g. real PYQ
frequency where known — see `scripts/seed_topics.py`), `is_core` (boolean). `paper_id`
defaults to the sentinel `'_all'` (exam-wide, not one specific paper) — DECIDE-21, needed
once a single exam_id can have multiple papers (e.g. `upsc_cse`'s Essay paper shouldn't see
Prelims-only topics as valid classification candidates just because they share an exam_id).
A topic used by only one exam just has one row here — reuse costs nothing to not have.

### `content_types`
Registry of document *kinds*, independent of exam/topic. `type_id` (PK), `name`
(`mains_pyq`, `mcq_pyq`, `official_report`, `study_material`, `current_affairs`,
`monthly_report`, `yearly_report`, `model_answer`, `syllabus`), `is_time_sensitive`
(boolean — drives the recency boost in ranking for `current_affairs`/`monthly_report`/
`yearly_report`).

### `pyq_bank`
One table for both question formats, discriminated by `question_format`.

| Field | Meaning |
|---|---|
| `question_id` | PK |
| `exam_id`, `paper_id`, `topic_id` | Same FKs as `chunks` |
| `question_format` | `mcq` or `descriptive` |
| `year` | PYQ year |
| `question_text` | The question |
| `options`, `correct_option` | MCQ-only, null for descriptive |
| `statements` | MCQ-only, null for standalone-option MCQs and all descriptive questions. Populated when the question is statement-based ("how many of the following statements are correct") — the dominant real UPSC Prelims format. Getting this distinction right at extraction time is what makes `pyq_explanations` possible to generate correctly (DECIDE-23/BUG-04) |
| `marks`, `word_limit` | Descriptive-only, null for MCQ |
| `source_type`, `verified_by`, `reviewed_at` | Same provenance fields as `chunks` |

### `pyq_explanations`
One row per PYQ (1:1 with `pyq_bank` via `question_id`), generated by a separate, later,
on-demand batch job — never live during a timed quiz (DECIDE-23). Designed directly against
a real failure found in Nyaya Recall's equivalent feature (BUG-04: 100% of 904 generated
rows had every wrong-option field silently empty, because its schema forced independent
option notes onto statement-based questions where that shape doesn't apply).

| Field | Meaning |
|---|---|
| `question_id` | PK, FK → `pyq_bank.question_id` |
| `concept_summary` | Brief — always shown, whether the attempt was right or wrong |
| `detail` | JSON-encoded, discriminated by `option_format`: `standalone` (per-option rationale) or `statement_based` (per-statement rationale + a combination-rationale). Detailed — only shown on a wrong attempt |
| `elimination_strategy` | Nullable — real exam-technique reasoning (which options/statements a trained aspirant could eliminate immediately, and why). Not every question has a clean one |
| `grounding_chunk_ids` | JSON list — citations used to generate this explanation, so it can be checked against a real source rather than trusted as pure model recall |
| `model_version`, `generated_at`, `verified_by`, `reviewed_at` | Same provenance pattern as everything else in this schema |

### `user_attempts` (DECIDE-34)
Attempt-level log — one row per question Rahul actually answered via `scripts/quiz.py`.
The only per-user signal anywhere in nyaya-core; everything else in this schema describes
question/content, never what a user did with it.

| Field | Meaning |
|---|---|
| `attempt_id` | PK, autoincrement |
| `question_id` | FK → `pyq_bank.question_id` |
| `chosen_option`, `correct_option` | What was picked vs. what was graded correct **at the time of the attempt** — `correct_option` is copied here rather than re-joined at query time, so a later re-verification of `pyq_bank.correct_option` can't silently rewrite history |
| `is_correct` | 0/1, derived once at attempt time |
| `attempted_at` | ISO timestamp |

### `topic_coverage` (DECIDE-34)
One row per (`exam_id`, `topic_id`) actually attempted at least once — computed, not
measured directly. Recomputed by `scripts/quiz.py` at the end of every session from ALL
historical `user_attempts` for that topic, not just that session's. **An untested topic has
NO row here** (never a row of zeros) — `daily_priority.py` treats "no row" as
`coverage_depth = 0.0`, the layered-coverage skill's anti-false-positive rule (untested =
max urgency, never a fabricated default).

| Field | Meaning |
|---|---|
| `exam_id`, `topic_id` | Composite PK, FKs → `exams`/`topics` |
| `attempts_count` | Total historical attempts on questions tagged with this exact `topic_id` |
| `accuracy` | `correct / attempts_count`, 0-1 |
| `coverage_depth` | layered-coverage skill's Q3 depth rule: accuracy >= 0.75 -> 1.0 (fully covered); 0.45-0.74 -> accuracy (proportional); < 0.45 -> accuracy * 0.5 (penalised) |
| `last_computed_at` | ISO timestamp of the last recompute |

---

## Rules vs. data — where each actually lives
Two different things can be meant by "tracking a convention," and they're deliberately kept
in different places:
- **Real dimensions other queries need to join/filter/group on** — which institution runs
  an exam, which exam a paper belongs to, which topics an exam cares about — live as actual
  rows in `institutions`/`exams`/`papers`/`exam_topics`. These are queryable today with
  plain SQL (see `institutions`' example above); no separate registry needed, because they
  already are one.
- **The grammar for constructing a new id** ("exam_id = institution_exam", "paper_id is
  short and scoped by its exam", "topic_id is globally unique snake_case, no institution
  prefix") is documentation, not data — nothing at runtime needs to `SELECT` a naming rule,
  a person (or a future Claude session) needs to *apply* it correctly when adding a new
  registry row. It lives here, in this section, and in `CLAUDE.md`'s Critical invariants —
  the same place `docs/decisions.md`/`MASTER_INDEX.md` already track every other design
  decision. Duplicating prose rules into a database table would add a second copy to keep in
  sync for no query anything would ever run.

## Naming conventions
- `*_id` fields are always the FK/PK pattern; never a display name.
- `content_type` vs `topic` are **independent axes** — a chunk's `content_type` says what
  kind of document it came from (a report vs. a textbook), its `topic_id` says what subject
  it's about. Don't conflate them.
- `source_type` is about **trust/provenance** (was this verified, AI-generated, official) —
  a third, independent axis from both of the above.
- **`exam_id` = `{institution}_{exam}`, always the actual exam a candidate applies to, never
  a paper/subject within it** (DECIDE-21). "UPSC" alone is never a full `exam_id` — UPSC
  runs CSE, IES, EPFO, CAPF, etc., each a genuinely different exam
  (`upsc_cse`, `upsc_ies`, ...). Institution codes so far: `upsc`, `rbi`; bare state-name
  codes for State PCS since each state has exactly one relevant PCS exam
  (`uppcs`, `hpas`, `ukpsc`, `mppsc`).
- **`paper_id` is short and un-prefixed, scoped by its exam via a composite key** — never
  repeats the exam/institution identity (`essay`, not `upsc_cse_essay`). The pattern is
  `papers`' PK = `(exam_id, paper_id)`; anywhere else `paper_id` appears (`pyq_bank`,
  `exam_topics`, `ChunkMetadata`), `exam_id` is always present alongside it, so the pair is
  what actually identifies a paper — same reasoning as why `topic_id` doesn't need an exam
  prefix (DECIDE-19).
- New exam checklist (so this stays consistent as exams are added): (1) confirm the real
  conducting institution and the exam's own name — don't assume "UPSC" is specific enough;
  (2) `exam_id` = institution_exam, both short lowercase codes; (3) if the exam has multiple
  distinct papers with materially different content, register them in `papers` with short
  paper_ids, not as separate exam_ids; (4) if none exist yet, that's fine — `exam_topics`
  defaults to `'_all'` until real paper-level content arrives.
