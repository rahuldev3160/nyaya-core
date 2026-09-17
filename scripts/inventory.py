"""Live inventory of everything actually indexed in nyaya-core right now — chunks
(LanceDB) and pyq_bank (SQLite), per exam/paper/topic/content_type/status. Run this
before trusting any assumption about what a given exam actually has available (e.g. "will
/search have anything to find here") — this exact gap (PFRDA: zero chunks; EPFO: 125,
thin) was found by querying these tables by hand this session; this script exists so that
never has to happen again by hand.

Usage:
    .venv/bin/python scripts/inventory.py [--exam_id pfrda_gradea]
"""
from __future__ import annotations

import argparse
import sqlite3
from collections import Counter
from pathlib import Path

import lancedb

DB_PATH = Path(__file__).parent.parent / "data" / "core.db"
LANCEDB_PATH = Path(__file__).parent.parent / "data" / "lancedb"


def pyq_bank_counts(conn: sqlite3.Connection, exam_id: str | None) -> dict:
    query = "SELECT exam_id, paper_id, topic_id, question_format, status FROM pyq_bank"
    params: list = []
    if exam_id:
        query += " WHERE exam_id = ?"
        params.append(exam_id)
    rows = conn.execute(query, params).fetchall()

    by_exam: Counter = Counter()
    by_exam_paper: Counter = Counter()
    by_exam_topic: Counter = Counter()
    by_format: Counter = Counter()
    by_status: Counter = Counter()
    for eid, pid, tid, qformat, status in rows:
        by_exam[eid] += 1
        by_exam_paper[(eid, pid)] += 1
        by_exam_topic[(eid, tid)] += 1
        by_format[(eid, qformat)] += 1
        by_status[(eid, status)] += 1

    return {
        "total": len(rows),
        "by_exam": by_exam,
        "by_exam_paper": by_exam_paper,
        "by_exam_topic": by_exam_topic,
        "by_format": by_format,
        "by_status": by_status,
    }


def chunk_counts(exam_id: str | None) -> dict:
    db = lancedb.connect(LANCEDB_PATH)
    if "chunks" not in db.list_tables():
        return {"total": 0, "by_exam": Counter(), "by_exam_content_type": Counter()}
    table = db.open_table("chunks")
    query = table.search()
    if exam_id:
        query = query.where(f"exam_id = '{exam_id}'", prefilter=True)
    rows = query.limit(100_000).to_list()

    by_exam: Counter = Counter()
    by_exam_content_type: Counter = Counter()
    for r in rows:
        by_exam[r["exam_id"]] += 1
        by_exam_content_type[(r["exam_id"], r["content_type"])] += 1

    return {"total": len(rows), "by_exam": by_exam, "by_exam_content_type": by_exam_content_type}


def print_report(exam_id: str | None) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")

    pyq = pyq_bank_counts(conn, exam_id)
    chunks = chunk_counts(exam_id)

    print("=== pyq_bank (SQLite core.db) ===")
    print(f"Total rows: {pyq['total']}")
    print("\nBy exam:")
    for eid, count in sorted(pyq["by_exam"].items()):
        print(f"  {eid}: {count}")
    print("\nBy exam / paper:")
    for (eid, pid), count in sorted(pyq["by_exam_paper"].items(), key=lambda x: x[0]):
        print(f"  {eid} / {pid}: {count}")
    print("\nBy exam / question_format:")
    for (eid, fmt), count in sorted(pyq["by_format"].items()):
        print(f"  {eid} / {fmt}: {count}")
    print("\nBy exam / status:")
    for (eid, status), count in sorted(pyq["by_status"].items()):
        print(f"  {eid} / {status}: {count}")
    print(f"\nDistinct (exam, topic) pairs with real PYQs: {len(pyq['by_exam_topic'])}")

    print("\n=== chunks (LanceDB) ===")
    print(f"Total rows: {chunks['total']}")
    print("\nBy exam:")
    for eid, count in sorted(chunks["by_exam"].items()):
        print(f"  {eid}: {count}")
    print("\nBy exam / content_type:")
    for (eid, ctype), count in sorted(chunks["by_exam_content_type"].items()):
        print(f"  {eid} / {ctype}: {count}")

    all_exams = {r[0] for r in conn.execute("SELECT exam_id FROM exams").fetchall()}
    if exam_id:
        all_exams &= {exam_id}
    zero_chunk_exams = sorted(e for e in all_exams if chunks["by_exam"].get(e, 0) == 0)
    if zero_chunk_exams:
        print(
            f"\nWARNING: zero indexed chunks for: {', '.join(zero_chunk_exams)} — "
            "/search and /topic/{id}/brief will return insufficient_grounding=True for "
            "these until content is ingested. /pyq is unaffected (reads pyq_bank directly)."
        )

    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--exam_id", default=None)
    args = parser.parse_args()
    print_report(args.exam_id)


if __name__ == "__main__":
    main()
