"""Haiku-per-chunk enrichment (PLAN.md Phase 1, DECIDE-13): one combined call per chunk
does classification (content_type + topic_id), writes the Contextual Retrieval
`context_prefix`, and extracts PYQ structure where applicable.

The system prompt (source document + valid content_types + valid topics for this exam) is
built ONCE per document and passed with `cache_control` so every chunk call after the first
reuses Anthropic's prompt cache instead of re-billing the full document each time — building
it fresh per chunk would defeat that, since a byte-different "static" prefix can't be cached.
"""

import json
import os
import sqlite3
from datetime import date
from pathlib import Path

import anthropic

from src.schema.models import ChunkMetadata, DescriptiveQuestion, MCQQuestion, PYQQuestion, SourceType, TextChunk

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"
MODEL = os.getenv("AI_MODEL_FAST", "claude-haiku-4-5-20251001")


class ReviewNeededError(Exception):
    """Raised whenever Haiku itself signals uncertainty — no registered topic fit, or a PYQ
    missing a field the schema requires (year, correct_option). DECIDE-10's 'no silent
    fallback, explicit insufficient-grounding signal' principle applied to ingestion: better
    to surface the chunk for manual review than force a wrong guess into the database.
    """


def load_content_types(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    return conn.execute("SELECT type_id, name FROM content_types").fetchall()


def load_topics(conn: sqlite3.Connection, exam_id: str, paper_id: str | None = None) -> list[tuple[str, str]]:
    """Topics relevant to this exam, via the `exam_topics` junction (DECIDE-19/21) — `topics`
    itself is exam-agnostic, so a topic shared with another exam (e.g. "Monetary Policy"
    reused by both RBI and IES) is a single row, not duplicated per exam.

    `paper_id`, when given, narrows to topics relevant to that specific paper plus any
    exam-wide ('_all') topics — e.g. a document known to be from `upsc_cse`'s `essay` paper
    shouldn't see `modern_history`/`polity` as candidates just because they're valid for
    `prelims_gs` under the same exam_id (DECIDE-21). Omit `paper_id` for the broadest set
    (every topic linked to this exam, across all its papers) — the right choice when the
    caller doesn't know which paper a document belongs to.
    """
    if paper_id is None:
        rows = conn.execute(
            "SELECT DISTINCT t.topic_id, t.name FROM topics t "
            "JOIN exam_topics et ON t.topic_id = et.topic_id WHERE et.exam_id = ?",
            (exam_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT DISTINCT t.topic_id, t.name FROM topics t "
            "JOIN exam_topics et ON t.topic_id = et.topic_id "
            "WHERE et.exam_id = ? AND et.paper_id IN ('_all', ?)",
            (exam_id, paper_id),
        ).fetchall()
    if not rows:
        raise ReviewNeededError(
            f"no topics registered for exam_id='{exam_id}'"
            f"{f', paper_id={paper_id!r}' if paper_id else ''} — run scripts/seed_topics.py "
            f"for this exam/paper before ingesting its content (DECIDE-18)."
        )
    return rows


def _strip_json_fences(text: str) -> str:
    """Claude wraps JSON in ```json fences even when told not to — strip before parsing."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()


def build_system_prompt(
    source_doc: str,
    document_context: str,
    content_types: list[tuple[str, str]],
    topics: list[tuple[str, str]],
) -> str:
    template = (PROMPTS_DIR / "enrich_chunk_system.txt").read_text()
    return (
        template.replace("{{CONTENT_TYPES}}", ", ".join(t[0] for t in content_types))
        .replace("{{TOPICS}}", "\n".join(f"- {tid}: {name}" for tid, name in topics))
        .replace("{{SOURCE_DOC}}", source_doc)
        .replace("{{DOCUMENT_CONTEXT}}", document_context)
    )


def build_user_prompt(chunk: TextChunk) -> str:
    template = (PROMPTS_DIR / "enrich_chunk_user.txt").read_text()
    return template.replace("{{PAGE_NUMBER}}", str(chunk.page_number)).replace(
        "{{CHUNK_CONTENT}}", chunk.content
    )


def parse_enrichment(raw_response_text: str) -> dict:
    return json.loads(_strip_json_fences(raw_response_text))


def build_chunk_metadata(
    chunk: TextChunk,
    exam_id: str,
    source_type: SourceType,
    data: dict,
    published_date: date | None = None,
    paper_id: str | None = None,
) -> ChunkMetadata:
    """`source_type`/`published_date`/`paper_id` are caller-supplied (which folder/batch this
    document came from — same reasoning as DECIDE-17's exam_id: provenance, publication
    date, and which paper a document belongs to are all known before ingestion starts, not
    something Haiku should infer from a chunk's text).
    """
    if data.get("topic_id") is None:
        raise ReviewNeededError(
            f"chunk {chunk.chunk_index} of {chunk.source_doc} (page {chunk.page_number}): "
            f"no registered topic matched — needs manual review, not a silent default."
        )
    chunk_id = f"{exam_id}_{chunk.source_doc}_{chunk.page_number}_{chunk.chunk_index}"
    return ChunkMetadata(
        chunk_id=chunk_id,
        content=chunk.content,
        context_prefix=data["context_prefix"],
        exam_id=exam_id,
        paper_id=paper_id,
        topic_id=data["topic_id"],
        content_type=data["content_type"],
        section_id=chunk.section_id,
        source_doc=chunk.source_doc,
        page_number=chunk.page_number,
        published_date=published_date,
        source_type=source_type,
    )


def build_pyq(
    chunk_id: str, exam_id: str, source_type: SourceType, data: dict, paper_id: str | None = None
) -> PYQQuestion | None:
    if not data.get("is_pyq") or not data.get("pyq"):
        return None
    p = data["pyq"]
    if p.get("year") is None:
        raise ReviewNeededError(f"PYQ extracted from {chunk_id} has no year — needs manual review.")

    base = dict(
        question_id=f"{chunk_id}_pyq",
        exam_id=exam_id,
        paper_id=paper_id,
        topic_id=data["topic_id"],
        year=p["year"],
        question_text=p["question_text"],
        source_type=source_type,
    )
    if p["question_format"] == "mcq":
        if not p.get("correct_option"):
            raise ReviewNeededError(f"MCQ PYQ from {chunk_id} has no correct_option — needs manual review.")
        return MCQQuestion(
            **base, options=p["options"], correct_option=p["correct_option"],
            statements=p.get("statements"),
        )
    return DescriptiveQuestion(
        **base, marks=p.get("marks") or 0, word_limit=p.get("word_limit") or 0
    )


def persist_pyq(pyq: PYQQuestion, conn: sqlite3.Connection) -> None:
    """Writes one extracted PYQ to `pyq_bank`, upserting by question_id."""
    is_mcq = isinstance(pyq, MCQQuestion)
    conn.execute(
        """INSERT INTO pyq_bank
           (question_id, exam_id, paper_id, topic_id, question_format, year, question_text,
            options, correct_option, statements, marks, word_limit, source_type, verified_by, reviewed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(question_id) DO UPDATE SET
             question_text=excluded.question_text, options=excluded.options,
             correct_option=excluded.correct_option, statements=excluded.statements,
             marks=excluded.marks, word_limit=excluded.word_limit""",
        (
            pyq.question_id, pyq.exam_id, pyq.paper_id, pyq.topic_id, pyq.question_format, pyq.year,
            pyq.question_text,
            json.dumps(pyq.options) if is_mcq else None,
            pyq.correct_option if is_mcq else None,
            json.dumps(pyq.statements) if is_mcq and pyq.statements else None,
            None if is_mcq else pyq.marks,
            None if is_mcq else pyq.word_limit,
            pyq.source_type, pyq.verified_by,
            pyq.reviewed_at.isoformat() if pyq.reviewed_at else None,
        ),
    )
    conn.commit()


def enrich_chunk(
    chunk: TextChunk,
    exam_id: str,
    source_type: SourceType,
    system_prompt: str,
    client: anthropic.Anthropic,
    published_date: date | None = None,
    paper_id: str | None = None,
) -> tuple[ChunkMetadata, PYQQuestion | None, dict]:
    """One Haiku call per chunk. Pass the same `system_prompt` (from build_system_prompt(),
    built once per document) across every chunk of that document to get the cache hit.
    Returns (metadata, pyq_or_none, usage) — `usage` feeds the ingestion driver's
    cost-logging requirement (PLAN.md Phase 1: "Haiku calls add up — surface it, don't
    guess").
    """
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": build_user_prompt(chunk)}],
    )
    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cache_creation_input_tokens": getattr(response.usage, "cache_creation_input_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(response.usage, "cache_read_input_tokens", 0) or 0,
    }
    data = parse_enrichment(response.content[0].text)
    metadata = build_chunk_metadata(
        chunk, exam_id, source_type, data, published_date=published_date, paper_id=paper_id
    )
    pyq = build_pyq(metadata.chunk_id, exam_id, source_type, data, paper_id=paper_id)
    return metadata, pyq, usage
