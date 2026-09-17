"""Request/response shapes for nyaya-core's FastAPI surface (PLAN.md Phase 2).

Kept separate from src/schema/models.py (the ingestion-time contracts) and
src/retrieval/models.py (search-result shapes) — this file is API-boundary-only.

`PYQOut.options` is `dict[str, str]` (letter -> option text), matching how `pyq_bank`
actually stores options today (verified directly against live data: e.g.
`{"A": "Rs 75", "B": "Rs 9", ...}`) — NOT `list[str]` as `src/schema/models.py`'s
`MCQQuestion.options` declares. That ingestion-time model/storage mismatch is real and
pre-existing; flagged here rather than silently worked around, and left unfixed as
out-of-scope for this API build (it doesn't block reading real data correctly).
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ExamOut(BaseModel):
    exam_id: str
    name: str
    institution_id: Optional[str] = None


class PaperOut(BaseModel):
    exam_id: str
    paper_id: str
    name: str


class TopicOut(BaseModel):
    topic_id: str
    name: str
    parent_topic_id: Optional[str] = None
    notes: Optional[str] = None
    weight: Optional[float] = None  # populated only when returned scoped to one exam/paper
    is_core: Optional[bool] = None


class PYQOut(BaseModel):
    question_id: str
    exam_id: str
    paper_id: Optional[str] = None
    topic_id: Optional[str] = None
    question_format: str  # "mcq" | "descriptive"
    year: Optional[int] = None
    question_number: Optional[int] = None
    question_text: str
    options: Optional[dict[str, str]] = None  # mcq only — see module docstring
    statements: Optional[list[str]] = None  # mcq only, when statement-based
    correct_option: Optional[str] = None  # mcq only, None until a real key is merged
    marks: Optional[int] = None  # descriptive only
    word_limit: Optional[int] = None  # descriptive only
    source_type: str
    status: Optional[str] = None  # mcq only: unverified | verified | void
    source_file: Optional[str] = None
    answer_key_file: Optional[str] = None


class TopicBriefOut(BaseModel):
    """Composite: 'explain X + give PYQs on it' in one call."""

    topic_id: str
    exam_id: str
    explanation_chunks: list  # list[SearchHit] — the search layer's own shape, reused as-is
    insufficient_grounding: bool
    mcq_pyqs: list[PYQOut]
    mains_pyqs: list[PYQOut]


class VerifyCitationRequest(BaseModel):
    claim: str
    chunk_id: str


class VerifyCitationResponse(BaseModel):
    claim: str
    chunk_id: str
    entailed: bool
    reasoning: str


class IngestRequest(BaseModel):
    folder: str
    exam_id: str
    source_type: str  # official_pyq | ai_generated | coaching_derived | self_notes
    paper_id: Optional[str] = None
    force: bool = False


class IngestResponse(BaseModel):
    status: str  # "started"
    pid: int
    log_file: str
    note: str


class AttemptRequest(BaseModel):
    question_id: str
    chosen_option: str


class AttemptResponse(BaseModel):
    question_id: str
    chosen_option: str
    correct_option: str
    is_correct: bool
    topic_coverage: Optional[dict] = None  # {attempts_count, accuracy, coverage_depth}
