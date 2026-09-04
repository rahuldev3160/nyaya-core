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

**Format for future entries:**
```
### BUG-XX — Short description {#bug-xx}
**Date:** YYYY-MM-DD | **Session:** SN | **Fixed:** Yes/No

**Root cause:** One line. Always state why, not just what.
**Fix:** What was changed.
**Lesson:** What pattern to apply in future to prevent this class of bug.
```
