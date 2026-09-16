"""PYQ completeness ledger — record and report tooling for `pyq_completeness_ledger`
(DECIDE-35, see docs/decisions.md and migrate_013_pyq_completeness_ledger.py).

This is the reusable, exam-agnostic replacement for the kind of manual "compare our DB
against the real official PDFs year by year" audit Rahul had to run by hand for Scribe's
Eco Optional gaps. Once a row is recorded here, "how complete is our PYQ coverage" is a
query (`report`), not a fresh manual comparison.

Two subcommands:

  record — .venv/bin/python scripts/pyq_completeness.py record \\
               --exam_id upsc_cse --paper_id eco_optional_1 --year 2019 \\
               --expected_count 8 --source_reference "path/to/official_paper.pdf" \\
               [--gap_detail "Q5, Q7 missing"]

    Computes `actual_count` live from `pyq_bank` (never manually typed — it can't drift
    from what's actually ingested) and upserts the row. `--expected_count` is optional:
    omit it to just refresh `actual_count` for a row without claiming any real source has
    been checked yet — the row (or a freshly-inserted one) stays/becomes `unaudited`.

    Status is derived automatically, never passed in:
      - `expected_count` not given (still unknown)      -> 'unaudited'
      - `expected_count` given, `actual_count >= it`     -> 'complete'
      - `expected_count` given, `actual_count < it`      -> 'partial'
        (this includes the actual_count == 0 case — a fully quantified 100% gap is a real,
        known gap, i.e. 'partial', not 'unaudited'; 'unaudited' means the target itself is
        still unknown, not that the gap is total)

    Works fine for an exam/paper/year with zero `pyq_bank` rows at all (e.g. right now,
    every year of `upsc_cse`/`eco_optional_1`/`eco_optional_2`) — `actual_count` is simply 0,
    not an error.

  report — .venv/bin/python scripts/pyq_completeness.py report [--exam_id upsc_cse]

    Prints every ledger row for the given exam (or every exam, if omitted), grouped by
    exam then paper. Every non-'complete' row is ALWAYS printed explicitly — this table
    exists specifically so a partial/unaudited year can never hide inside an aggregate
    percentage (mirrors the `layered-coverage` skill's anti-false-positive rule: a
    higher-level rollup must never hide a lower-level gap). Non-complete rows are listed
    first, worst-covered first; a one-line summary count comes after, never instead of, the
    explicit listing. Also flags any paper registered in `papers` for the exam that has NO
    ledger row at all yet — an un-recorded paper is not the same as a 'complete' one, and
    silently omitting it from the report would itself be a false positive.
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "core.db"


def _actual_count(conn: sqlite3.Connection, exam_id: str, paper_id: str, year: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM pyq_bank WHERE exam_id = ? AND paper_id = ? AND year = ?",
        (exam_id, paper_id, year),
    ).fetchone()
    return row[0]


def _derive_status(expected_count: int | None, actual_count: int) -> str:
    if expected_count is None:
        return "unaudited"
    if actual_count >= expected_count:
        return "complete"
    return "partial"


def record(
    conn: sqlite3.Connection,
    exam_id: str,
    paper_id: str,
    year: int,
    expected_count: int | None,
    source_reference: str | None,
    gap_detail: str | None = None,
) -> dict:
    """Upsert one (exam_id, paper_id, year) ledger row. Returns the row as a dict."""
    actual_count = _actual_count(conn, exam_id, paper_id, year)
    status = _derive_status(expected_count, actual_count)
    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        """
        INSERT INTO pyq_completeness_ledger
            (exam_id, paper_id, year, expected_count, actual_count,
             source_reference, status, gap_detail, last_audited_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(exam_id, paper_id, year) DO UPDATE SET
            expected_count   = excluded.expected_count,
            actual_count     = excluded.actual_count,
            source_reference = excluded.source_reference,
            status           = excluded.status,
            gap_detail       = excluded.gap_detail,
            last_audited_at  = excluded.last_audited_at
        """,
        (
            exam_id,
            paper_id,
            year,
            expected_count,
            actual_count,
            source_reference,
            status,
            gap_detail,
            now,
        ),
    )
    conn.commit()

    return {
        "exam_id": exam_id,
        "paper_id": paper_id,
        "year": year,
        "expected_count": expected_count,
        "actual_count": actual_count,
        "source_reference": source_reference,
        "status": status,
        "gap_detail": gap_detail,
        "last_audited_at": now,
    }


def _coverage_sort_key(row: sqlite3.Row) -> tuple:
    """Worst-covered first. Unaudited rows sort before quantified partial gaps (an unknown
    target is at least as urgent as a known one, arguably more so — nobody has even checked
    yet), which sort by ascending coverage ratio (emptiest gap first). Complete rows never
    reach this function's callers for the "always show" list, but it's still used to order
    them last/by year in the full per-paper listing."""
    if row["status"] == "unaudited":
        return (0, 0.0, row["year"])
    if row["status"] == "partial":
        ratio = row["actual_count"] / row["expected_count"] if row["expected_count"] else 0.0
        return (1, ratio, row["year"])
    return (2, 1.0, row["year"])


def report(conn: sqlite3.Connection, exam_id: str | None) -> None:
    conn.row_factory = sqlite3.Row

    if exam_id:
        exam_ids = [exam_id]
    else:
        exam_ids = [r["exam_id"] for r in conn.execute("SELECT exam_id FROM exams ORDER BY exam_id")]

    any_noncomplete = False

    for eid in exam_ids:
        papers = [
            dict(r)
            for r in conn.execute(
                "SELECT exam_id, paper_id FROM papers WHERE exam_id = ? ORDER BY paper_id", (eid,)
            )
        ]
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM pyq_completeness_ledger WHERE exam_id = ? ORDER BY paper_id, year",
                (eid,),
            )
        ]

        papers_with_rows = {(r["exam_id"], r["paper_id"]) for r in rows}
        unrecorded_papers = [p for p in papers if (p["exam_id"], p["paper_id"]) not in papers_with_rows]

        if not rows and not unrecorded_papers:
            continue  # exam has no papers and no ledger rows — nothing to report

        print(f"\n=== {eid} ===")

        if unrecorded_papers:
            for p in unrecorded_papers:
                print(f"  [NO LEDGER ROWS] paper_id={p['paper_id']!r} — never recorded, "
                      f"not audited for any year yet")
                any_noncomplete = True

        noncomplete = sorted(
            (r for r in rows if r["status"] != "complete"),
            key=lambda r: (
                0 if r["status"] == "unaudited" else 1,
                (r["actual_count"] / r["expected_count"]) if r.get("expected_count") else 0.0,
                r["paper_id"],
                r["year"],
            ),
        )
        complete = sorted((r for r in rows if r["status"] == "complete"), key=lambda r: (r["paper_id"], r["year"]))

        for r in noncomplete:
            any_noncomplete = True
            expected_str = r["expected_count"] if r["expected_count"] is not None else "?"
            print(
                f"  [{r['status'].upper():9s}] paper_id={r['paper_id']!r} year={r['year']} "
                f"actual={r['actual_count']} expected={expected_str} "
                f"source={r['source_reference'] or '(none)'} "
                f"gap_detail={r['gap_detail'] or '(none)'}"
            )

        for r in complete:
            print(
                f"  [COMPLETE ] paper_id={r['paper_id']!r} year={r['year']} "
                f"actual={r['actual_count']} expected={r['expected_count']} "
                f"source={r['source_reference'] or '(none)'}"
            )

        total = len(rows)
        n_complete = len(complete)
        n_partial = sum(1 for r in rows if r["status"] == "partial")
        n_unaudited = sum(1 for r in rows if r["status"] == "unaudited")
        print(
            f"  -- summary: {total} recorded row(s) "
            f"({n_complete} complete, {n_partial} partial, {n_unaudited} unaudited), "
            f"{len(unrecorded_papers)} paper(s) with no ledger row at all --"
        )

    if not any_noncomplete and exam_ids:
        print("\nNo partial/unaudited/unrecorded rows found — but check the summaries above; "
              "an exam/paper with zero rows at all is reported separately, not silently clean.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record/report real-vs-expected PYQ counts per (exam_id, paper_id, year)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_record = sub.add_parser("record", help="Upsert one ledger row, computing actual_count live.")
    p_record.add_argument("--exam_id", required=True)
    p_record.add_argument("--paper_id", required=True)
    p_record.add_argument("--year", type=int, required=True)
    p_record.add_argument(
        "--expected_count", type=int, default=None,
        help="Real count from an authoritative source. Omit if not yet known (row stays/becomes 'unaudited')."
    )
    p_record.add_argument(
        "--source_reference", default=None,
        help="Where expected_count came from — a real file path or citation. Required alongside --expected_count in practice, but not enforced here so a source-refresh-only call (no --expected_count) doesn't need one."
    )
    p_record.add_argument("--gap_detail", default=None, help="Which specific question numbers are missing, if known.")

    p_report = sub.add_parser("report", help="Print every ledger row, worst-covered first, never rolled up only.")
    p_report.add_argument("--exam_id", default=None, help="Limit to one exam; omit for every exam.")

    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")

    if args.command == "record":
        row = record(
            conn,
            exam_id=args.exam_id,
            paper_id=args.paper_id,
            year=args.year,
            expected_count=args.expected_count,
            source_reference=args.source_reference,
            gap_detail=args.gap_detail,
        )
        print(
            f"Recorded {row['exam_id']}/{row['paper_id']}/{row['year']}: "
            f"actual={row['actual_count']} expected={row['expected_count']} status={row['status']}"
        )
    elif args.command == "report":
        report(conn, args.exam_id)

    conn.close()


if __name__ == "__main__":
    main()
