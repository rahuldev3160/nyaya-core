# CLAUDE.md

Guidance for working in this repo. Read `PROJECT.md` → `docs/FOUNDATION.md` → `HANDOFF.md`
before starting any session.

## Project
Nyaya Core — unified, exam-agnostic RAG data platform for the Nyaya product family
(Recall, Scribe, future products). See `PROJECT.md`.

## Stack
| Layer | Technology |
|---|---|
| Ingestion | Python, parsers ported from Devthorium (pdfplumber/pdf2image/pytesseract/python-docx/textutil/BeautifulSoup) |
| Chunking | Custom header-aware two-stage splitter (`SyllabusChunker`) |
| Embeddings | Ollama `nomic-embed-text` (768-dim, local) |
| Vector + FTS store | LanceDB, embedded, `data/lancedb/` |
| Structured store | SQLite, `data/core.db` |
| Reranking | FlashRank (in-process cross-encoder) |
| API | FastAPI, internal only |

## Sibling projects
- `../Devthorium` — Nyaya Recall. Calls this platform's API live (same machine). Its
  `scripts/parsers/`, `scripts/ingest_pyq.py` classification pattern, and `scripts/chunker.py`/
  `embedder.py` (being retired) are the direct ancestors of this repo's ingestion code.
- `../Descriptive-exams` — Nyaya Scribe. Consumes via batch sync (Railway can't reach a
  local-only service) — never add a live API dependency from Scribe to here without
  revisiting DECIDE-03 in `docs/decisions.md`.

## Audit system — always check first
1. Read `HANDOFF.md` — exact next step, open items
2. Read `docs/MASTER_INDEX.md` — decisions/bugs/risks catalogue
3. Full detail in `docs/decisions.md`, `docs/bugs.md`, `docs/risks.md`, `docs/research.md`

Register every DECIDE/BUG/RISK/RESEARCH entry at the moment it's created, not at session
end — update `docs/MASTER_INDEX.md` in the same edit.

## Data dictionary
`docs/DATA_DICTIONARY.md` explains every table/field. `scripts/inventory.py` (once built)
shows what's actually indexed right now — run that, don't guess from the dictionary alone.

## Critical invariants
- `topic_id` is the join key between `chunks` (LanceDB) and `pyq_bank` (SQLite) — always a
  registry FK, never free text (DECIDE-04).
- `exams`/`papers`/`topics`/`content_types` are data-driven tables. A new exam is a row,
  never a code change, a new `Literal` value, or a hardcoded dict entry.
- **Naming (DECIDE-21):** `exam_id` = `{institution}_{exam}`, always the actual exam a
  candidate applies to, never a paper/subject within it — "UPSC" alone is never a full
  `exam_id` (UPSC runs CSE, IES, EPFO, CAPF...). `paper_id` is short and un-prefixed, scoped
  by `exam_id` via a composite key (`papers`' PK is `(exam_id, paper_id)`) — it never repeats
  the exam/institution identity. Full checklist in `docs/DATA_DICTIONARY.md`'s Naming
  conventions section — read it before registering any new exam.
- Chunking must never split a statute Article/Section or a math derivation/equation/table
  across a chunk boundary (Law/Econ Optional invariants from the source spec).
- Ingestion is incremental and idempotent — re-running after new uploads must only process
  new files (hash-based skip-list), never reprocess everything.

## Approval gates
See `docs/FOUNDATION.md` — always stop and flag before: deleting Recall's old pipeline,
touching Scribe's DB schema/migrations, large paid ingestion batches, anything that makes
this platform reachable by anyone but Rahul.

## Sound alert rule
Before asking Rahul for any approval: `afplay /System/Library/Sounds/Ping.aiff` first — he
studies in another window and won't see the terminal otherwise (established pattern from
sibling projects).
