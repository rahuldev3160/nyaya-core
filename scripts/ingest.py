"""Ingestion driver (PLAN.md Phase 1) — walks a folder, drives chunk_document() ->
enrich_chunk() -> write_chunk() per file. `exam_id`/`source_type` are CLI args, not
per-chunk classifications (DECIDE-17): the folder you point this at IS the exam scope.

Incremental/resumable via a hash-based skip-list (`data/ingestion_log.json`), same pattern
as Devthorium's `ingestion_log.json` — re-running after new uploads only processes new or
changed files. Uncertainty is flagged, never silently dropped or guessed past (DECIDE-10) —
appended to `data/flagged_chunks.jsonl`, batch continues. Two independent failure units, per
BUG-09: a whole CHUNK can be flagged (its own overall topic didn't match — no embedding gets
written for it), and/or individual QUESTIONS within an otherwise-fine chunk can be flagged
(missing year/correct_option/own topic) without discarding their valid siblings.

Usage:
    .venv/bin/python scripts/ingest.py --folder /path/to/pdfs --exam-id upsc_prelims_gs \\
        --source-type coaching_derived
"""

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

import anthropic
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(Path(__file__).parent.parent / ".env")

from src.ingestion.chunker import chunk_document
from src.ingestion.embed import write_chunk
from src.ingestion.enrich import (
    build_system_prompt,
    enrich_chunk,
    load_content_types,
    load_topics,
    persist_pyq,
)
from src.ingestion.parsers import (
    extract_digital_pdf,
    extract_docx,
    extract_handwritten_pdf,
    extract_html,
    extract_pages,
    extract_scanned_pdf,
    extract_textclipping,
    get_page_text_quality,
)

DB_PATH = Path(__file__).parent.parent / "data" / "core.db"
LOG_PATH = Path(__file__).parent.parent / "data" / "ingestion_log.json"
FLAGGED_PATH = Path(__file__).parent.parent / "data" / "flagged_chunks.jsonl"

HANDWRITTEN_KEYWORDS = {"handwritten", "self notes", "self_notes", "goodnotes", "notability"}
YEAR_IN_FILENAME = re.compile(r"(?<!\d)(19|20)\d{2}(?!\d)")  # \b fails after '_' (both \w) — e.g. "report_2023"

EXTRACTORS = {
    "digital_pdf": extract_digital_pdf,
    "scanned_pdf": extract_scanned_pdf,
    "handwritten_pdf": extract_handwritten_pdf,
    "docx": extract_docx,
    "pages": extract_pages,
    "html": extract_html,
    "textclipping": extract_textclipping,
}


def file_hash(path: Path) -> str:
    stat = path.stat()
    return hashlib.sha256(f"{path}:{stat.st_size}:{stat.st_mtime}".encode()).hexdigest()[:16]


def load_log() -> dict:
    return json.loads(LOG_PATH.read_text()) if LOG_PATH.exists() else {}


