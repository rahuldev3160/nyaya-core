"""Migration (DECIDE-35, see docs/decisions.md): adds `pyq_completeness_ledger`, a
permanent, exam-agnostic table for answering "how much of the real exam's PYQ content do we
actually have, year by year" with a query instead of a manual audit.

**Why this exists:** Rahul noticed Scribe (a sibling product) shows incomplete PYQ counts
for some years of UPSC Economics Optional, and a separate, parallel audit is finding the
exact real gaps there by hand (comparing Scribe's DB against official scanned exam PDFs).
That audit is a one-off. This table is the reusable infrastructure so the *next* time this
question comes up — for any exam, not just Eco Optional — it's a `SELECT`, not a fresh
manual comparison.

Grain: one row per (exam_id, paper_id, year) — the finest level "how complete is this year's
content" makes sense at. Deliberately NOT per-topic or per-question — this ledger tracks
*count* completeness against a real external source, not classification/tagging quality
(that's `pyq_bank.status`/`source_type`'s job, a different axis entirely).

Fields:
  - `expected_count`  — the REAL count from an authoritative source (official PDF, official
    answer key, or official notification pattern). Nullable — a year nobody has checked yet
    has no expected_count, which is exactly what `status='unaudited'` means. Never invented,
    never inferred from `actual_count`.
  - `actual_count`    — live COUNT(*) from `pyq_bank` for this (exam_id, paper_id, year),
    computed by `scripts/pyq_completeness.py`'s `record` command every time it runs — never
    manually typed, so it can't silently drift from the real ingested data.
  - `source_reference` — free text: where `expected_count` came from. A real file path or
    citation (e.g. "data/answer_keys/upsc_eco_opt1_2019_official.pdf") — never invented, per
    this project's "no false positives" philosophy (DECIDE-27/28's provenance discipline).
  - `status` — `complete` (actual >= expected) / `partial` (expected known, actual short of
    it) / `unaudited` (expected_count not yet known — the default; matches `topic_coverage`'s
    "no row = untested" anti-false-positive rule in spirit, except here the row DOES exist
    once anyone runs `record`, because `actual_count` is worth tracking even before a real
    source has been checked).
  - `gap_detail` — free text: which specific question numbers are missing, when knowable
    (e.g. "Q5, Q7 missing"). Nullable — often not knowable until someone actually diffs
    against the source.
  - `last_audited_at` — ISO timestamp of the last time `record` was run for this row (i.e.
    the last time a human actually looked at a source and typed in an expected_count/
    source_reference — not just the last time `actual_count` was refreshed against
    `pyq_bank`, though today those happen together in the same `record` call).

Composite PK `(exam_id, paper_id, year)` — mirrors `papers`' own `(exam_id, paper_id)`
composite-PK pattern (DECIDE-21: a child entity's key shouldn't have to repeat its parent's
identity, `paper_id` alone is not globally unique). Gives SQLite's automatic unique index on
the full triple for free (same as `papers`' `sqlite_autoindex_papers_1`) — that's the "proper
index on (exam_id, paper_id, year)" the design calls for, not a redundant duplicate index.
A separate `idx_pyq_completeness_status` index is added because "every partial/unaudited row"
is a real, common query this table exists to serve fast, and `status` isn't a prefix of the
PK so it needs its own index.

FK is the composite `(exam_id, paper_id) REFERENCES papers(exam_id, paper_id)` — same
pattern `pyq_bank`'s own FK already uses (DECIDE-21) — so a ledger row can't reference a
paper that was never registered.

Nothing exam-specific is hardcoded here — this must generalize across every exam/paper this
platform will ever hold.

Run: .venv/bin/python scripts/migrate_013_pyq_completeness_ledger.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "core.db"


def _already_migrated(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='pyq_completeness_ledger'"
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
        CREATE TABLE pyq_completeness_ledger (
            exam_id          TEXT NOT NULL REFERENCES exams(exam_id),
            paper_id         TEXT NOT NULL,
            year             INTEGER NOT NULL,
            expected_count   INTEGER,
            actual_count     INTEGER NOT NULL DEFAULT 0,
            source_reference TEXT,
            status           TEXT NOT NULL DEFAULT 'unaudited'
                                  CHECK (status IN ('complete', 'partial', 'unaudited')),
            gap_detail       TEXT,
            last_audited_at  TEXT,
            PRIMARY KEY (exam_id, paper_id, year),
            FOREIGN KEY (exam_id, paper_id) REFERENCES papers(exam_id, paper_id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX idx_pyq_completeness_status ON pyq_completeness_ledger(status)"
    )

    conn.commit()

    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='pyq_completeness_ledger'"
        ).fetchall()
    ]
    print(f"Created tables: {sorted(tables)}")
    conn.close()


if __name__ == "__main__":
    main()
