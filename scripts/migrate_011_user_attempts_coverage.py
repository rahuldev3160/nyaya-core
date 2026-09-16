"""Migration (DECIDE-34, see docs/decisions.md): adds a real per-user attempt/coverage
signal to `core.db` for the first time.

Step-0 verification (2026-09-16, before writing any code) confirmed the plan's original
assumption — that Recall (Devthorium) already serves/quizzes on PFRDA or EPFO content and
could be joined against for `coverage_depth` — was false. Checked Devthorium's live
`data/upsc.db` directly (not just nyaya-core's own notes, which could have been stale):
`topic_weights.exam_source` only has `rbi_grade_b` and `upsc_prelims` rows; `pyq_questions`
has no exam-scoping column at all (single-exam app); no file under Devthorium's
`backend/`/`scripts/`/`web/` references `nyaya-core`, `core.db`, `pfrda`, or `epfo`. There is
nothing to join. This matches `daily_priority.py`'s own module docstring (written same
session, verified against the live schema): no per-user attempt table exists anywhere in
nyaya-core, and that tracking lives in Recall/Scribe's own separate DBs, not here — except
now nyaya-core needs its own, since Recall doesn't cover this content and isn't going to
build it. Built directly on nyaya-core instead (`scripts/quiz.py`).

Two new tables:

1. `user_attempts` — attempt-level log, one row per question answered.
   `question_id` FKs to `pyq_bank`. `is_correct` is stored explicitly (not derived at query
   time) so historical rows remain correct even if `pyq_bank.correct_option` is later
   corrected by a re-verification pass — an attempt reflects what was graded *at the time*.

2. `topic_coverage` — one row per (exam_id, topic_id) actually attempted at least once.
   Computed, not measured directly — `scripts/quiz.py` upserts it at the end of each
   session from ALL historical `user_attempts` for that topic (not just that session's).
   Untested topics get NO row here (never a row with 0s) — `daily_priority.py` treats
   "no row" as `coverage_depth = 0.0`, per the layered-coverage skill's anti-false-positive
   rule (untested = max priority, never a fabricated default).

   `coverage_depth` follows the layered-coverage skill's Q3 depth rule exactly:
     accuracy >= 0.75           -> coverage_depth = 1.0            (fully covered)
     0.45 <= accuracy < 0.75    -> coverage_depth = accuracy       (proportional)
     accuracy < 0.45            -> coverage_depth = accuracy * 0.5 (penalised)

Run: .venv/bin/python scripts/migrate_011_user_attempts_coverage.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "core.db"


def _already_migrated(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='user_attempts'"
    ).fetchone()
    return row[0] > 0


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")

    if _already_migrated(conn):
        print("Already migrated — nothing to do.")
        conn.close()
        return

    conn.execute(
        """
        CREATE TABLE user_attempts (
            attempt_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id    TEXT NOT NULL REFERENCES pyq_bank(question_id),
            chosen_option  TEXT NOT NULL,
            correct_option TEXT NOT NULL,
            is_correct     INTEGER NOT NULL CHECK (is_correct IN (0, 1)),
            attempted_at   TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX idx_user_attempts_question ON user_attempts(question_id)")

    conn.execute(
        """
        CREATE TABLE topic_coverage (
            exam_id         TEXT NOT NULL REFERENCES exams(exam_id),
            topic_id        TEXT NOT NULL REFERENCES topics(topic_id),
            attempts_count  INTEGER NOT NULL,
            accuracy        REAL NOT NULL,
            coverage_depth  REAL NOT NULL,
            last_computed_at TEXT NOT NULL,
            PRIMARY KEY (exam_id, topic_id)
        )
        """
    )

    conn.commit()

    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
            "('user_attempts', 'topic_coverage')"
        ).fetchall()
    ]
    print(f"Created tables: {sorted(tables)}")
    conn.close()


if __name__ == "__main__":
    main()
