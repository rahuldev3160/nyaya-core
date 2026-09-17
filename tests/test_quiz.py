"""Unit tests for scripts/quiz.py — against a throwaway in-memory sqlite DB seeded with
fake pyq_bank/exam_topics/user_attempts/topic_coverage rows, never data/core.db (same
pattern as tests/test_daily_priority.py)."""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from quiz import (
    ACCURACY_FULL,
    ACCURACY_PARTIAL,
    compute_coverage_depth,
    fetch_candidate_questions,
    normalize_options,
    recompute_topic_coverage,
    select_questions,
)

SCHEMA = """
CREATE TABLE exams (exam_id TEXT PRIMARY KEY, name TEXT NOT NULL, institution_id TEXT, created_at TEXT);
CREATE TABLE papers (exam_id TEXT NOT NULL, paper_id TEXT NOT NULL, name TEXT NOT NULL, PRIMARY KEY (exam_id, paper_id));
CREATE TABLE topics (topic_id TEXT PRIMARY KEY, name TEXT NOT NULL, parent_topic_id TEXT, notes TEXT);
CREATE TABLE exam_topics (
    exam_id TEXT NOT NULL, paper_id TEXT NOT NULL DEFAULT '_all', topic_id TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0, is_core INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (exam_id, paper_id, topic_id)
);
CREATE TABLE pyq_bank (
    question_id TEXT PRIMARY KEY, exam_id TEXT NOT NULL, paper_id TEXT, topic_id TEXT,
    question_format TEXT NOT NULL, question_text TEXT NOT NULL, options TEXT,
    correct_option TEXT, status TEXT NOT NULL DEFAULT 'unverified'
);
CREATE TABLE user_attempts (
    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT, question_id TEXT NOT NULL,
    chosen_option TEXT NOT NULL, correct_option TEXT NOT NULL,
    is_correct INTEGER NOT NULL, attempted_at TEXT NOT NULL
);
CREATE TABLE topic_coverage (
    exam_id TEXT NOT NULL, topic_id TEXT NOT NULL, attempts_count INTEGER NOT NULL,
    accuracy REAL NOT NULL, coverage_depth REAL NOT NULL, last_computed_at TEXT NOT NULL,
    PRIMARY KEY (exam_id, topic_id)
);
"""


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    return conn


