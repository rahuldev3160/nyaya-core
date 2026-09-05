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


class MCQQuestion(PYQBase):
    question_format: Literal["mcq"] = "mcq"
    options: list[str]
    correct_option: str


class DescriptiveQuestion(PYQBase):
    question_format: Literal["descriptive"] = "descriptive"
    marks: int
    word_limit: int


PYQQuestion = Annotated[
    Union[MCQQuestion, DescriptiveQuestion],
    Field(discriminator="question_format"),
]
