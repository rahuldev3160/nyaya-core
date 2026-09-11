"""One-time migration (DECIDE-27): adds real answer-key support to pyq_bank.

Two changes:
1. Schema: `question_number` (needed to match a real key, which is always indexed by the
   printed question number) and `status` ('unverified'/'verified'/'void' — void covers a
   real, printed "item dropped from scoring" outcome, distinct from "not known yet").
2. Data fix: the 36 rows already in pyq_bank for the 2025 EPFO paper got their
   `correct_option` from Haiku guessing (enrich_chunk_system.txt used to literally ask for
   "text of the correct option, or null if not determinable") — the same untrusted-source
   problem as the NotebookLM-solved 2025 key, just baked into the original pipeline. Rahul's
   standing instruction (DECIDE-26, reaffirmed this session): no question is solved by the
   LLM, ever — correctness only enters via a real, human-sourced answer key. Reset those 36
   rows to unverified rather than let them look more trustworthy than they are.

Run: .venv/bin/python scripts/migrate_005_answer_key_support.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "core.db"


def _already_migrated(conn: sqlite3.Connection) -> bool:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(pyq_bank)").fetchall()]
    return "status" in cols


def main() -> None:
    conn = sqlite3.connect(DB_PATH)

    if _already_migrated(conn):
        print("Already migrated — nothing to do.")
        conn.close()
        return

    conn.execute("ALTER TABLE pyq_bank ADD COLUMN question_number INTEGER")
    conn.execute(
        "ALTER TABLE pyq_bank ADD COLUMN status TEXT NOT NULL DEFAULT 'unverified'"
    )

    reset = conn.execute(
        "UPDATE pyq_bank SET correct_option = NULL, verified_by = NULL, status = 'unverified' "
        "WHERE question_format = 'mcq' AND correct_option IS NOT NULL"
    )
    print(f"Reset {reset.rowcount} MCQ row(s) with a Haiku-guessed correct_option back to unverified.")

    # The 2025 paper's subject was General Ability Test (per its own filename) — register the
    # paper this exam has actually been ingesting under, and backfill the existing rows that
    # predate `papers` having any row for this exam at all.
    conn.execute(
        "INSERT OR IGNORE INTO papers (exam_id, paper_id, name) VALUES "
        "('upsc_epfo_apfc_eo_ao', 'gat', 'EPFO APFC/EO-AO — General Ability Test')"
    )
    backfilled = conn.execute(
        "UPDATE pyq_bank SET paper_id = 'gat' "
        "WHERE exam_id = 'upsc_epfo_apfc_eo_ao' AND paper_id IS NULL"
    )
    print(f"Backfilled paper_id='gat' on {backfilled.rowcount} existing row(s).")

    conn.commit()

    n = conn.execute(
        "SELECT COUNT(*) FROM pyq_bank WHERE exam_id = 'upsc_epfo_apfc_eo_ao'"
    ).fetchone()[0]
    print(f"upsc_epfo_apfc_eo_ao now has {n} pyq_bank row(s), all status='unverified'.")

    conn.close()


if __name__ == "__main__":
    main()
