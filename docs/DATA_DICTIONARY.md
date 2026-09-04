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

### `exams`
One row per exam. `exam_id` (PK), `name`, `created_at`. Adding a new exam = one INSERT,
no code change.

### `papers`
One row per paper within an exam. `paper_id` (PK), `exam_id` (FK), `name`. Nullable link
for exams without a paper concept.

### `topics`
The shared topic vocabulary. `topic_id` (PK), `exam_id` (FK), `name`, `parent_topic_id`
(nullable, for subtopic nesting). This is the join key between `chunks` and `pyq_bank`.

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
| `marks`, `word_limit` | Descriptive-only, null for MCQ |
| `source_type`, `verified_by`, `reviewed_at` | Same provenance fields as `chunks` |

---

## Naming conventions
- `*_id` fields are always the FK/PK pattern; never a display name.
- `content_type` vs `topic` are **independent axes** — a chunk's `content_type` says what
  kind of document it came from (a report vs. a textbook), its `topic_id` says what subject
  it's about. Don't conflate them.
- `source_type` is about **trust/provenance** (was this verified, AI-generated, official) —
  a third, independent axis from both of the above.
