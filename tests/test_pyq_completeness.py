"""Tests for scripts/pyq_completeness.py — against a throwaway in-memory sqlite DB seeded
with fake exams/papers/pyq_bank rows, never data/core.db (same pattern as
tests/test_quiz.py/tests/test_daily_priority.py)."""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from pyq_completeness import _derive_status, record, report

SCHEMA = """
CREATE TABLE exams (exam_id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT);
CREATE TABLE papers (exam_id TEXT NOT NULL, paper_id TEXT NOT NULL, name TEXT NOT NULL, PRIMARY KEY (exam_id, paper_id));
CREATE TABLE pyq_bank (
    question_id TEXT PRIMARY KEY, exam_id TEXT NOT NULL, paper_id TEXT, topic_id TEXT,
    question_format TEXT NOT NULL, year INTEGER, question_text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unverified'
);
CREATE TABLE pyq_completeness_ledger (
    exam_id TEXT NOT NULL,
    paper_id TEXT NOT NULL,
    year INTEGER NOT NULL,
    expected_count INTEGER,
    actual_count INTEGER NOT NULL DEFAULT 0,
    source_reference TEXT,
    status TEXT NOT NULL DEFAULT 'unaudited' CHECK (status IN ('complete', 'partial', 'unaudited')),
    gap_detail TEXT,
    last_audited_at TEXT,
    PRIMARY KEY (exam_id, paper_id, year),
    FOREIGN KEY (exam_id, paper_id) REFERENCES papers(exam_id, paper_id)
);
"""


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    return conn


def _seed_exam_paper(conn, exam_id="upsc_cse", paper_id="eco_optional_1"):
    conn.execute("INSERT OR IGNORE INTO exams (exam_id, name) VALUES (?, ?)", (exam_id, exam_id))
    conn.execute(
        "INSERT OR IGNORE INTO papers (exam_id, paper_id, name) VALUES (?, ?, ?)",
        (exam_id, paper_id, paper_id),
    )
    conn.commit()


def _seed_pyq(conn, exam_id, paper_id, year, n, question_format="descriptive", offset=0):
    for i in range(offset, offset + n):
        conn.execute(
            "INSERT INTO pyq_bank (question_id, exam_id, paper_id, year, question_format, question_text) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (f"{exam_id}_{paper_id}_{year}_{i}", exam_id, paper_id, year, question_format, f"Q{i}"),
        )
    conn.commit()


# --- _derive_status unit tests -------------------------------------------------------

def test_derive_status_unaudited_when_expected_unknown():
    assert _derive_status(None, 0) == "unaudited"
    assert _derive_status(None, 5) == "unaudited"


def test_derive_status_complete_when_actual_meets_or_exceeds_expected():
    assert _derive_status(8, 8) == "complete"
    assert _derive_status(8, 10) == "complete"


def test_derive_status_partial_when_actual_short_of_expected():
    assert _derive_status(8, 3) == "partial"


def test_derive_status_partial_when_actual_zero_but_expected_known():
    assert _derive_status(8, 0) == "partial"


# --- record() integration tests ------------------------------------------------------

def test_record_empty_exam_zero_content_no_expected_is_unaudited():
    """The exact real-world case named in the brief: eco_optional_1 has zero pyq_bank rows."""
    conn = _conn()
    _seed_exam_paper(conn, "upsc_cse", "eco_optional_1")

    row = record(conn, "upsc_cse", "eco_optional_1", 2023, expected_count=None, source_reference=None)

    assert row["actual_count"] == 0
    assert row["status"] == "unaudited"
    assert row["expected_count"] is None


def test_record_empty_exam_zero_content_with_expected_is_partial():
    conn = _conn()
    _seed_exam_paper(conn, "upsc_cse", "eco_optional_2")

    row = record(
        conn, "upsc_cse", "eco_optional_2", 2023,
        expected_count=8, source_reference="data/answer_keys/fake_source_for_test.pdf",
    )

    assert row["actual_count"] == 0
    assert row["status"] == "partial"


