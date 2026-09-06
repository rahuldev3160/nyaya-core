"""Header-aware two-stage chunker (`SyllabusChunker`, PLAN.md Phase 1).

Stage 1 splits a parsed document into sections at detected heading lines — numbered
headings, "Article N"/"Section N" (a hard boundary: never let a statute clause span two
sections), and ALL-CAPS titles. Sections are the parent-document layer for auto-merging
retrieval (DECIDE-14) and get persisted to the `sections` table before Stage 2 runs.

Stage 2 only fires when a section is too large for one chunk. It splits on atomic
blocks — paragraphs, or a run of consecutive table rows treated as one unit — never
mid-sentence, mid-word, or through a table. An atomic block larger than the chunk budget
is kept whole rather than sliced (correctness over size — the invariant CLAUDE.md states
for Law/Econ Optional content).

No word-level overlap between chunks (unlike Devthorium's old word-slider): lost
cross-chunk context is compensated by the Contextual Retrieval blurb (DECIDE-13,
generated later in the Haiku enrichment step), not by literal text duplication.
"""

import re
import sqlite3
from dataclasses import dataclass, field

from src.schema.models import TextChunk

CHUNK_SIZE_WORDS = 375

_HEADING_PATTERNS = [
    re.compile(r"^#{1,6}\s+.+$"),  # markdown, in case a source already has it
    re.compile(r"^(Chapter|Part|Unit)\s+[IVXLCDM\d]+\b.*$", re.IGNORECASE),
    re.compile(r"^(Article|Section)\s+\d+[A-Z]?\b.*$"),  # statute boundary
    re.compile(r"^\d+(\.\d+){0,3}\s+[A-Z].{0,80}$"),  # numbered heading, e.g. "1.2 Something"
    re.compile(r"^[A-Z][A-Z \-&]{4,80}$"),  # ALL-CAPS short title
]

_TABLE_ROW = re.compile(r".+\|.+")


def _is_heading(line: str) -> bool:
    line = line.strip()
    if not line or len(line) > 100:
        return False
    return any(p.match(line) for p in _HEADING_PATTERNS)


@dataclass
class Section:
    """Stage-1 output — one row destined for the `sections` table."""

    section_id: str
    doc_id: str
    heading: str | None
    page_start: int
    page_end: int
    lines: list[str] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n".join(self.lines).strip()


def split_sections(pages: list[tuple[int, str]], doc_id: str) -> list[Section]:
    """Stage 1. `pages` is a parser's output: (page_number, page_text) pairs, 1-indexed."""
    sections: list[Section] = []
    current: Section | None = None

    for page_num, text in pages:
        for raw_line in text.split("\n"):
            line = raw_line.rstrip()
            if _is_heading(line):
                if current is not None and current.full_text:
                    sections.append(current)
                current = Section(
                    section_id=f"{doc_id}_s{len(sections)}",
                    doc_id=doc_id,
                    heading=line.strip(),
                    page_start=page_num,
                    page_end=page_num,
                )
                continue
            if current is None:
                current = Section(
                    section_id=f"{doc_id}_s0", doc_id=doc_id, heading=None,
                    page_start=page_num, page_end=page_num,
                )
            current.lines.append(line)
            current.page_end = page_num

    if current is not None and current.full_text:
        sections.append(current)
    return sections


def persist_sections(
    sections: list[Section],
    exam_id: str,
    conn: sqlite3.Connection,
    topic_id: str | None = None,
    content_type: str | None = None,
) -> None:
    """Writes Stage-1 sections to the `sections` table. `exam_id` is caller-supplied —
    it's the scope of the whole ingestion run (a folder = an exam), never Haiku-classified
    per chunk (DECIDE-17). `topic_id`/`content_type` are nullable here; the enrichment step
    backfills them once the first chunk in a section is classified.
    """
    conn.executemany(
        """INSERT OR IGNORE INTO sections
           (section_id, doc_id, exam_id, topic_id, content_type, heading, full_text,
            page_start, page_end)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (s.section_id, s.doc_id, exam_id, topic_id, content_type, s.heading,
             s.full_text, s.page_start, s.page_end)
            for s in sections
        ],
    )
    conn.commit()


def _atomic_blocks(text: str) -> list[str]:
    """Splits on blank lines (paragraphs), but keeps a run of consecutive table rows
    (docx tables are flattened to "cell | cell" lines by docx_parser.py) as one block —
    otherwise a paragraph-boundary split would slice a table across two chunks.
    """
    blocks: list[str] = []
    buf: list[str] = []
    in_table = False

    def flush() -> None:
        if buf and "\n".join(buf).strip():
            blocks.append("\n".join(buf).strip())
        buf.clear()

    for line in text.split("\n"):
        is_row = bool(_TABLE_ROW.match(line))
        if is_row != in_table and buf:
            flush()
        in_table = is_row
        if not line.strip() and not in_table:
            buf.append(line)
            flush()
            continue
        buf.append(line)
    flush()
    return blocks


def chunk_section(section: Section, start_index: int = 0) -> list[TextChunk]:
    """Stage 2. Packs atomic blocks into chunks up to CHUNK_SIZE_WORDS; an oversized
    single block is emitted whole rather than split (statute/table integrity)."""
    blocks = _atomic_blocks(section.full_text)
    chunks: list[str] = []
    current: list[str] = []
    current_words = 0

    def flush() -> None:
        nonlocal current, current_words
        if current:
            chunks.append("\n\n".join(current))
        current, current_words = [], 0

    for block in blocks:
        block_words = len(block.split())
        if current_words + block_words > CHUNK_SIZE_WORDS and current:
            flush()
        current.append(block)
        current_words += block_words
    flush()

    return [
        TextChunk(
            content=content,
            source_doc=section.doc_id,
            page_number=section.page_start,
            section_id=section.section_id,
            chunk_index=start_index + i,
        )
        for i, content in enumerate(chunks)
    ]


def chunk_document(pages: list[tuple[int, str]], doc_id: str, exam_id: str,
                    conn: sqlite3.Connection) -> list[TextChunk]:
    """Runs both stages end-to-end for one document: split into sections, persist them,
    then chunk each section, with `chunk_index` running continuously across the document
    (matches the old `chunk_id` convention: {exam_id}_{source_stem}_{page}_{idx})."""
    sections = split_sections(pages, doc_id)
    persist_sections(sections, exam_id, conn)

    chunks: list[TextChunk] = []
    for section in sections:
        chunks.extend(chunk_section(section, start_index=len(chunks)))
    return chunks
