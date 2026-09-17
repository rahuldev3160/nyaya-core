# Bugs

### BUG-01 — Scribe truncates grounding chunks to 400 chars {#bug-01}
**Date:** 2026-09-04 | **Session:** S2 | **Fixed:** No — root cause found, fix scheduled

**Root cause:** `Descriptive-exams/scripts/generate_answers.py` truncates each of the 4
retrieved ChromaDB chunks to 400 characters (~100 tokens) before injecting into the Claude
prompt — ~400 tokens of total grounding for a full model-answer or MCQ-explanation
generation. This is the confirmed cause of Rahul's "explanations too short" observation.
**Fix:** Not yet applied — lives outside this repo (Descriptive-exams). Scheduled for
Nyaya Core Phase 4 (batch sync + Scribe grounding), where `generate_answers.py` is rewired
to pull from Nyaya Core's `/search` with a caller-supplied, generous token budget
(DECIDE-08) instead of a hardcoded 400-char slice.
**Lesson:** Never hardcode a chunk/token truncation shared across different-stakes call
sites — logged as L-DEV-41 for reuse beyond this project.

### BUG-02 — Ported parsers discarded page boundaries {#bug-02}
**Date:** 2026-09-06 | **Session:** S4 | **Fixed:** Yes

**Root cause:** Phase 0 ported all 7 parser modules from Devthorium "verbatim" and verified
only that they imported cleanly — not their return shape against Nyaya Core's own schema.
`digital_pdf.py`/`scanned_pdf.py`/`handwritten_pdf.py` each joined every page's text into
one `"\n\n"`-separated string before returning, discarding which page any given line came
from. Devthorium never needed page numbers (no citations), so this was invisible there.
Nyaya Core's `ChunkMetadata.page_number` and `sections.page_start/page_end` both require it.
**Fix:** All 7 parsers now return `list[tuple[int, str]]` — `(page_number, page_text)`
pairs, 1-indexed. The 3 PDF-family parsers derive real per-page numbers from `pdfplumber`/
`pdf2image`'s page iteration. The 4 formats with no native page concept (docx, .pages, html,
.textClipping) return a single `(1, full_text)` page, kept in the same shape so the chunker
has one uniform interface regardless of source format. Caught and fixed before the chunker
(the first real consumer) was written — zero migration cost.
**Lesson:** "Verified it imports" is not "verified its output shape matches the schema
downstream code depends on." Check a ported function's actual return contract against the
new consumer's needs, not just that the function is callable.

### BUG-03 — `\b` regex silently failed to match a year after an underscore {#bug-03}
**Date:** 2026-09-06 | **Session:** S4 | **Fixed:** Yes

**Root cause:** `scripts/ingest.py`'s filename-year inference used
`re.compile(r"\b(19|20)\d{2}\b")`, expecting it to match "2023" in a filename like
`Economic_Survey_2023.pdf`. `\b` only fires at a transition between a word character (`\w`
— letters, digits, AND underscore) and a non-word character. Since `_` and `2` are both
`\w`, there's no boundary between them — the regex silently matched nothing and
`published_date` was always `None` for underscore-separated filenames, the single most
common naming convention for downloaded reports.
**Fix:** Replaced with `(?<!\d)(19|20)\d{2}(?!\d)` — a digit-only lookaround instead of a
word-boundary, so it only excludes a year embedded inside a longer number, not one
preceded by `_`/`-`/space. Caught by a unit test (`tests/test_ingest.py::
test_infer_published_date_from_filename_year`) written *before* assuming the regex worked.
**Lesson:** `\b` in a filename/identifier context is a trap — real-world names use `_`/`-`
as word separators, both of which `\b` treats as no boundary at all against adjacent
alphanumerics. Prefer explicit lookarounds (`(?<!\d)...(?!\d)`) over `\b` whenever the
surrounding characters might include `_` or `-`, and never trust a regex's happy path
without testing it against realistic filenames.

### BUG-04 — Recall's PYQ explanation feature: 100% of wrong-option fields silently empty {#bug-04}
**Date:** 2026-09-06 | **Session:** S4 | **Fixed:** No (found in Devthorium/Recall, not this
repo — logged here because it directly shapes the `pyq_explanations` design about to be built)