def save_log(log: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(json.dumps(log, indent=2))


def detect_parser(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return "docx"
    if suffix == ".pages":
        return "pages"
    if suffix in (".html", ".htm"):
        return "html"
    if suffix == ".textclipping":
        return "textclipping"
    if suffix == ".pdf":
        if any(kw in path.name.lower() for kw in HANDWRITTEN_KEYWORDS):
            return "handwritten_pdf"
        return "scanned_pdf" if get_page_text_quality(str(path)) < 100 else "digital_pdf"
    return "unknown"


def infer_published_date(path: Path, cli_override: date | None) -> date | None:
    if cli_override:
        return cli_override
    match = YEAR_IN_FILENAME.search(path.stem)
    return date(int(match.group()), 1, 1) if match else None


def ingest_file(
    path: Path,
    exam_id: str,
    source_type: str,
    conn: sqlite3.Connection,
    client: anthropic.Anthropic,
    published_date: date | None,
    paper_id: str | None = None,
    force_parser: str | None = None,
) -> dict:
    """Runs the full pipeline for one file. Returns a usage/outcome summary for logging.
    `paper_id` (DECIDE-21), when given, narrows topic classification to that specific paper
    within `exam_id` (plus exam-wide topics) — pass it whenever a folder's content is known
    to belong to one paper (e.g. ingesting only Ethics-paper PDFs), so a chunk can't get
    classified into a different paper's topic just because it shares the same exam_id.

    `force_parser` overrides `detect_parser`'s heuristic — needed for e.g. a coaching-site
    PDF whose first pages are a text-heavy cover/intro but whose actual question pages are
    image-only: `get_page_text_quality` only samples the first 3 pages, so it can score such
    a file as "digital" and silently extract almost nothing from the rest (confirmed on the
    real APFC 2012 question paper, 182 avg chars/page from the sample, 0 from the real
    content pages). Always eyeball a few pages past the cover before trusting auto-detection.
    """
    parser_name = force_parser or detect_parser(path)
    if parser_name == "unknown":
        raise ValueError(f"no parser for '{path.suffix}' ({path.name})")

    pages = EXTRACTORS[parser_name](str(path))
    doc_id = path.stem
    chunks = chunk_document(pages, doc_id=doc_id, exam_id=exam_id, conn=conn)

    content_types = load_content_types(conn)
    topics = load_topics(conn, exam_id, paper_id=paper_id)  # raises ReviewNeededError if no taxonomy yet
    document_context = "\n\n".join(text for _, text in pages)
    system_prompt = build_system_prompt(doc_id, document_context, content_types, topics)

    try:
        source_file = str(path.relative_to(Path(__file__).parent.parent))
    except ValueError:
        source_file = str(path)

    summary = {
        "file": str(path), "chunks_written": 0, "pyqs_written": 0, "pyqs_deduped": 0,
        "chunks_flagged": 0, "pyqs_flagged": 0, "input_tokens": 0, "output_tokens": 0,
        "cache_creation_tokens": 0, "cache_read_tokens": 0,
    }

    def _log_flagged(reason: str) -> None:
        FLAGGED_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(FLAGGED_PATH, "a") as f:
            f.write(json.dumps({"file": str(path), "chunk_index": chunk.chunk_index, "reason": reason}) + "\n")

    for chunk in chunks:
        metadata, pyqs, pyq_failures, metadata_failure, usage = enrich_chunk(
            chunk, exam_id, source_type, system_prompt, client, topics,
            published_date=published_date, paper_id=paper_id, source_file=source_file,
        )

        # The chunk's own overall classification (its embedding/retrieval placement) and its
        # extracted questions (each independently topic-tagged, BUG-09) are independent
        # outcomes of the same call — one failing must not take the other down with it.
        if metadata is not None:
            write_chunk(metadata)
            summary["chunks_written"] += 1
        else:
            summary["chunks_flagged"] += 1
            _log_flagged(metadata_failure)

        for pyq in pyqs:
            if persist_pyq(pyq, conn):
                summary["pyqs_written"] += 1
            else:
                summary["pyqs_deduped"] += 1
        for reason in pyq_failures:
            summary["pyqs_flagged"] += 1
            _log_flagged(reason)

        summary["input_tokens"] += usage["input_tokens"]
        summary["output_tokens"] += usage["output_tokens"]
        summary["cache_creation_tokens"] += usage["cache_creation_input_tokens"]
        summary["cache_read_tokens"] += usage["cache_read_input_tokens"]

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("--exam-id", required=True)
    parser.add_argument("--source-type", required=True,
                         choices=["official_pyq", "ai_generated", "coaching_derived", "self_notes"])
    parser.add_argument("--published-date", type=date.fromisoformat, default=None,
                         help="YYYY-MM-DD, applied to every file in this batch if given")
    parser.add_argument("--paper-id", default=None,
                         help="Narrows topic classification to one paper within --exam-id "
                              "(DECIDE-21) — set this whenever the folder's content belongs "
                              "to a single known paper, e.g. --paper-id essay.")
    parser.add_argument("--force", action="store_true",
                         help="Reprocess files even if their hash is already recorded in "
                              "ingestion_log.json — needed to re-run a file after a schema/"
                              "prompt change, not just after the file itself changes.")
    parser.add_argument("--parser", choices=list(EXTRACTORS), default=None,
                         help="Force this parser instead of auto-detecting — use when "
                              "detect_parser's first-3-pages heuristic is fooled by a "
                              "text-heavy cover/intro on an otherwise image-only PDF (check "
                              "a few real content pages before trusting auto-detection).")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    client = anthropic.Anthropic()
    log = load_log()

    files = [p for p in args.folder.rglob("*") if p.is_file() and detect_parser(p) != "unknown"]
    totals = {"files_processed": 0, "files_skipped": 0, "chunks_written": 0, "pyqs_written": 0,
              "pyqs_deduped": 0, "chunks_flagged": 0, "pyqs_flagged": 0, "input_tokens": 0,
              "output_tokens": 0, "cache_creation_tokens": 0, "cache_read_tokens": 0}

    for path in files:
        h = file_hash(path)
        if log.get(str(path)) == h and not args.force:
            totals["files_skipped"] += 1
            continue

        published_date = infer_published_date(path, args.published_date)
        summary = ingest_file(path, args.exam_id, args.source_type, conn, client, published_date,
                               paper_id=args.paper_id, force_parser=args.parser)
        print(f"{path.name}: {summary['chunks_written']} chunks, {summary['pyqs_written']} PYQs, "
              f"{summary['pyqs_deduped']} duplicate PYQs skipped (BUG-13), "
              f"{summary['chunks_flagged']} chunks flagged, {summary['pyqs_flagged']} questions flagged")

        log[str(path)] = h
        save_log(log)  # after every file, not just at the end — a crash mid-batch shouldn't lose progress
        totals["files_processed"] += 1
        for key in ("chunks_written", "pyqs_written", "pyqs_deduped", "chunks_flagged", "pyqs_flagged",
                    "input_tokens", "output_tokens", "cache_creation_tokens", "cache_read_tokens"):
            totals[key] += summary[key]

    conn.close()
    print(
        f"\nDone: {totals['files_processed']} files processed, {totals['files_skipped']} skipped "
        f"(unchanged). {totals['chunks_written']} chunks written, {totals['pyqs_written']} PYQs, "
        f"{totals['pyqs_deduped']} duplicate PYQs skipped (BUG-13), "
        f"{totals['chunks_flagged']} whole chunks flagged, {totals['pyqs_flagged']} individual "
        f"questions flagged (see {FLAGGED_PATH.name}).\n"
        f"Haiku usage: {totals['input_tokens']} input, {totals['output_tokens']} output, "
        f"{totals['cache_creation_tokens']} cache-write, {totals['cache_read_tokens']} cache-read tokens."
    )


if __name__ == "__main__":
    main()
