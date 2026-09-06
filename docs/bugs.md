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

**Format for future entries:**
```
### BUG-XX — Short description {#bug-xx}
**Date:** YYYY-MM-DD | **Session:** SN | **Fixed:** Yes/No

**Root cause:** One line. Always state why, not just what.
**Fix:** What was changed.
**Lesson:** What pattern to apply in future to prevent this class of bug.
```
