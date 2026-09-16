"""Unit tests for scripts/daily_priority.py's ranking/formatting logic — against a
throwaway in-memory sqlite DB seeded with fake topics/exam_topics rows, never the real
data/core.db (same pattern as tests/test_enrich.py's `_pyq_bank_conn`)."""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from daily_priority import (
    COVERAGE_DEPTH,
    compute_at_risk,
    fetch_coverage_depth,
    fetch_items,
    get_scopes,
    paper_display_name,
    stream_label,
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


def _seed_fake_exam(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO exams VALUES ('fake_exam', 'Fake Exam', 'fake_inst', '2026-01-01')")
    conn.executemany(
        "INSERT INTO papers VALUES (?, ?, ?)",
        [
            ("fake_exam", "p_general", "Fake Exam — General stream"),
            ("fake_exam", "p_research", "Fake Exam — Research stream"),
        ],
    )
    conn.executemany(
        "INSERT INTO topics (topic_id, name, parent_topic_id) VALUES (?, ?, ?)",
        [
            ("topic_high", "High weight topic", None),
            ("topic_mid", "Mid weight topic", None),
            ("topic_low", "Low weight topic", None),
            ("topic_sub", "Subtopic of high", "topic_high"),
            ("topic_flat_a", "Flat placeholder A", None),
            ("topic_flat_b", "Flat placeholder B", None),
        ],
    )
    conn.executemany(
        "INSERT INTO exam_topics (exam_id, paper_id, topic_id, weight) VALUES (?, ?, ?, ?)",
        [
            ("fake_exam", "p_general", "topic_high", 30.0),
            ("fake_exam", "p_general", "topic_mid", 10.0),
            ("fake_exam", "p_general", "topic_low", 1.0),
            ("fake_exam", "p_general", "topic_sub", 5.0),
            ("fake_exam", "p_research", "topic_flat_a", 1.0),
            ("fake_exam", "p_research", "topic_flat_b", 1.0),
        ],
    )
    conn.commit()


def test_coverage_depth_is_zero_for_every_item():
    """Core assumption of the whole script: no real coverage signal exists in nyaya-core,
    so every item must score coverage_depth == 0.0 exactly (never a fabricated default)."""
    assert COVERAGE_DEPTH == 0.0


def test_fetch_items_returns_weight_and_computes_priority_score_equal_to_weight():
    conn = _conn()
    _seed_fake_exam(conn)
    items = fetch_items(conn, "fake_exam", "p_general")
    assert len(items) == 4
    by_id = {i["topic_id"]: i for i in items}
    # coverage_depth = 0.0 everywhere => priority_score == weight exactly
    assert by_id["topic_high"]["weight"] == 30.0
    assert by_id["topic_high"]["priority_score"] == 30.0
    assert by_id["topic_high"]["coverage_depth"] == 0.0
    assert by_id["topic_sub"]["parent_topic_id"] == "topic_high"


def test_priority_ranking_sorts_descending_by_weight():
    conn = _conn()
    _seed_fake_exam(conn)
    items = fetch_items(conn, "fake_exam", "p_general")
    ranked = sorted(items, key=lambda i: i["priority_score"], reverse=True)
    assert [i["topic_id"] for i in ranked] == ["topic_high", "topic_mid", "topic_sub", "topic_low"]


def test_at_risk_flags_above_median_weight_items_since_coverage_always_zero():
    conn = _conn()
    _seed_fake_exam(conn)
    items = fetch_items(conn, "fake_exam", "p_general")
    at_risk = compute_at_risk(items)
    at_risk_ids = {i["topic_id"] for i in at_risk}
    # weights: 30, 10, 1, 5 -> median 7.5 -> only topic_high (30) and topic_mid (10) exceed it
    assert at_risk_ids == {"topic_high", "topic_mid"}


def test_at_risk_empty_list_does_not_crash():
    assert compute_at_risk([]) == []


def test_get_scopes_with_explicit_paper_id_returns_single_scope():
    conn = _conn()
    _seed_fake_exam(conn)
    scopes = get_scopes(conn, "fake_exam", "p_research")
    assert scopes == [("p_research", "Fake Exam — Research stream")]


def test_get_scopes_with_no_paper_id_returns_every_real_paper_id():
    conn = _conn()
    _seed_fake_exam(conn)
    scopes = get_scopes(conn, "fake_exam", None)
    paper_ids = {pid for pid, _ in scopes}
    assert paper_ids == {"p_general", "p_research"}


def test_paper_display_name_falls_back_to_raw_id_when_not_registered():
    conn = _conn()
    _seed_fake_exam(conn)
    assert paper_display_name(conn, "fake_exam", "p_general") == "Fake Exam — General stream"
    assert paper_display_name(conn, "fake_exam", "unregistered_paper") == "unregistered_paper"


def test_stream_label_detects_general_and_research_and_falls_back_to_common():
    assert stream_label("phase1_p2_general") == "General stream"
    assert stream_label("phase1_p2_research") == "Research stream"
    assert stream_label("phase1_p1") == "Common (all streams)"


def test_fetch_items_empty_scope_returns_empty_list_not_error():
    conn = _conn()
    _seed_fake_exam(conn)
    items = fetch_items(conn, "fake_exam", "nonexistent_paper")
    assert items == []


# --- DECIDE-34: real coverage_depth wiring (topic_coverage table) ---


def test_fetch_coverage_depth_falls_back_to_zero_when_no_row_exists():
    """Untested topic (no topic_coverage row) must fall back to COVERAGE_DEPTH (0.0),
    never a fabricated default — the layered-coverage anti-false-positive rule."""
    conn = _conn()
    _seed_fake_exam(conn)
    assert fetch_coverage_depth(conn, "fake_exam", "topic_high") == COVERAGE_DEPTH
    assert fetch_coverage_depth(conn, "fake_exam", "topic_high") == 0.0


def test_fetch_coverage_depth_returns_real_row_when_present():
    conn = _conn()
    _seed_fake_exam(conn)
    conn.execute(
        "INSERT INTO topic_coverage (exam_id, topic_id, attempts_count, accuracy, "
        "coverage_depth, last_computed_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("fake_exam", "topic_high", 4, 0.75, 1.0, "2026-09-16T00:00:00+00:00"),
    )
    conn.commit()
    assert fetch_coverage_depth(conn, "fake_exam", "topic_high") == 1.0
    # A different, untested topic in the same exam is unaffected.
    assert fetch_coverage_depth(conn, "fake_exam", "topic_mid") == 0.0


def test_fetch_items_uses_real_coverage_depth_and_lowers_priority_score():
    """A topic with real full coverage (coverage_depth=1.0) must drop to priority_score=0
    (weight * (1 - 1.0)), while an untested sibling keeps priority_score == weight."""
    conn = _conn()
    _seed_fake_exam(conn)
    conn.execute(
        "INSERT INTO topic_coverage (exam_id, topic_id, attempts_count, accuracy, "
        "coverage_depth, last_computed_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("fake_exam", "topic_high", 10, 0.9, 1.0, "2026-09-16T00:00:00+00:00"),
    )
    conn.commit()
    items = fetch_items(conn, "fake_exam", "p_general")
    by_id = {i["topic_id"]: i for i in items}
    assert by_id["topic_high"]["coverage_depth"] == 1.0
    assert by_id["topic_high"]["priority_score"] == 0.0
    # topic_mid still untested -> unchanged behaviour.
    assert by_id["topic_mid"]["coverage_depth"] == 0.0
    assert by_id["topic_mid"]["priority_score"] == by_id["topic_mid"]["weight"]


def test_fetch_items_partial_coverage_reduces_but_does_not_zero_priority():
    conn = _conn()
    _seed_fake_exam(conn)
    conn.execute(
        "INSERT INTO topic_coverage (exam_id, topic_id, attempts_count, accuracy, "
        "coverage_depth, last_computed_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("fake_exam", "topic_mid", 3, 0.5, 0.5, "2026-09-16T00:00:00+00:00"),
    )
    conn.commit()
    items = fetch_items(conn, "fake_exam", "p_general")
    by_id = {i["topic_id"]: i for i in items}
    # weight 10.0 * (1 - 0.5) = 5.0
    assert by_id["topic_mid"]["priority_score"] == 5.0
