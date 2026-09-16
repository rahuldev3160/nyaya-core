"""Tests for scripts/migrate_013_pyq_completeness_ledger.py — runs against a throwaway
sqlite file (never data/core.db), by monkeypatching the module's DB_PATH constant, same
approach as tests/test_migrate_011.py."""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import migrate_013_pyq_completeness_ledger as migration


def _fresh_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "core.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE exams (exam_id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE papers (exam_id TEXT NOT NULL, paper_id TEXT NOT NULL, name TEXT NOT NULL, PRIMARY KEY (exam_id, paper_id));
        """
    )
    conn.commit()
    conn.close()
    return db_path


def test_migration_creates_table(tmp_path, monkeypatch):
    db_path = _fresh_db(tmp_path)
    monkeypatch.setattr(migration, "DB_PATH", db_path)

    migration.main()

    conn = sqlite3.connect(db_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert "pyq_completeness_ledger" in tables


def test_schema_has_expected_columns_and_composite_pk(tmp_path, monkeypatch):
    db_path = _fresh_db(tmp_path)
    monkeypatch.setattr(migration, "DB_PATH", db_path)
    migration.main()

    conn = sqlite3.connect(db_path)
    info = conn.execute("PRAGMA table_info(pyq_completeness_ledger)").fetchall()
    conn.close()
    cols = {r[1] for r in info}
    assert cols == {
        "exam_id",
        "paper_id",
        "year",
        "expected_count",
        "actual_count",
        "source_reference",
        "status",
        "gap_detail",
        "last_audited_at",
    }
    pk_cols = {r[1] for r in info if r[5] > 0}
    assert pk_cols == {"exam_id", "paper_id", "year"}


def test_status_check_constraint_rejects_bad_value(tmp_path, monkeypatch):
    db_path = _fresh_db(tmp_path)
    monkeypatch.setattr(migration, "DB_PATH", db_path)
    migration.main()

    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO exams (exam_id, name, created_at) VALUES ('e1', 'E1', 't')")
    conn.execute("INSERT INTO papers (exam_id, paper_id, name) VALUES ('e1', 'p1', 'P1')")
    conn.commit()
    try:
        conn.execute(
            "INSERT INTO pyq_completeness_ledger (exam_id, paper_id, year, status) "
            "VALUES ('e1', 'p1', 2020, 'bogus')"
        )
        conn.commit()
        raised = False
    except sqlite3.IntegrityError:
        raised = True
    conn.close()
    assert raised


def test_status_index_exists(tmp_path, monkeypatch):
    db_path = _fresh_db(tmp_path)
    monkeypatch.setattr(migration, "DB_PATH", db_path)
    migration.main()

    conn = sqlite3.connect(db_path)
    indices = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='pyq_completeness_ledger'"
        ).fetchall()
    }
    conn.close()
    assert "idx_pyq_completeness_status" in indices


def test_migration_is_idempotent(tmp_path, monkeypatch):
    db_path = _fresh_db(tmp_path)
    monkeypatch.setattr(migration, "DB_PATH", db_path)

    migration.main()
    migration.main()  # must not raise "table already exists"

    conn = sqlite3.connect(db_path)
    count = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='pyq_completeness_ledger'"
    ).fetchone()[0]
    conn.close()
    assert count == 1


def test_paper_fk_requires_registered_paper(tmp_path, monkeypatch):
    """A ledger row can't reference a paper that was never registered in `papers`."""
    db_path = _fresh_db(tmp_path)
    monkeypatch.setattr(migration, "DB_PATH", db_path)
    migration.main()

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("INSERT INTO exams (exam_id, name, created_at) VALUES ('e1', 'E1', 't')")
    conn.commit()
    try:
        conn.execute(
            "INSERT INTO pyq_completeness_ledger (exam_id, paper_id, year, status) "
            "VALUES ('e1', 'never_registered', 2020, 'unaudited')"
        )
        conn.commit()
        raised = False
    except sqlite3.IntegrityError:
        raised = True
    conn.close()
    assert raised
