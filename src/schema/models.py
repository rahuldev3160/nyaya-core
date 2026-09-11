"""Pydantic data contracts for Nyaya Core.

Validated at the boundary where untrusted data enters the system: right after an LLM
enrichment call, before anything touches core.db or LanceDB. See docs/DATA_DICTIONARY.md
for what each field means at the storage layer — this file is the same shape, enforced.
"""

from datetime import date, datetime
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field

SourceType = Literal["official_pyq", "ai_generated", "coaching_derived", "self_notes"]


class TextChunk(BaseModel):
    """Raw output of the Stage-2 chunker, before Haiku enrichment (DECIDE-13).

    Deliberately has no exam_id/topic_id/content_type/context_prefix yet — those don't
    exist until the enrichment call classifies this chunk. Modeling the pre- and
    post-enrichment shapes as separate classes makes "this field isn't known yet" a type
    error instead of a null-checking convention.
    """

    content: str
    source_doc: str
    page_number: int
    section_id: str
    chunk_index: int


class ChunkMetadata(BaseModel):
    """One row as it will be written to LanceDB's `chunks` table (vector attached at
    embed time, not modeled here — see docs/DATA_DICTIONARY.md).
    """

    chunk_id: str  # {exam_id}_{source_stem}_{page}_{idx} — built after enrichment, not before
    content: str
    context_prefix: str  # Contextual Retrieval blurb (DECIDE-13); embed context_prefix + content

    # Registry FKs. Plain str, NOT a Literal/enum — exams/topics/content_types are
    # data-driven tables (CLAUDE.md: "a new exam is a row, never a code change"). Validity
    # is enforced by the DB foreign key at insert time, not by this schema.
    exam_id: str
    paper_id: Optional[str] = None
    topic_id: str
    content_type: str
    section_id: str  # FK -> sections.section_id (DECIDE-14, parent-document layer)

    source_doc: str
    page_number: int
    published_date: Optional[date] = None

    source_type: SourceType  # small, stable provenance enum — this one IS a Literal
    verified_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    is_current: bool = True
    superseded_by: Optional[str] = None  # FK -> chunks.chunk_id (DECIDE-11)

    tags: dict[str, str] = Field(default_factory=dict)  # DECIDE-09: JSON side, see chunk_tags EAV table


class PYQBase(BaseModel):
    question_id: str
    exam_id: str
    paper_id: Optional[str] = None
    topic_id: str
    year: int
    question_text: str
    source_type: SourceType
    verified_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    tags: dict[str, str] = Field(default_factory=dict)
    # The number printed on the question in its source booklet (e.g. "47.") — literal
    # extraction, not inferred. Required to later match a real answer key (which is always
    # indexed by this number) back to the right row; None only for content with no visible
    # numbering (rare, e.g. a question quoted in prose).
    question_number: Optional[int] = None
    # The exact question-paper file this was extracted from (DECIDE-28) — e.g.
    # "data/raw_ingest_staging/upsc_epfo_apfc_eo_ao/eoao_gat_2023_notebooklm.pdf". Lets any
    # question be traced back to its literal source and re-checked/corrected if that source
    # is later found to be flawed, without having to reverse-engineer it from question_id.
    source_file: Optional[str] = None