def _seed(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO exams VALUES ('fake_exam', 'Fake Exam', 'fake_inst', '2026-01-01')")
    conn.executemany(
        "INSERT INTO topics (topic_id, name, parent_topic_id) VALUES (?, ?, ?)",
        [("topic_a", "Topic A", None), ("topic_b", "Topic B", None)],
    )
    conn.executemany(
        "INSERT INTO exam_topics (exam_id, paper_id, topic_id, weight) VALUES (?, ?, ?, ?)",
        [
            ("fake_exam", "p1", "topic_a", 20.0),
            ("fake_exam", "p1", "topic_b", 5.0),
        ],
    )
    conn.executemany(
        "INSERT INTO pyq_bank (question_id, exam_id, paper_id, topic_id, question_format, "
        "question_text, options, correct_option, status) VALUES (?, ?, ?, ?, 'mcq', ?, ?, ?, ?)",
        [
            ("q1", "fake_exam", "p1", "topic_a", "Q1 text?", '{"A": "x", "B": "y"}', "A", "verified"),
            ("q2", "fake_exam", "p1", "topic_b", "Q2 text?", '{"A": "x", "B": "y"}', "B", "verified"),
            ("q3", "fake_exam", "p1", "topic_a", "Q3 text?", '{"A": "x", "B": "y"}', "A", "void"),
            ("q4", "fake_exam", "p1", "topic_a", "Q4 text?", '{"A": "x", "B": "y"}', None, "unverified"),
            ("q5", "fake_exam", "p1", None, "Q5 text?", '{"A": "x", "B": "y"}', "A", "verified"),
        ],
    )
    conn.commit()


# --- normalize_options: real per-exam storage-shape difference (found live) ---


def test_normalize_options_passes_through_dict_shape_unchanged():
    """pfrda_gradea's real storage shape."""
    assert normalize_options('{"A": "x", "B": "y"}') == {"A": "x", "B": "y"}


def test_normalize_options_letters_a_list_shape():
    """rbi_depr / upsc_epfo_apfc_eo_ao's real storage shape — a plain JSON list, no
    letters. Before this fix, print_question crashed on every row shaped like this
    (`options[letter]` on a list with a string key)."""
    assert normalize_options('["Q-P-R-S", "P-Q-S-R", "R-S-P-Q", "S-R-Q-P"]') == {
        "A": "Q-P-R-S",
        "B": "P-Q-S-R",
        "C": "R-S-P-Q",
        "D": "S-R-Q-P",
    }


def test_normalize_options_empty_or_none_is_empty_dict():
    assert normalize_options(None) == {}
    assert normalize_options("") == {}


# --- compute_coverage_depth: all three score bands ---


def test_coverage_depth_full_at_or_above_75_percent():
    assert compute_coverage_depth(ACCURACY_FULL) == 1.0
    assert compute_coverage_depth(0.9) == 1.0
    assert compute_coverage_depth(1.0) == 1.0


def test_coverage_depth_proportional_between_45_and_74_percent():
    assert compute_coverage_depth(ACCURACY_PARTIAL) == ACCURACY_PARTIAL
    assert compute_coverage_depth(0.6) == 0.6
    assert compute_coverage_depth(0.74) == 0.74


def test_coverage_depth_penalised_below_45_percent():
    assert compute_coverage_depth(0.4) == 0.4 * 0.5
    assert compute_coverage_depth(0.0) == 0.0


# --- fetch_candidate_questions: filters ---


def test_fetch_candidates_excludes_void_unverified_and_no_topic():
    conn = _conn()
    _seed(conn)
    candidates = fetch_candidate_questions(conn, "fake_exam", None, None)
    ids = {c["question_id"] for c in candidates}
    # q3 void, q4 no correct_option, q5 no topic_id -> all excluded
    assert ids == {"q1", "q2"}


def test_select_questions_orders_by_real_priority_topic_a_before_topic_b():
    conn = _conn()
    _seed(conn)
    selected = select_questions(conn, "fake_exam", None, None, n=10)
    assert [q["question_id"] for q in selected] == ["q1", "q2"]  # topic_a weight 20 > topic_b weight 5


def test_select_questions_respects_topic_filter():
    conn = _conn()
    _seed(conn)
    selected = select_questions(conn, "fake_exam", None, "topic_b", n=10)
    assert [q["question_id"] for q in selected] == ["q2"]


def test_select_questions_no_candidates_returns_empty_list():
    conn = _conn()
    _seed(conn)
    selected = select_questions(conn, "nonexistent_exam", None, None, n=10)
    assert selected == []


# --- recompute_topic_coverage: uses ALL historical attempts, upserts correctly ---


def test_recompute_topic_coverage_no_attempts_returns_none():
    conn = _conn()
    _seed(conn)
    assert recompute_topic_coverage(conn, "fake_exam", "topic_a") is None


def test_recompute_topic_coverage_uses_all_historical_attempts_not_just_one_session():
    conn = _conn()
    _seed(conn)
    # 3 historical attempts on topic_a's q1: 2 correct, 1 wrong -> accuracy 2/3
    conn.executemany(
        "INSERT INTO user_attempts (question_id, chosen_option, correct_option, is_correct, attempted_at) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            ("q1", "A", "A", 1, "t1"),
            ("q1", "A", "A", 1, "t2"),
            ("q1", "B", "A", 0, "t3"),
        ],
    )
    conn.commit()

    result = recompute_topic_coverage(conn, "fake_exam", "topic_a")
    assert result["attempts_count"] == 3
    assert abs(result["accuracy"] - (2 / 3)) < 1e-9
    assert result["coverage_depth"] == compute_coverage_depth(2 / 3)

    row = conn.execute(
        "SELECT attempts_count, accuracy, coverage_depth FROM topic_coverage "
        "WHERE exam_id = 'fake_exam' AND topic_id = 'topic_a'"
    ).fetchone()
    assert row[0] == 3
    assert abs(row[1] - (2 / 3)) < 1e-9


def test_recompute_topic_coverage_upserts_not_duplicates_row():
    conn = _conn()
    _seed(conn)
    conn.execute(
        "INSERT INTO user_attempts (question_id, chosen_option, correct_option, is_correct, attempted_at) "
        "VALUES ('q1', 'A', 'A', 1, 't1')"
    )
    conn.commit()
    recompute_topic_coverage(conn, "fake_exam", "topic_a")

    # Second session adds a wrong attempt -> recompute again, must update, not insert a 2nd row.
    conn.execute(
        "INSERT INTO user_attempts (question_id, chosen_option, correct_option, is_correct, attempted_at) "
        "VALUES ('q1', 'B', 'A', 0, 't2')"
    )
    conn.commit()
    recompute_topic_coverage(conn, "fake_exam", "topic_a")

    rows = conn.execute(
        "SELECT COUNT(*) FROM topic_coverage WHERE exam_id = 'fake_exam' AND topic_id = 'topic_a'"
    ).fetchone()
    assert rows[0] == 1

    accuracy = conn.execute(
        "SELECT accuracy FROM topic_coverage WHERE exam_id = 'fake_exam' AND topic_id = 'topic_a'"
    ).fetchone()[0]
    assert abs(accuracy - 0.5) < 1e-9
