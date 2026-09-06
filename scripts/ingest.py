"""Ingestion driver (PLAN.md Phase 1) — walks a folder, drives chunk_document() ->
enrich_chunk() -> write_chunk() per file. `exam_id`/`source_type` are CLI args, not
per-chunk classifications (DECIDE-17): the folder you point this at IS the exam scope.

Incremental/resumable via a hash-based skip-list (`data/ingestion_log.json`), same pattern
as Devthorium's `ingestion_log.json` — re-running after new uploads only processes new or
changed files. A chunk Haiku flags as uncertain (ReviewNeededError — no topic match, or a
PYQ missing year/correct_option) does not abort the batch; it's appended to
`data/flagged_chunks.jsonl` for manual review and the run continues (DECIDE-10's principle:
surface uncertainty, don't crash on it and don't silently drop it either).

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

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.chunker import chunk_document
from src.ingestion.embed import write_chunk
from src.ingestion.enrich import (
    ReviewNeededError,
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
) -> dict:
    """Runs the full pipeline for one file. Returns a usage/outcome summary for logging.
    `paper_id` (DECIDE-21), when given, narrows topic classification to that specific paper
    within `exam_id` (plus exam-wide topics) — pass it whenever a folder's content is known
    to belong to one paper (e.g. ingesting only Ethics-paper PDFs), so a chunk can't get
    classified into a different paper's topic just because it shares the same exam_id.
    """
    parser_name = detect_parser(path)
    if parser_name == "unknown":
        raise ValueError(f"no parser for '{path.suffix}' ({path.name})")

    pages = EXTRACTORS[parser_name](str(path))
    doc_id = path.stem
    chunks = chunk_document(pages, doc_id=doc_id, exam_id=exam_id, conn=conn)

    content_types = load_content_types(conn)
    topics = load_topics(conn, exam_id, paper_id=paper_id)  # raises ReviewNeededError if no taxonomy yet
    document_context = "\n\n".join(text for _, text in pages)
    system_prompt = build_system_prompt(doc_id, document_context, content_types, topics)

    summary = {
        "file": str(path), "chunks_written": 0, "pyqs_written": 0, "chunks_flagged": 0,
        "input_tokens": 0, "output_tokens": 0, "cache_creation_tokens": 0, "cache_read_tokens": 0,
    }

    for chunk in chunks:
        try:
            metadata, pyq, usage = enrich_chunk(
                chunk, exam_id, source_type, system_prompt, client,
                published_date=published_date, paper_id=paper_id,
            )
        except ReviewNeededError as e:
            summary["chunks_flagged"] += 1
            FLAGGED_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(FLAGGED_PATH, "a") as f:
                f.write(json.dumps({"file": str(path), "chunk_index": chunk.chunk_index, "reason": str(e)}) + "\n")
            continue

        write_chunk(metadata)
        summary["chunks_written"] += 1
        if pyq is not None:
            persist_pyq(pyq, conn)
            summary["pyqs_written"] += 1

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
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    client = anthropic.Anthropic()
    log = load_log()

    files = [p for p in args.folder.rglob("*") if p.is_file() and detect_parser(p) != "unknown"]
    totals = {"files_processed": 0, "files_skipped": 0, "chunks_written": 0, "pyqs_written": 0,
              "chunks_flagged": 0, "input_tokens": 0, "output_tokens": 0,
              "cache_creation_tokens": 0, "cache_read_tokens": 0}

    for path in files:
        h = file_hash(path)
        if log.get(str(path)) == h:
            totals["files_skipped"] += 1
            continue

        published_date = infer_published_date(path, args.published_date)
        summary = ingest_file(path, args.exam_id, args.source_type, conn, client, published_date,
                               paper_id=args.paper_id)
        print(f"{path.name}: {summary['chunks_written']} chunks, {summary['pyqs_written']} PYQs, "
              f"{summary['chunks_flagged']} flagged")

        log[str(path)] = h
        save_log(log)  # after every file, not just at the end — a crash mid-batch shouldn't lose progress
        totals["files_processed"] += 1
        for key in ("chunks_written", "pyqs_written", "chunks_flagged", "input_tokens",
                    "output_tokens", "cache_creation_tokens", "cache_read_tokens"):
            totals[key] += summary[key]

    conn.close()
    print(
        f"\nDone: {totals['files_processed']} files processed, {totals['files_skipped']} skipped "
        f"(unchanged). {totals['chunks_written']} chunks written, {totals['pyqs_written']} PYQs, "
        f"{totals['chunks_flagged']} flagged for review (see {FLAGGED_PATH.name}).\n"
        f"Haiku usage: {totals['input_tokens']} input, {totals['output_tokens']} output, "
        f"{totals['cache_creation_tokens']} cache-write, {totals['cache_read_tokens']} cache-read tokens."
    )


if __name__ == "__main__":
    main()
