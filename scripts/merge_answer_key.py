"""Merges a real, extracted answer key (scripts/extract_answer_key.py's output) into
`pyq_bank.correct_option` (DECIDE-27). Pure data merge — no LLM call, no judgment: matches
by `question_number` and writes exactly what the key says.

Usage:
    .venv/bin/python scripts/merge_answer_key.py --exam-id upsc_epfo_apfc_eo_ao \\
        --paper-id gat --year 2023 --key-json data/answer_keys/..._2023.json --series A
"""

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "core.db"
VALID_LETTERS = {"A", "B", "C", "D"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--exam-id", required=True)
    parser.add_argument("--paper-id", required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--key-json", type=Path, required=True,
                         help="Output of scripts/extract_answer_key.py")
    parser.add_argument("--series", required=True,
                         help="Which series in the key file to apply — MUST match the "
                              "question paper's own printed series, never assumed.")
    parser.add_argument("--verified-by", default="upsc_official_key",
                         help="Provenance tag stored in pyq_bank.verified_by")
    args = parser.parse_args()

    key_data = json.loads(args.key_json.read_text())
    series_data = key_data.get("series", {}).get(args.series)
    if series_data is None:
        available = ", ".join(key_data.get("series", {}).keys())
        raise SystemExit(f"Series {args.series!r} not found in {args.key_json} "
                          f"(available: {available})")
    answers: dict[str, str] = series_data["answers"]
    dropped: set[int] = set(series_data.get("dropped", []))

    # A dropped item's cell often prints as "X" rather than a letter (confirmed on the real
    # 2012/2021 keys) — extract_answer_key.py can read that "X" straight into `answers`, so
    # only flag a bad letter for a question that ISN'T already accounted for as dropped.
    bad_letters = {qn: letter for qn, letter in answers.items()
                   if letter not in VALID_LETTERS and int(qn) not in dropped}
    if bad_letters:
        raise SystemExit(f"Key has non-A/B/C/D letter(s), refusing to merge: {bad_letters}")

    # Full provenance of exactly which file + series verified this batch (Rahul's ask,
    # DECIDE-28) — stored per-row so any answer can be traced back and re-checked later.
    answer_key_file = f"{key_data.get('source_pdf', args.key_json.name)}#series={args.series}"

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT question_id, question_number, options FROM pyq_bank "
        "WHERE exam_id = ? AND paper_id = ? AND year = ? AND question_format = 'mcq'",
        (args.exam_id, args.paper_id, args.year),
    ).fetchall()

    now = datetime.now(timezone.utc).isoformat()
    verified, voided, unmatched, no_number = 0, 0, 0, 0

    for question_id, question_number, options_json in rows:
        if question_number is None:
            no_number += 1
            continue
        qnum_str = str(question_number)
        options = json.loads(options_json) if options_json else []

        if question_number in dropped:
            conn.execute(
                "UPDATE pyq_bank SET status = 'void', correct_option = NULL, "
                "verified_by = ?, answer_key_file = ?, reviewed_at = ? WHERE question_id = ?",
                (args.verified_by, answer_key_file, now, question_id),
            )
            voided += 1
            continue

        letter = answers.get(qnum_str)
        if letter is None:
            unmatched += 1
            continue

        letter_index = ord(letter) - ord("A")
        if options and letter_index >= len(options):
            print(f"WARNING: {question_id} (Q{question_number}) key says '{letter}' but "
                  f"only has {len(options)} option(s) extracted — merging letter anyway, "
                  f"flag for manual review.")

        conn.execute(
            "UPDATE pyq_bank SET status = 'verified', correct_option = ?, "
            "verified_by = ?, answer_key_file = ?, reviewed_at = ? WHERE question_id = ?",
            (letter, args.verified_by, answer_key_file, now, question_id),
        )
        verified += 1

    conn.commit()

    total = len(rows)
    print(f"pyq_bank rows for {args.exam_id}/{args.paper_id}/{args.year}: {total}")
    print(f"  verified: {verified}")
    print(f"  void (dropped by UPSC): {voided}")
    print(f"  unmatched (question_number not in key): {unmatched}")
    if no_number:
        print(f"  skipped (no question_number captured at extraction time): {no_number}")
    key_qnums = {int(q) for q in answers} | dropped
    db_qnums = {qn for _, qn, _ in rows if qn is not None}
    missing_from_db = sorted(key_qnums - db_qnums)
    if missing_from_db:
        print(f"  key has {len(missing_from_db)} question number(s) with no matching DB row "
              f"at all (not extracted from the paper): {missing_from_db}")

    conn.close()


if __name__ == "__main__":
    main()
