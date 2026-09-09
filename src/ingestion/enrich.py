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


def chunk_id_for(exam_id: str, chunk: TextChunk) -> str:
    """Deterministic regardless of enrichment outcome — needed independently of
    `build_chunk_metadata` succeeding, since `build_pyqs` must still be able to run (and
    generate stable `question_id`s) even when the chunk's own overall classification fails
    (see enrich_chunk)."""
    return f"{exam_id}_{chunk.source_doc}_{chunk.page_number}_{chunk.chunk_index}"


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
    chunk_id = chunk_id_for(exam_id, chunk)
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


def build_pyqs(
    chunk_id: str, exam_id: str, source_type: SourceType, data: dict, valid_topic_ids: set[str],
    paper_id: str | None = None, published_date: date | None = None,
) -> tuple[list[PYQQuestion], list[str]]:
    """A chunk can legitimately contain more than one complete question (a dense MCQ
    test-booklet chunk, not just Devthorium-style prose with an occasional embedded PYQ) —
    `pyqs` is always a list, `[]` if none. Each item gets its own index-suffixed
    `question_id` so multiple questions from the same chunk never collide on upsert.

    Returns (valid_pyqs, failure_reasons) — a validation failure on one item flags only
    THAT item, not the whole chunk. Real dense-MCQ content (BUG-07/found this session)
    routinely packs 5-9 independent questions into one chunk; discarding all of them
    because one lacked a determinable answer (the dominant real failure mode — an official
    paper with no answer key) was silently destroying good, valid extractions alongside
    the bad one. Each remaining valid question is still worth keeping on its own.

    Each question gets its OWN `topic_id`, not the chunk-level one — a chunk with no
    section headers to key off (this exam's real content) can genuinely span a subject
    boundary. Falls back to the chunk-level topic_id only when a question doesn't specify
    its own; a per-question topic_id that isn't in `valid_topic_ids` is treated as a
    per-item failure, not silently accepted — `topic_id` is a real database foreign key
    (DECIDE-04), and asking Haiku to classify it once per question (rather than once per
    chunk) means more independent chances for an invented value to slip through.

    `published_date` (caller-supplied, e.g. from --published-date) backfills a question's
    `year` when Haiku can't find one stated in the chunk text — expected for an official
    current-cycle paper, which never restates its own year inline (only a *prior*-year
    reference would appear in the question text itself). Same DECIDE-17 reasoning as
    exam_id/source_type: the document's own date is known provenance, not something to force
    an LLM to re-derive from content that was never going to state it.
    """
    raw_items = data.get("pyqs") or []
    results: list[PYQQuestion] = []
    failures: list[str] = []
    for i, p in enumerate(raw_items):
        topic_id = p.get("topic_id") or data["topic_id"]
        if topic_id not in valid_topic_ids:
            failures.append(f"PYQ #{i} from {chunk_id} has topic_id '{topic_id}', not a "
                             f"registered topic — needs manual review.")
            continue

        year = p.get("year") or (published_date.year if published_date else None)
        if year is None:
            failures.append(f"PYQ #{i} extracted from {chunk_id} has no year — needs manual review.")
            continue

        base = dict(
            question_id=f"{chunk_id}_pyq_{i}",
            exam_id=exam_id,
            paper_id=paper_id,
            topic_id=topic_id,
            year=year,
            question_text=p["question_text"],
            source_type=source_type,
        )
        if p["question_format"] == "mcq":
            if not p.get("correct_option"):
                failures.append(f"MCQ PYQ #{i} from {chunk_id} has no correct_option — needs manual review.")
                continue
            results.append(MCQQuestion(
                **base, options=p["options"], correct_option=p["correct_option"],
                statements=p.get("statements"),
            ))
        else:
            results.append(DescriptiveQuestion(
                **base, marks=p.get("marks") or 0, word_limit=p.get("word_limit") or 0
            ))
    return results, failures


def persist_pyq(pyq: PYQQuestion, conn: sqlite3.Connection) -> None:
    """Writes one extracted PYQ to `pyq_bank`, upserting by question_id."""
    is_mcq = isinstance(pyq, MCQQuestion)
    conn.execute(
        """INSERT INTO pyq_bank
           (question_id, exam_id, paper_id, topic_id, question_format, year, question_text,
            options, correct_option, statements, marks, word_limit, source_type, verified_by, reviewed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(question_id) DO UPDATE SET
             topic_id=excluded.topic_id, year=excluded.year,
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
    topics: list[tuple[str, str]],
    published_date: date | None = None,
    paper_id: str | None = None,
) -> tuple[ChunkMetadata | None, list[PYQQuestion], list[str], str | None, dict]:
    """One Haiku call per chunk. Pass the same `system_prompt` (from build_system_prompt(),
    built once per document) across every chunk of that document to get the cache hit.
    Returns (metadata, pyqs, pyq_failures, metadata_failure, usage) — `usage` feeds the
    ingestion driver's cost-logging requirement (PLAN.md Phase 1: "Haiku calls add up —
    surface it, don't guess"). `topics` (the same list already loaded for
    `build_system_prompt`) is re-passed here so `build_pyqs` can validate each question's
    own topic_id against the real registered set, not just trust it.

    `metadata` and `pyqs` are extracted INDEPENDENTLY, not gated on each other. The chunk's
    own overall topic classification (used for its embedding/retrieval placement) can
    legitimately fail — a chunk with no section headers to key off can genuinely be an
    unclassifiable mix — but that must not also discard the individual questions inside it,
    since each of those now carries its own, separately-validated topic_id (BUG-09). When
    the chunk-level classification fails, `metadata` is `None` and `metadata_failure` holds
    the reason (caller should skip `write_chunk` but still persist any valid `pyqs`).
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

    metadata: ChunkMetadata | None = None
    metadata_failure: str | None = None
    try:
        metadata = build_chunk_metadata(
            chunk, exam_id, source_type, data, published_date=published_date, paper_id=paper_id
        )
    except ReviewNeededError as e:
        metadata_failure = str(e)

    valid_topic_ids = {tid for tid, _ in topics}
    pyqs, pyq_failures = build_pyqs(chunk_id_for(exam_id, chunk), exam_id, source_type, data,
                                     valid_topic_ids, paper_id=paper_id, published_date=published_date)
    return metadata, pyqs, pyq_failures, metadata_failure, usage
