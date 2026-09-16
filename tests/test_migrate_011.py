"""Tests for scripts/migrate_011_user_attempts_coverage.py — runs against a throwaway
sqlite file (never data/core.db), by monkeypatching the module's DB_PATH constant, same
approach as the other real-schema tests in this suite (e.g. tests/test_enrich.py's
throwaway in-memory DB pattern)."""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import migrate_011_user_attempts_coverage as migration


def _fresh_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "core.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE exams (exam_id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE topics (topic_id TEXT PRIMARY KEY, name TEXT NOT NULL, parent_topic_id TEXT);
        CREATE TABLE pyq_bank (question_id TEXT PRIMARY KEY, exam_id TEXT NOT NULL, topic_id TEXT);
        """
    )
    conn.commit()
    conn.close()
    return db_path


def test_migration_creates_both_tables(tmp_path, monkeypatch):
    db_path = _fresh_db(tmp_path)
    monkeypatch.setattr(migration, "DB_PATH", db_path)

    migration.main()

    conn = sqlite3.connect(db_path)
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    conn.close()
    assert "user_attempts" in tables
    assert "topic_coverage" in tables


def test_user_attempts_schema_has_expected_columns(tmp_path, monkeypatch):
    db_path = _fresh_db(tmp_path)
    monkeypatch.setattr(migration, "DB_PATH", db_path)
    migration.main()

    conn = sqlite3.connect(db_path)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(user_attempts)").fetchall()}
    conn.close()
    assert cols == {
        "attempt_id",
        "question_id",
        "chosen_option",
        "correct_option",
        "is_correct",
        "attempted_at",
    }


def test_topic_coverage_schema_has_expected_columns_and_composite_pk(tmp_path, monkeypatch):
    db_path = _fresh_db(tmp_path)
    monkeypatch.setattr(migration, "DB_PATH", db_path)
    migration.main()

    conn = sqlite3.connect(db_path)
    info = conn.execute("PRAGMA table_info(topic_coverage)").fetchall()
    conn.close()
    cols = {r[1] for r in info}
    assert cols == {
        "exam_id",
        "topic_id",
        "attempts_count",
        "accuracy",
        "coverage_depth",
        "last_computed_at",
    }
    pk_cols = {r[1] for r in info if r[5] > 0}  # PRAGMA table_info col 5 = pk order (0 = not pk)
    assert pk_cols == {"exam_id", "topic_id"}


def test_migration_is_idempotent_running_twice_does_not_error(tmp_path, monkeypatch):
    db_path = _fresh_db(tmp_path)
    monkeypatch.setattr(migration, "DB_PATH", db_path)

    migration.main()
    migration.main()  # must not raise "table already exists"

    conn = sqlite3.connect(db_path)
    count = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='user_attempts'"
    ).fetchone()[0]
    conn.close()
    assert count == 1


def test_user_attempts_question_id_fk_references_pyq_bank(tmp_path, monkeypatch):
    """A real attempt row must be insertable once its question_id exists in pyq_bank."""
    db_path = _fresh_db(tmp_path)
    monkeypatch.setattr(migration, "DB_PATH", db_path)
    migration.main()

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute(
        "INSERT INTO pyq_bank (question_id, exam_id, topic_id) VALUES ('q1', 'fake_exam', 't1')"
    )
    conn.execute(
        "INSERT INTO user_attempts (question_id, chosen_option, correct_option, is_correct, attempted_at) "
        "VALUES ('q1', 'A', 'A', 1, '2026-09-16T00:00:00+00:00')"
    )
    conn.commit()
    row = conn.execute("SELECT COUNT(*) FROM user_attempts").fetchone()
    conn.close()
    assert row[0] == 1
