"""One-time migration (DECIDE-28): adds source-file provenance to pyq_bank.

Rahul's explicit ask: always be able to trace a question back to the exact file it came
from, and a verified answer back to the exact key file that verified it — so if a source is
later found to be wrong, the affected rows can be found and re-checked, not guessed at.

Run: .venv/bin/python scripts/migrate_006_source_provenance.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "core.db"

# Best-effort backfill for the two documents already ingested before this column existed.
BACKFILL_SOURCE_FILE = [
    # (exam_id, year, source_file)
    ("upsc_epfo_apfc_eo_ao", 2025,
     "data/raw_ingest_staging/upsc_epfo_apfc_eo_ao/epfo_apfc_eoao_2025.pdf"),
    ("upsc_epfo_apfc_eo_ao", 2023,
     "data/raw_ingest_staging/upsc_epfo_apfc_eo_ao/eoao_gat_2023_notebooklm.pdf"),
]
BACKFILL_ANSWER_KEY_FILE = [
    # (exam_id, year, status, answer_key_file) — only rows already merged from a real key
    ("upsc_epfo_apfc_eo_ao", 2023, "verified",
     "UPSC-EPFO-EO-AO-Answer-Key-2023.pdf#series=A"),
]


def _already_migrated(conn: sqlite3.Connection) -> bool:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(pyq_bank)").fetchall()]
    return "source_file" in cols


def main() -> None:
    conn = sqlite3.connect(DB_PATH)

    if _already_migrated(conn):
        print("Already migrated — nothing to do.")
        conn.close()
        return

    conn.execute("ALTER TABLE pyq_bank ADD COLUMN source_file TEXT")
    conn.execute("ALTER TABLE pyq_bank ADD COLUMN answer_key_file TEXT")

    for exam_id, year, source_file in BACKFILL_SOURCE_FILE:
        n = conn.execute(
            "UPDATE pyq_bank SET source_file = ? WHERE exam_id = ? AND year = ? "
            "AND source_file IS NULL",
            (source_file, exam_id, year),
        ).rowcount
        print(f"Backfilled source_file for {n} row(s): {exam_id}/{year} -> {source_file}")

    for exam_id, year, status, answer_key_file in BACKFILL_ANSWER_KEY_FILE:
        n = conn.execute(
            "UPDATE pyq_bank SET answer_key_file = ? WHERE exam_id = ? AND year = ? "
            "AND status = ? AND answer_key_file IS NULL",
            (answer_key_file, exam_id, year, status),
        ).rowcount
        print(f"Backfilled answer_key_file for {n} row(s): {exam_id}/{year} -> {answer_key_file}")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