**Root cause:** Recall's `prompts/pyq_explanation.txt` schema (`option_a_note`-
`option_d_note`) assumes four independently-meaningful factual options. Most real UPSC
Prelims MCQs are statement-based ("how many statements are correct," options like "Only
one"/"Only two"/"All three") — there's nothing coherent to say about why "Only two" is wrong
as a standalone concept under that schema. The model silently omits those fields for that
format; nothing in `generate_pyq_explanations.py` detects the omission or refuses to write
an incomplete row. Confirmed against the live table: all 904 rows have empty wrong-option
fields — systematic, not occasional. Full detail: Devthorium's `ISSUES.md` ISSUE-029.
**Fix:** Not applied to Recall's own table (out of scope for this repo). Designing
nyaya-core's `pyq_explanations` to not repeat this: (1) detect statement-based vs.
standalone-option format at PYQ-extraction time and branch the schema accordingly instead
of forcing one shape on both; (2) validate every required field is populated before writing
a row — treat a partial LLM response as `ReviewNeededError`, never a silent partial write
(same principle already applied to chunk enrichment); (3) ground the explanation in
retrieved content and cite it, rather than pure model recall with no verification.
**Lesson:** A structured-output schema that fits the common case can silently fail on a
different-but-frequent case without ever raising an error — the model just omits the
fields that don't apply, and nothing downstream distinguishes "correctly empty" from
"silently failed." Validate structured LLM output against what the input actually requires,
not just against "did I get valid JSON back." Cross-project lesson logged as GL-06 in
`~/.claude/GLOBAL_LEARNINGS.md` (the process-level failure: a same-titled issue was marked
Resolved after fixing 3 of 4 surfaces sharing the defect).

### BUG-05 — `sections.topic_id` FK pointed at a dropped table (`topics_old`) {#bug-05}
**Date:** 2026-09-09 | **Session:** S5 | **Fixed:** Yes

**Root cause:** `migrate_002_topics_exam_agnostic.py` ran `ALTER TABLE topics RENAME TO
topics_old` then recreated `topics` and dropped `topics_old`, on the stated (and wrong)
assumption that renaming `topics` wouldn't affect `sections`' FK since "topics.topic_id is
still the PK, no data there needs touching." On this SQLite build, `ALTER TABLE RENAME`
does NOT rewrite other tables' stored FK clauses that reference the renamed table by name —
`sections` (created before that migration ran) was left with a literal
`REFERENCES "topics_old"(topic_id)` in its schema, a table that no longer existed from that
point on. Invisible for 3 sessions because `sections` had zero real rows until this
session's first-ever real (non-synthetic) ingestion run — `scripts/ingest.py` against the
real 2025 APFC/EO/AO paper — which is what actually exercised the `INSERT INTO sections`
path against the live `data/core.db` for the first time and immediately hit
`sqlite3.OperationalError: no such table: main.topics_old`.
**Fix:** `migrate_004_fix_sections_topic_fk.py` — recreates `sections` with the correct
`REFERENCES topics(topic_id)`, preserving any existing rows (none existed at fix time).
Verified against `sqlite_master` after running.
**Lesson:** A table-rename-based migration must explicitly check every OTHER table's stored
FK clauses for a reference to the renamed table — don't assume the database engine rewrites
them. And more generally: an "only synthetic smoke tests, never run against the real live
DB" testing strategy can hide a real schema bug indefinitely if the smoke tests always use
fresh throwaway DB copies (built via `init_db.py`'s correct schema-as-code) rather than a
copy of the actual live, migration-history-bearing database — the first real run against
production is what actually validates the schema's migration history, not just its
schema-as-code.

### BUG-06 — `ingest.py` never loaded `.env`; API key only worked if manually exported {#bug-06}
**Date:** 2026-09-09 | **Session:** S5 | **Fixed:** Yes

**Root cause:** `python-dotenv` has been a listed dependency since S4 (`.env` was created the
same session specifically to hold `ANTHROPIC_API_KEY`), but no file in the repo ever called
`load_dotenv()` — `scripts/ingest.py` calls `anthropic.Anthropic()` with no arguments, which
only picks up the key from the real process environment. S4's real-API smoke test worked
because that key had been manually `export`ed in that interactive terminal session; this
session's background ingestion run used a fresh shell that never had it exported, so
`anthropic.Anthropic()` failed client-side (`TypeError: Could not resolve authentication
method`) on the very first enrichment call — before any request reached Anthropic's
servers, so this specific failure cost nothing.
**Fix:** Added `load_dotenv(Path(__file__).parent.parent / ".env")` to `scripts/ingest.py`
right after the path setup, so the key loads from `.env` regardless of shell history.
**Lesson:** A dependency being listed in `requirements.txt` doesn't mean it's actually
wired up — this one sat unused for 3 sessions because the smoke tests that "confirmed
real-API access works" ran in a shell that happened to already have the var exported,
masking that the code itself never loaded it.

### BUG-07 — `enrich_chunk` assumed at most one PYQ per chunk; crashed on real dense MCQ content {#bug-07}
**Date:** 2026-09-09 | **Session:** S5 | **Fixed:** Yes

**Root cause:** `build_pyq`/the enrichment prompt's `"pyq": null | {...}` contract assumed
a chunk contains at most one complete question — true for Devthorium-style prose (a PYQ
occasionally embedded in study material) but false for a real dense MCQ test booklet, where
the chunker's atomic-block packing can legitimately group 2+ short complete questions into
one chunk. Haiku, given no explicit instruction for that case, improvised and returned a
JSON array instead of an object for one such chunk; `build_pyq`'s `p.get("year")` then threw
`AttributeError: 'list' object has no attribute 'get'`, an unhandled exception (not a
`ReviewNeededError`) that crashed the whole ingestion run — surfaced by the real 2025 APFC/
EO/AO paper, the first genuinely MCQ-dense document ever run through this pipeline.
**Fix:** Changed the contract to always be a list — prompt now specifies `"pyqs": [...]`
(empty if none), `build_pyq` renamed `build_pyqs`, returns `list[PYQQuestion]`, each item
gets an index-suffixed `question_id` (`{chunk_id}_pyq_{i}`) so multiple questions from one
chunk never collide on upsert. `ingest.py`'s call site loops over the list. All existing
`test_enrich.py` cases updated to the list shape; added
`test_multiple_pyqs_in_one_chunk_get_distinct_ids` to guard the exact failure mode. 20/20
tests passing across all non-API-dependent test files.
**Lesson:** A structured-extraction contract designed against one content shape (prose with
occasional PYQs) silently doesn't generalize to a structurally different one (a document
that IS just PYQs, densely packed) — and an LLM given an ambiguous schema (singular object,
but real input has multiple valid items) will improvise a plausible-looking but
uncontracted shape rather than fail loudly. Prefer "always a list" over "object or null"
for anything extracted per-chunk when the true cardinality is genuinely 0-to-many, even if
early testing only ever produced 0 or 1.

### BUG-08 — PYQ `year` never backfilled from `--published-date`, over half of real flags were this {#bug-08}
**Date:** 2026-09-09 | **Session:** S5 | **Fixed:** Yes

**Root cause:** `build_pyqs` required Haiku to find a `year` stated in the chunk's own text,
raising `ReviewNeededError` if absent — reasonable for prose material where an embedded PYQ
might say "(UPSC 2022)", but wrong for an official CURRENT-cycle paper: a 2025 exam's own
questions never restate "2025" inline, only a prior-year reference would appear in the text
at all. `enrich_chunk` already receives `published_date` (from `--published-date`) and
threads it into `ChunkMetadata`, but never passed it to `build_pyqs` — a real, known fact
sitting unused right next to the code that needed it. Impact, measured on the real 2025
APFC/EO/AO ingestion run: of 33 chunks flagged, 17 (>half) were pure "no year" misses on
otherwise perfectly good extractions.
**Fix:** `build_pyqs` takes `published_date`, falls back to `published_date.year` when
Haiku's own `year` is null; still raises `ReviewNeededError` if both are absent. Added
`test_pyq_missing_year_backfilled_from_published_date`. 11/11 `test_enrich.py` tests
passing (22 total across all non-API-dependent test files).
**Lesson:** Same shape as DECIDE-17 (exam_id/source_type shouldn't be re-derived from
content when the caller already knows it) — but the principle didn't get applied
consistently to every caller-known fact when this schema was extended. Worth an explicit
check next time a new per-question field is added: is this something the ingestion CALLER
already knows, or something that genuinely only exists inside the content?

### BUG-09 — One bad question discarded its good siblings; topic was chunk-level not question-level {#bug-09}
**Date:** 2026-09-09 | **Session:** S5 | **Fixed:** Yes

**Root cause (two compounding issues, both from the same design gap):** (1) `build_pyqs`
raised on the FIRST invalid question in a chunk, discarding the whole chunk — including
any other questions in it that had already validated successfully. Confirmed against real
data: one real chunk's failure was at question index 6, meaning 6 valid questions were
being destroyed as collateral damage from 1 unanswerable one. Given most flags are "no
correct_option" (this raw exam booklet has no answer key), and chunks routinely hold 5-9
questions, this was throwing away most of the real yield. (2) `topic_id` was classified
once per CHUNK and copied onto every question inside it — reasonable for prose with real
section headers (which naturally keep a chunk within one topic), wrong for this exam's
actual content: Part B has no subject headers at all, so a chunk can genuinely straddle a
real subject boundary (last question of one subject, first two of the next), silently
mistagging some questions regardless of the answer-key problem.
**Fix:** `build_pyqs` now returns `(valid_pyqs, failure_reasons)` — a bad question is
flagged individually and skipped; its siblings in the same chunk are kept. Each question
gets its own `topic_id` (prompt updated to ask for one per question, not just once per
chunk), falling back to the chunk-level value only when a question doesn't specify its
own; a per-question topic_id not in the registered set is now caught here (per-item flag)
instead of crashing later on the `pyq_bank.topic_id` foreign key — asking Haiku to classify
topic once per question instead of once per chunk means more independent chances for an
invented value to slip through, so this needed real validation, not just trusting the
prompt instruction. Also fixed `persist_pyq`'s upsert, which wasn't updating `topic_id`/
`year` on conflict — a stale value from before this fix would have silently survived a
re-run otherwise. `ingest.py` now logs per-question flags separately from whole-chunk
flags (`pyqs_flagged` vs `chunks_flagged`) so the summary distinguishes them. 6 new tests
in `test_enrich.py` (partial-chunk survival, per-question topic override, invalid-topic
rejection); 14/14 passing, 32/32 across all non-API-dependent test files.
**Lesson:** A per-chunk "unit of review" made sense when a chunk held at most one PYQ
(the original design). Once a chunk could hold many independent items, the same
all-or-nothing policy silently became a much bigger yield problem without any single line
of code being obviously wrong — the bug was in an assumption (validation granularity)
carried forward from before BUG-07, not in new code BUG-07 itself introduced. Worth
re-examining "unit of atomicity" assumptions whenever a schema changes from 0-or-1 to
0-to-many.

### BUG-10 — Chunk-level topic failure discarded question-level topic successes {#bug-10}
**Date:** 2026-09-09 | **Session:** S5 | **Fixed:** Yes

**Root cause:** BUG-09 gave each extracted PYQ its own independently-validated `topic_id`,
but `enrich_chunk` still called `build_chunk_metadata` first and let its
`ReviewNeededError` (the chunk's own OVERALL topic came back null) propagate and abort the
whole chunk — including `build_pyqs`, which never even ran. Confirmed against real data:
after BUG-09's fix, 11 chunks were still failing whole — 5 were the known harmless
instructions page, but 6 were real content chunks (pages 11-18) whose individual questions,
now independently topic-tagged, were never given the chance to be extracted at all.
**Fix:** `enrich_chunk` now extracts chunk-level metadata and per-question PYQs as two
independent outcomes of the same Haiku call, not gated on each other. `build_chunk_metadata`
failures are caught locally (`metadata=None`, reason returned separately) rather than
propagated; `build_pyqs` always runs regardless, using a new `chunk_id_for()` helper (the
chunk_id formula never actually depended on successful classification — only extracted from
`build_chunk_metadata` because nothing else needed it before). Caller skips `write_chunk`
when `metadata` is `None` (no home for that chunk's own embedding) but still persists any
valid PYQs. New end-to-end test `test_enrich_chunk_keeps_valid_pyqs_when_chunk_level_topic_fails`
(the first test to exercise `enrich_chunk` itself via a fake client, not just the two
builder functions separately — closed a real coverage gap, an unused `SimpleNamespace`
import had been sitting in the test file suggesting this was intended but never written).
33/33 tests passing.
**Lesson:** Same lesson as BUG-09, one layer up: when a schema changes from "one thing has
one classification" to "several independent things share a container," check whether a
failure at the CONTAINER level still needs to gate the CONTENTS — it often shouldn't once
the contents can stand on their own. This was found by tracing the exact same reasoning
Rahul applied to BUG-09 up one more level, not by new evidence — worth actively asking
"does this same argument apply anywhere else?" after fixing one instance of a pattern.

### BUG-11 — `PLAN.md` cited a resolved decision as still open, causing a wrong answer to Rahul {#bug-11}
**Date:** 2026-09-09 | **Session:** S6 | **Fixed:** Yes

**Root cause:** `PLAN.md`'s Phase 0 checklist carried a note written in S3 ("DECIDE-16 needs
Rahul's confirmation whether `upsc_eco_optional` is distinct from `upsc_eco_opt`") that was
never updated after DECIDE-16 actually resolved in S4, and was further superseded by
DECIDE-21's restructuring the same session. Answering a direct question from Rahul by
reading `PLAN.md` and quoting that line — without cross-checking `decisions.md`'s own
Resolved/Closed status field for DECIDE-16 — produced a wrong claim that the question was
still open, when it had been closed for 3 sessions.
**Fix:** `PLAN.md`'s note corrected to point at the real outcome (DECIDE-16 → DECIDE-21 →
DECIDE-25). `PROJECT.md`'s top-line status (also stale — predated S5's real ingestion and
the 9th exam registration) refreshed in the same pass.
**Lesson:** A decision log entry (`decisions.md`) is the authoritative source for whether a
decision is resolved. A checklist or plan note that *cites* a decision by ID can go stale
the moment the decision closes — never trust the citing doc's framing over the log entry's
own status field. Applies beyond this repo to any project with a similar plan-doc /
decision-log split.

### BUG-12 — 36 "extracted" 2025 answers were Haiku guesses, not real data {#bug-12}
**Date:** 2026-09-12 | **Session:** S8 | **Fixed:** Yes

**Root cause:** `enrich_chunk_system.txt` (since S4/DECIDE-13) asked Haiku for
`"correct_option": "<text of the correct option, or null if not determinable>"` — an
explicit instruction to answer the question itself when confident. The 2025 paper's 84
flagged/dropped questions (DECIDE-26) were the cases Haiku *wasn't* confident on; the 36
that made it into `pyq_bank` looking like successful extractions were actually just the
cases Haiku *was* confident on and guessed right or wrong with zero way to tell which.
**Fix:** Prompt no longer asks for correctness at all (DECIDE-27). `scripts/
migrate_005_answer_key_support.py` reset all 36 rows to `correct_option=NULL,
status='unverified'`.
**Lesson:** "The model produced a value without raising an error" is not evidence the value
is correct — DECIDE-10's "no silent fallback" principle was applied to *missing* data here,
but the mirror case (present-but-untrustworthy data) slipped through because nothing marked
model-derived correctness differently from source-derived correctness. Any field an LLM can
answer directly from its own knowledge (not just extract from the given text) needs either a
verification step or an explicit provenance/status flag before another system trusts it.

### BUG-14 — truncated Haiku JSON response crashed the whole ingestion run {#bug-14}
**Date:** 2026-09-12 | **Session:** S8 | **Fixed:** Yes

**Root cause:** A chunk packed with many dense MCQs (real 2017 EPFO paper) produced a
response `json.loads` couldn't parse ("Unterminated string...") — the response was cut off
by `max_tokens=2048`. `parse_enrichment`'s `json.loads` call was unguarded, so the exception
propagated all the way up and killed the entire batch, discarding every chunk not yet
processed along with it.
**Fix:** Raised `max_tokens` to 4096 (fewer truncations) and wrapped the parse in
`enrich_chunk` so a `JSONDecodeError` flags just that one chunk (same shape as any other
chunk-level failure) and lets the batch continue.
**Lesson:** Any external-response parse step inside a per-item loop needs the same
per-item failure isolation as validation does (BUG-09/10's principle) — a malformed
*response*, not just a *validated-but-wrong* one, is still just one item's problem.

### BUG-13 — chunk-boundary duplication produces the same PYQ twice {#bug-13}
**Date:** 2026-09-12 | **Session:** S8 | **Fixed:** Yes

**Root cause:** The 2023 EPFO GAT paper produced 5 duplicate `question_number`s (each
appearing in two adjacent chunks with near-identical `question_text`) — `chunk_document()`'s
Stage-2 packing evidently lets some content span into both a chunk boundary's trailing edge
and the next chunk's leading edge, and Haiku extracts the same question from both.
**Fix:** `persist_pyq` now checks for an existing row with the same
`(exam_id, paper_id, year, question_number)` before inserting and skips the duplicate
(`ingest.py` reports it as "duplicate PYQs skipped"), since `question_id` (chunk-derived)
can't catch this via the existing `ON CONFLICT`. Confirmed working on the 2016 paper (27 of
117 raw extractions were duplicates, all correctly skipped). The chunker's underlying
boundary overlap itself is not fixed — this is a persist-time safety net, not a root fix.
**Lesson:** `persist_pyq`'s upsert key is `question_id` (chunk-derived), not
`question_number` — the two chunks produce different `question_id`s for the same real
question, so the DB's own `ON CONFLICT` can't catch this class of duplicate. A future fix
should either eliminate the chunk-boundary overlap at the source, or de-duplicate by
`(exam_id, paper_id, year, question_number)` at ingest time before persisting.

### BUG-15 — `pyq_bank.options` stored as a list for rbi_depr/EPFO, crashing dict-shaped consumers {#bug-15}
**Date:** 2026-09-17 | **Session:** S9 (Phase 2 build) | **Fixed:** Yes

**Root cause:** `pyq_bank.options` is real JSON but was never uniformly one shape across
exams — `pfrda_gradea` stores `{"A": "...", "B": "...", ...}` (437 rows), but `rbi_depr`
(65 rows) and `upsc_epfo_apfc_eo_ao` (660 rows) both store a plain JSON list
`["...", "...", ...]` with no letters at all, from a different ingestion path. Found live
while building the new `/topic/{id}/brief` endpoint against a real EPFO row —
`scripts/quiz.py`'s `print_question()` (`options[letter]` on a list with a string key)
would have crashed on every single rbi_depr/EPFO row, never caught before because this
script's own docstring/examples only ever demonstrated `--exam_id pfrda_gradea`.
**Fix:** New `normalize_options()` in `scripts/quiz.py` (converts a list to
`{A: ..., B: ..., ...}` by position, passes a dict through unchanged) — used by both
`scripts/quiz.py`'s `print_question()` and the new `/pyq`/`/topic/{id}/brief` API
endpoints (`src/api/routes.py`), so every consumer sees one consistent dict shape
regardless of the underlying storage difference. The underlying storage inconsistency
itself was NOT changed — normalized only at read time.
**Lesson:** A field's shape being "real JSON, verified against live data" for one exam
does not mean it's the same shape for every exam — different ingestion runs/scripts can
silently disagree on a JSON field's internal structure. Any new consumer of a
multi-source JSON column should check the shape actually stored for every exam it will
touch, not just the one exam its author happened to test against.

**Format for future entries:**
```
### BUG-XX — Short description {#bug-xx}
**Date:** YYYY-MM-DD | **Session:** SN | **Fixed:** Yes/No

**Root cause:** One line. Always state why, not just what.
**Fix:** What was changed.
**Lesson:** What pattern to apply in future to prevent this class of bug.
```