class MCQQuestion(PYQBase):
    question_format: Literal["mcq"] = "mcq"
    options: list[str]
    # Letter (A/B/C/D, matching the position in `options`) of the verified correct answer —
    # never filled by Haiku (DECIDE-26/27: no question is solved by the LLM). None until a
    # real answer key is merged in via scripts/merge_answer_key.py.
    correct_option: Optional[str] = None
    # unverified: no real key applied yet. verified: correct_option came from a real official
    # key. void: UPSC itself dropped this item from scoring (a real, printed "item dropped"
    # outcome) — distinct from "we don't know yet".
    status: Literal["unverified", "verified", "void"] = "unverified"
    # The exact answer-key file (+ series, e.g. "UPSC-EPFO-EO-AO-Answer-Key-2023.pdf#series=A")
    # that supplied `correct_option` (DECIDE-28) — set only by scripts/merge_answer_key.py,
    # never by extraction. None while status='unverified'.
    answer_key_file: Optional[str] = None
    # Most real UPSC-style MCQs are statement-based ("how many of the following statements
    # are correct" — options like "Only one"/"Only two"/"All three"), not four independently
    # meaningful factual options. Capturing statements as structured data at extraction time
    # (not just embedded in question_text) is what lets explanation generation evaluate each
    # statement on its own instead of forcing a schema built for standalone options onto a
    # format it doesn't fit — the exact bug found in Recall's PYQ-explanation feature
    # (BUG-04: 100% of wrong-option fields came back silently empty for this reason).
    # None means standalone-option format; a populated list means statement-based.
    statements: Optional[list[str]] = None


class DescriptiveQuestion(PYQBase):
    question_format: Literal["descriptive"] = "descriptive"
    marks: int
    word_limit: int


PYQQuestion = Annotated[
    Union[MCQQuestion, DescriptiveQuestion],
    Field(discriminator="question_format"),
]


class OptionRationale(BaseModel):
    """One standalone option's rationale — used when `MCQQuestion.statements` is None."""

    option_label: str  # e.g. "A" — or the option text itself if the source has no letters
    option_text: str
    is_correct: bool
    rationale: str  # why this option is right, or specifically why it's wrong


class StatementRationale(BaseModel):
    """One numbered statement's rationale — used when `MCQQuestion.statements` is set."""

    statement_number: int
    statement_text: str
    is_correct: bool
    rationale: str


class StandaloneExplanation(BaseModel):
    """Explanation shape for an MCQ with independently-meaningful options."""

    option_format: Literal["standalone"] = "standalone"
    options: list[OptionRationale]


class StatementBasedExplanation(BaseModel):
    """Explanation shape for a statement-based MCQ ("how many of the above statements are
    correct") — evaluates each statement independently, then explains why the chosen
    combination option (e.g. "Only two") follows from those evaluations. This is the schema
    Recall's PYQ-explanation feature lacked (BUG-04): it forced a standalone-option shape
    onto statement-based questions, and the model silently omitted fields that didn't apply.
    """

    option_format: Literal["statement_based"] = "statement_based"
    statements: list[StatementRationale]
    combination_rationale: str  # why the correct combination-option follows from the above


ExplanationDetail = Annotated[
    Union[StandaloneExplanation, StatementBasedExplanation],
    Field(discriminator="option_format"),
]


class PYQExplanation(BaseModel):
    """One row in `pyq_explanations` (1:1 with `pyq_bank` via `question_id`). Generated in a
    separate, deliberately-triggered batch job — never live during a timed quiz, same
    principle Recall already established for its own quiz sessions. Validated against this
    schema before being written: a partial or malformed response is a generation failure to
    flag (`ReviewNeededError`, matching the pattern already used for chunk enrichment), never
    a silent partial write — that silent-partial-write failure mode is exactly BUG-04's root
    cause (100% of Recall's 904 generated rows had empty wrong-option fields, unnoticed).
    """

    question_id: str  # FK -> pyq_bank.question_id
    concept_summary: str  # brief — always shown, whether the user got the question right or not
    detail: ExplanationDetail  # detailed — only shown to the user on a wrong attempt
    # Real exam-technique reasoning: which options/statements a trained aspirant could
    # eliminate immediately, and why. Never attempted anywhere in this system before (fork
    # research confirmed) — a first-class field here, not an afterthought.
    elimination_strategy: Optional[str] = None
    # Citations used to generate this explanation — BUG-04's third root cause was zero
    # grounding/verification (pure model recall, no source to check against).
    grounding_chunk_ids: list[str] = Field(default_factory=list)
    model_version: str
    generated_at: datetime
    verified_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
