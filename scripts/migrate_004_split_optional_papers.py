"""One-time migration (DECIDE-25): splits eco_optional/law_optional into Paper I/II.

Every UPSC Optional subject is 2 compulsory papers/year with disjoint syllabi (e.g.
Economics Paper I = theory, Paper II = Indian economy) — DECIDE-21's restructuring
correctly split mains_gs into gs1-gs4 but left the two Optionals as one paper row each.
Caught before any dependent data existed (zero rows in exam_topics/pyq_bank/sections
referenced either paper_id), so this is a clean rename+split, not a data migration.

Run: .venv/bin/python scripts/migrate_004_split_optional_papers.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "core.db"

OLD_PAPER_IDS = ["eco_optional", "law_optional"]

NEW_PAPERS = [
    ("upsc_cse", "eco_optional_1", "CSE Mains — Economics Optional Paper I"),
    ("upsc_cse", "eco_optional_2", "CSE Mains — Economics Optional Paper II"),
    ("upsc_cse", "law_optional_1", "CSE Mains — Law Optional Paper I (placeholder, no content yet)"),
    ("upsc_cse", "law_optional_2", "CSE Mains — Law Optional Paper II (placeholder, no content yet)"),
]


def _already_migrated(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) FROM papers WHERE exam_id = 'upsc_cse' AND paper_id = 'eco_optional_1'"
    ).fetchone()
    return row[0] > 0


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF")

    if _already_migrated(conn):
        print("Already migrated — nothing to do.")
        conn.close()
        return

    for table, col in [
        ("exam_topics", "paper_id"),
        ("pyq_bank", "paper_id"),
        ("sections", "paper_id"),
    ]:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if col not in cols:
            continue
        n = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {col} IN ('eco_optional', 'law_optional')"
        ).fetchone()[0]
        if n:
            raise RuntimeError(
                f"{table}.{col} has {n} row(s) referencing the old paper_id — "
                "this migration assumes zero dependent data, aborting."
            )

    conn.execute(
        "DELETE FROM papers WHERE exam_id = 'upsc_cse' AND paper_id IN (?, ?)",
        OLD_PAPER_IDS,
    )
    conn.executemany(
        "INSERT INTO papers (exam_id, paper_id, name) VALUES (?, ?, ?)", NEW_PAPERS
    )
    conn.commit()

    rows = conn.execute(
        "SELECT paper_id, name FROM papers WHERE exam_id = 'upsc_cse' ORDER BY paper_id"
    ).fetchall()
    print("upsc_cse papers after migration:")
    for paper_id, name in rows:
        print(f"  {paper_id}: {name}")

    conn.close()


if __name__ == "__main__":
    main()
