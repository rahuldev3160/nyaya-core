"""CLI quiz runner — the first real source of per-user coverage signal in nyaya-core.

Step-0 finding (2026-09-16, see `migrate_011_user_attempts_coverage.py`'s docstring for the
full evidence): Recall (Devthorium) does not serve or quiz on any PFRDA/EPFO content today,
so there was nothing to join `coverage_depth` against there. This script builds that signal
directly on nyaya-core instead: pulls real questions from `pyq_bank`, quizzes interactively
(immediate right/wrong feedback — this is real study utility, not just data collection),
logs every attempt to `user_attempts`, and at session end recomputes `topic_coverage` for
every topic touched — from ALL historical attempts for that topic, not just this session's —
so `daily_priority.py` gets a real ranking signal instead of its previous hardcoded 0.0.

Question selection reuses `daily_priority.py`'s own `get_scopes`/`fetch_items` ranking
(real `exam_topics.weight` * (1 - coverage_depth)) rather than reimplementing it — questions
in higher-priority topics are asked first. Falls back to raw `pyq_bank` order if the exam
has no `exam_topics` rows at all.

`coverage_depth` follows the layered-coverage skill's Q3 depth rule exactly:
    accuracy >= 0.75          -> coverage_depth = 1.0            (fully covered)
    0.45 <= accuracy < 0.75   -> coverage_depth = accuracy       (proportional)
    accuracy < 0.45           -> coverage_depth = accuracy * 0.5 (penalised)

Only status != 'void' questions with a real, non-null `correct_option` are quizzable — an
`unverified` row with no recorded answer can't be graded, so it's excluded here (not part of
the spec's literal filter list, but a practical necessity: this script can't tell Rahul
"right" or "wrong" against a blank answer key). Questions with no `topic_id` are also
excluded — `topic_coverage`'s primary key requires one.

Usage:
    .venv/bin/python scripts/quiz.py --exam_id pfrda_gradea [--paper_id ID] [--topic_id ID] [--n 10]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from daily_priority import fetch_items, get_scopes  # reuse real ranking, don't reimplement

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "core.db"

ACCURACY_FULL = 0.75
ACCURACY_PARTIAL = 0.45


def compute_coverage_depth(accuracy: float) -> float:
    """layered-coverage skill's Q3 depth rule."""
    if accuracy >= ACCURACY_FULL:
        return 1.0
    if accuracy >= ACCURACY_PARTIAL:
        return accuracy
    return accuracy * 0.5


def topic_priority_map(conn: sqlite3.Connection, exam_id: str, paper_id: str | None) -> dict[str, float]:
    """Real priority_score per topic_id, reusing daily_priority.py's ranking. Empty dict
    (caller falls back to raw pyq_bank order) if this exam has no exam_topics rows."""
    priorities: dict[str, float] = {}
    scopes = get_scopes(conn, exam_id, paper_id)
    for pid, _ in scopes:
        for item in fetch_items(conn, exam_id, pid):
            priorities[item["topic_id"]] = item["priority_score"]
    return priorities


def fetch_candidate_questions(
    conn: sqlite3.Connection, exam_id: str, paper_id: str | None, topic_id: str | None
) -> list[dict]:
    query = (
        "SELECT question_id, paper_id, topic_id, question_text, options, correct_option "
        "FROM pyq_bank WHERE exam_id = ? AND status != 'void' AND question_format = 'mcq' "
        "AND correct_option IS NOT NULL AND correct_option != '' AND topic_id IS NOT NULL"
    )
    params: list = [exam_id]
    if paper_id:
        query += " AND paper_id = ?"
        params.append(paper_id)
    if topic_id:
        query += " AND topic_id = ?"
        params.append(topic_id)
    rows = conn.execute(query, params).fetchall()
    return [
        {
            "question_id": r[0],
            "paper_id": r[1],
            "topic_id": r[2],
            "question_text": r[3],
            "options": r[4],
            "correct_option": r[5],
        }
        for r in rows
    ]


def select_questions(
    conn: sqlite3.Connection, exam_id: str, paper_id: str | None, topic_id: str | None, n: int
) -> list[dict]:
    candidates = fetch_candidate_questions(conn, exam_id, paper_id, topic_id)
    if not candidates:
        return []
    priorities = topic_priority_map(conn, exam_id, paper_id)
    if priorities:
        candidates.sort(key=lambda q: priorities.get(q["topic_id"], 0.0), reverse=True)
    return candidates[:n]


