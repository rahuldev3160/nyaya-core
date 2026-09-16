"""Tests for scripts/migrate_012_recompute_rbi_depr_phase1p1_weight.py — runs against a
throwaway sqlite file (never data/core.db), monkeypatching the module's DB_PATH/EXAM_ID/
PAPER_ID/CURRENT_YEAR constants, same approach as tests/test_migrate_011.py."""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import migrate_012_recompute_rbi_depr_phase1p1_weight as migration


def _fresh_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "core.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE exam_topics (
            exam_id TEXT, paper_id TEXT, topic_id TEXT, weight REAL,
            PRIMARY KEY (exam_id, paper_id, topic_id)
        );
        CREATE TABLE pyq_bank (
            question_id TEXT PRIMARY KEY, exam_id TEXT, paper_id TEXT, topic_id TEXT,
            question_format TEXT, year INTEGER
        );
        """
    )
    conn.commit()
    conn.close()
    return db_path


def _seed(db_path: Path, exam_topics: list[tuple], pyqs: list[tuple]) -> None:
    conn = sqlite3.connect(db_path)
    conn.executemany(
        "INSERT INTO exam_topics (exam_id, paper_id, topic_id, weight) VALUES (?,?,?,?)",
        exam_topics,
    )
    conn.executemany(
        "INSERT INTO pyq_bank (question_id, exam_id, paper_id, topic_id, question_format, year) "
        "VALUES (?,?,?,?,'mcq',?)",
        pyqs,
    )
    conn.commit()
    conn.close()


def test_recomputes_flat_placeholder_into_real_frequency(tmp_path, monkeypatch):
    db_path = _fresh_db(tmp_path)
    monkeypatch.setattr(migration, "DB_PATH", db_path)
    monkeypatch.setattr(migration, "EXAM_ID", "rbi_depr")
    monkeypatch.setattr(migration, "PAPER_ID", "phase1_p1")
    monkeypatch.setattr(migration, "CURRENT_YEAR", 2026)

    _seed(
        db_path,
        exam_topics=[
            ("rbi_depr", "phase1_p1", "macro", 1.0),
            ("rbi_depr", "phase1_p1", "micro", 1.0),
        ],
        pyqs=[
            ("q1", "rbi_depr", "phase1_p1", "macro", 2025),
            ("q2", "rbi_depr", "phase1_p1", "macro", 2025),
            ("q3", "rbi_depr", "phase1_p1", "micro", 2025),
        ],
    )

    conn = sqlite3.connect(db_path)
    weight = migration.recompute_weights(conn)
    after = dict(conn.execute(
        "SELECT topic_id, weight FROM exam_topics WHERE exam_id='rbi_depr' AND paper_id='phase1_p1'"
    ).fetchall())
    conn.close()

    # decay = 0.9 ** (2026 - 2025) = 0.9 exactly
    assert after["macro"] == weight["macro"] == 2 * 0.9
    assert after["micro"] == weight["micro"] == 1 * 0.9


def test_only_touches_the_named_exam_and_paper(tmp_path, monkeypatch):
    db_path = _fresh_db(tmp_path)
    monkeypatch.setattr(migration, "DB_PATH", db_path)
    monkeypatch.setattr(migration, "EXAM_ID", "rbi_depr")
    monkeypatch.setattr(migration, "PAPER_ID", "phase1_p1")
    monkeypatch.setattr(migration, "CURRENT_YEAR", 2026)

    _seed(
        db_path,
        exam_topics=[
            ("rbi_depr", "phase1_p1", "macro", 1.0),
            ("rbi_depr", "phase2_p1", "macro", 0.5),  # different paper — must stay untouched
            ("other_exam", "phase1_p1", "macro", 1.0),  # different exam — must stay untouched
        ],
        pyqs=[("q1", "rbi_depr", "phase1_p1", "macro", 2025)],
    )

    conn = sqlite3.connect(db_path)
    migration.recompute_weights(conn)
    rows = dict(
        ((r[0], r[1]), r[2])
        for r in conn.execute("SELECT exam_id, paper_id, weight FROM exam_topics").fetchall()
    )
    conn.close()

    assert rows[("rbi_depr", "phase1_p1")] == 0.9
    assert rows[("rbi_depr", "phase2_p1")] == 0.5  # untouched placeholder
    assert rows[("other_exam", "phase1_p1")] == 1.0  # untouched placeholder


def test_topic_with_zero_real_questions_is_not_touched(tmp_path, monkeypatch):
    db_path = _fresh_db(tmp_path)
    monkeypatch.setattr(migration, "DB_PATH", db_path)
    monkeypatch.setattr(migration, "EXAM_ID", "rbi_depr")
    monkeypatch.setattr(migration, "PAPER_ID", "phase1_p1")
    monkeypatch.setattr(migration, "CURRENT_YEAR", 2026)

    _seed(
        db_path,
        exam_topics=[
            ("rbi_depr", "phase1_p1", "macro", 1.0),
            ("rbi_depr", "phase1_p1", "env_econ", 1.0),  # zero real questions this batch
        ],
        pyqs=[("q1", "rbi_depr", "phase1_p1", "macro", 2025)],
    )

    conn = sqlite3.connect(db_path)
    weight = migration.recompute_weights(conn)
    after = dict(conn.execute(
        "SELECT topic_id, weight FROM exam_topics WHERE exam_id='rbi_depr' AND paper_id='phase1_p1'"
    ).fetchall())
    conn.close()

    assert "env_econ" not in weight  # never touched — honestly still the old placeholder
    assert after["env_econ"] == 1.0
    assert after["macro"] == 0.9


def test_multi_year_decay_favors_more_recent_year(tmp_path, monkeypatch):
    db_path = _fresh_db(tmp_path)
    monkeypatch.setattr(migration, "DB_PATH", db_path)
    monkeypatch.setattr(migration, "EXAM_ID", "rbi_depr")
    monkeypatch.setattr(migration, "PAPER_ID", "phase1_p1")
    monkeypatch.setattr(migration, "CURRENT_YEAR", 2026)

    _seed(
        db_path,
        exam_topics=[("rbi_depr", "phase1_p1", "macro", 1.0)],
        pyqs=[
            ("q1", "rbi_depr", "phase1_p1", "macro", 2025),  # decay 0.9^1
            ("q2", "rbi_depr", "phase1_p1", "macro", 2020),  # decay 0.9^6
        ],
    )

    conn = sqlite3.connect(db_path)
    weight = migration.recompute_weights(conn)
    conn.close()

    expected = 0.9 ** 1 + 0.9 ** 6
    assert abs(weight["macro"] - expected) < 1e-9
