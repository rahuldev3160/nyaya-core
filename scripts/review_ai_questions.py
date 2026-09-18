"""Spot-check CLI for AI-generated pyq_bank rows (source_type='ai_generated', written by
scripts/generate_ai_pyq_bank.py). Every AI-generated question is servable immediately
(status='unverified' is not a gate — see generate_ai_pyq_bank.py's docstring on trust
semantics), but Rahul can use this to personally review a sample and flip specific rows
to 'verified' (checked, trustworthy) or 'void' (wrong/bad, never serve again) — the same
two-outcome discipline real-PYQ answer-key merging already uses, just human-driven instead
of key-driven for this source_type.

Mirrors scripts/quiz.py's existing interactive-CLI pattern (input(), immediate feedback) —
not a new UI paradigm.

Usage:
    .venv/bin/python scripts/review_ai_questions.py --exam_id pfrda_gradea [--topic_id ID] [--n 10]
    .venv/bin/python scripts/review_ai_questions.py --exam_id pfrda_gradea --status unverified
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "core.db"
_LETTERS = ["A", "B", "C", "D", "E"]


def select_ai_questions(conn: sqlite3.Connection, exam_id: str, topic_id: str | None,
                         status: str, n: int) -> list[sqlite3.Row]:
    query = (
        "SELECT * FROM pyq_bank WHERE exam_id = ? AND source_type = 'ai_generated' "
        "AND status = ?"
    )
    args: list = [exam_id, status]
    if topic_id:
        query += " AND topic_id = ?"
        args.append(topic_id)
    query += " ORDER BY question_id LIMIT ?"
    args.append(n)
    return conn.execute(query, args).fetchall()


def print_question(idx: int, total: int, q: sqlite3.Row, explanation: sqlite3.Row | None) -> None:
    options = json.loads(q["options"])
    print(f"\n--- AI question {idx}/{total} [{q['topic_id']}] (id: {q['question_id']}) ---")
    print(q["question_text"])
    for letter in sorted(options):
        marker = " *" if letter == q["correct_option"] else ""
        print(f"  {letter}) {options[letter]}{marker}")
    if explanation:
        print(f"  Concept: {explanation['concept_summary']}")
        if explanation["elimination_strategy"]:
            print(f"  Elimination: {explanation['elimination_strategy']}")


def review_one(conn: sqlite3.Connection, q: sqlite3.Row) -> None:
    while True:
        choice = input("  [v]erify / [x]void / [s]kip / [q]uit: ").strip().lower()
        if choice in ("v", "verify"):
            conn.execute(
                "UPDATE pyq_bank SET status='verified', verified_by='rahul', reviewed_at=? "
                "WHERE question_id=?",
                (datetime.now(timezone.utc).isoformat(), q["question_id"]),
            )
            conn.commit()
            print("  -> verified.")
            return
        if choice in ("x", "void"):
            conn.execute(
                "UPDATE pyq_bank SET status='void', verified_by='rahul', reviewed_at=? "
                "WHERE question_id=?",
                (datetime.now(timezone.utc).isoformat(), q["question_id"]),
            )
            conn.commit()
            print("  -> voided, will no longer be served.")
            return
        if choice in ("s", "skip", ""):
            return
        if choice in ("q", "quit"):
            sys.exit(0)
        print("  Please enter v, x, s, or q.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exam_id", required=True)
    parser.add_argument("--topic_id", default=None)
    parser.add_argument("--status", default="unverified", choices=["unverified", "verified", "void"])
    parser.add_argument("--n", type=int, default=10)
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"ERROR: {DB_PATH} not found.", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row

    questions = select_ai_questions(conn, args.exam_id, args.topic_id, args.status, args.n)
    if not questions:
        print(f"No source_type='ai_generated' questions with status='{args.status}' found for the given filters.")
        conn.close()
        return

    print(f"Reviewing {len(questions)} AI-generated question(s), status='{args.status}'.\n")
    for idx, q in enumerate(questions, start=1):
        explanation = conn.execute(
            "SELECT * FROM pyq_explanations WHERE question_id = ?", (q["question_id"],)
        ).fetchone()
        print_question(idx, len(questions), q, explanation)
        review_one(conn, q)

    conn.close()


if __name__ == "__main__":
    main()