def log_attempt(
    conn: sqlite3.Connection, question_id: str, chosen_option: str, correct_option: str, is_correct: bool
) -> None:
    conn.execute(
        "INSERT INTO user_attempts (question_id, chosen_option, correct_option, is_correct, attempted_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            question_id,
            chosen_option,
            correct_option,
            int(is_correct),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()


def recompute_topic_coverage(conn: sqlite3.Connection, exam_id: str, topic_id: str) -> dict | None:
    """Recomputes topic_coverage from ALL historical user_attempts for this (exam_id,
    topic_id) — not just the current session's — and upserts the row."""
    row = conn.execute(
        """
        SELECT COUNT(*), COALESCE(SUM(ua.is_correct), 0)
        FROM user_attempts ua
        JOIN pyq_bank pb ON pb.question_id = ua.question_id
        WHERE pb.exam_id = ? AND pb.topic_id = ?
        """,
        (exam_id, topic_id),
    ).fetchone()
    attempts_count, correct_count = row
    if attempts_count == 0:
        return None

    accuracy = correct_count / attempts_count
    coverage_depth = compute_coverage_depth(accuracy)
    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        """
        INSERT INTO topic_coverage (exam_id, topic_id, attempts_count, accuracy, coverage_depth, last_computed_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(exam_id, topic_id) DO UPDATE SET
            attempts_count = excluded.attempts_count,
            accuracy = excluded.accuracy,
            coverage_depth = excluded.coverage_depth,
            last_computed_at = excluded.last_computed_at
        """,
        (exam_id, topic_id, attempts_count, accuracy, coverage_depth, now),
    )
    conn.commit()
    return {
        "attempts_count": attempts_count,
        "accuracy": accuracy,
        "coverage_depth": coverage_depth,
    }


def print_question(idx: int, total: int, q: dict) -> None:
    print(f"\n--- Question {idx}/{total} [{q['topic_id']}] ---")
    print(q["question_text"])
    options = json.loads(q["options"]) if q["options"] else {}
    for letter in sorted(options):
        print(f"  {letter}) {options[letter]}")


def run(exam_id: str, paper_id: str | None, topic_id: str | None, n: int) -> None:
    if not DB_PATH.exists():
        print(f"ERROR: {DB_PATH} not found.", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")

    questions = select_questions(conn, exam_id, paper_id, topic_id, n)
    if not questions:
        print("No quizzable questions found for the given filters "
              "(need status != 'void', a recorded correct_option, and a topic_id).")
        conn.close()
        return

    print(f"Starting quiz: {len(questions)} question(s) from '{exam_id}'"
          + (f" / paper '{paper_id}'" if paper_id else "")
          + (f" / topic '{topic_id}'" if topic_id else "") + ".\n")

    touched_topics: set[str] = set()
    n_correct = 0
    for idx, q in enumerate(questions, start=1):
        print_question(idx, len(questions), q)
        chosen = input("Your answer: ").strip().upper()
        correct = q["correct_option"].strip().upper()
        is_correct = chosen == correct
        if is_correct:
            n_correct += 1
            print("Correct!")
        else:
            print(f"Wrong — correct answer was {correct}.")

        log_attempt(conn, q["question_id"], chosen, correct, is_correct)
        touched_topics.add(q["topic_id"])

    print(f"\nSession done: {n_correct}/{len(questions)} correct "
          f"({n_correct / len(questions):.0%}).")

    print("\nRecomputed topic_coverage (from ALL historical attempts, not just this session):")
    for t_id in sorted(touched_topics):
        result = recompute_topic_coverage(conn, exam_id, t_id)
        if result:
            print(
                f"  {t_id}: attempts={result['attempts_count']} "
                f"accuracy={result['accuracy']:.0%} "
                f"coverage_depth={result['coverage_depth']:.2f}"
            )

    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive quiz runner over real pyq_bank questions.")
    parser.add_argument("--exam_id", required=True)
    parser.add_argument("--paper_id", default=None)
    parser.add_argument("--topic_id", default=None)
    parser.add_argument("--n", type=int, default=10)
    args = parser.parse_args()
    run(args.exam_id, args.paper_id, args.topic_id, args.n)


if __name__ == "__main__":
    main()