def test_record_complete_case():
    conn = _conn()
    _seed_exam_paper(conn, "upsc_epfo_apfc_eo_ao", "gat")
    _seed_pyq(conn, "upsc_epfo_apfc_eo_ao", "gat", 2023, n=114, question_format="mcq")

    row = record(
        conn, "upsc_epfo_apfc_eo_ao", "gat", 2023,
        expected_count=114, source_reference="docs/decisions.md#decide-27",
    )

    assert row["actual_count"] == 114
    assert row["status"] == "complete"


def test_record_partial_case_with_gap_detail():
    conn = _conn()
    _seed_exam_paper(conn, "upsc_epfo_apfc_eo_ao", "gat")
    _seed_pyq(conn, "upsc_epfo_apfc_eo_ao", "gat", 2023, n=114, question_format="mcq")

    row = record(
        conn, "upsc_epfo_apfc_eo_ao", "gat", 2023,
        expected_count=120, source_reference="docs/decisions.md#decide-27",
        gap_detail="Q115-120 (quant aptitude) not extracted",
    )

    assert row["actual_count"] == 114
    assert row["status"] == "partial"
    assert row["gap_detail"] == "Q115-120 (quant aptitude) not extracted"


def test_record_is_upsert_not_duplicate():
    conn = _conn()
    _seed_exam_paper(conn, "upsc_cse", "eco_optional_1")
    _seed_pyq(conn, "upsc_cse", "eco_optional_1", 2023, n=3)

    record(conn, "upsc_cse", "eco_optional_1", 2023, expected_count=None, source_reference=None)
    record(conn, "upsc_cse", "eco_optional_1", 2023, expected_count=3, source_reference="real_source.pdf")

    rows = conn.execute("SELECT * FROM pyq_completeness_ledger").fetchall()
    assert len(rows) == 1

    row = conn.execute(
        "SELECT status, expected_count, actual_count FROM pyq_completeness_ledger "
        "WHERE exam_id='upsc_cse' AND paper_id='eco_optional_1' AND year=2023"
    ).fetchone()
    assert row == ("complete", 3, 3)


def test_record_actual_count_reflects_live_pyq_bank_not_manually_typed():
    conn = _conn()
    _seed_exam_paper(conn, "upsc_cse", "eco_optional_1")
    _seed_pyq(conn, "upsc_cse", "eco_optional_1", 2023, n=5)

    row = record(conn, "upsc_cse", "eco_optional_1", 2023, expected_count=10, source_reference="src.pdf")
    assert row["actual_count"] == 5  # computed live, never taken from a parameter

    _seed_pyq(conn, "upsc_cse", "eco_optional_1", 2023, n=5, offset=5)  # 5 more ingested since last record
    row2 = record(conn, "upsc_cse", "eco_optional_1", 2023, expected_count=10, source_reference="src.pdf")
    assert row2["actual_count"] == 10
    assert row2["status"] == "complete"


# --- report() tests (smoke — checks it runs without error and doesn't crash on gaps) --

def test_report_runs_on_exam_with_no_ledger_rows_and_no_papers(capsys):
    """Must not error for an exam that doesn't even exist in `papers`/ledger."""
    conn = _conn()
    conn.row_factory = sqlite3.Row
    report(conn, "nonexistent_exam")
    captured = capsys.readouterr()
    assert "nonexistent_exam" not in captured.out  # nothing to report, prints nothing for it


def test_report_flags_unrecorded_paper():
    conn = _conn()
    _seed_exam_paper(conn, "upsc_cse", "eco_optional_1")
    conn.row_factory = sqlite3.Row

    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        report(conn, "upsc_cse")
    out = buf.getvalue()
    assert "NO LEDGER ROWS" in out
    assert "eco_optional_1" in out


def test_report_never_hides_partial_or_unaudited_row(capsys):
    conn = _conn()
    _seed_exam_paper(conn, "upsc_cse", "eco_optional_1")
    _seed_exam_paper(conn, "upsc_cse", "eco_optional_2")
    conn.row_factory = sqlite3.Row

    record(conn, "upsc_cse", "eco_optional_1", 2019, expected_count=8, source_reference="s1.pdf")
    record(conn, "upsc_cse", "eco_optional_2", 2020, expected_count=None, source_reference=None)

    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        report(conn, "upsc_cse")
    out = buf.getvalue()

    assert "PARTIAL" in out
    assert "UNAUDITED" in out
    assert "2019" in out
    assert "2020" in out
