"""Extracts a real, ALREADY-DIGITAL-TEXT answer key PDF into the same structured
{question_number: option_letter} JSON shape `scripts/extract_answer_key.py` produces
(DECIDE-27) — so `scripts/merge_answer_key.py` can merge either kind of key unmodified.

`extract_answer_key.py` exists for a SCANNED (image-only) key and uses Haiku vision to
transcribe it. That's the wrong tool here: this key (e.g. the real Next IAS RBI DEPR Set-1
key) is a normal digital-text PDF — `pdfplumber` can read the printed characters directly,
with zero LLM involvement at all (stricter than DECIDE-27 requires, which only bans an LLM
from JUDGING the answer — here there isn't even a transcription judgment call to make).

Expected on-page format: a flat or multi-column list of "<number>. (<letter>)" or
"<number>. <letter>" pairs, e.g. "1. (d)" / "14. (c)" / "27.  (d)" — one answer key per PDF,
no series concept (unlike the UPSC EPFO scanned keys, which print 4 series per PDF). Stored
under a single synthetic series key you choose via --series (e.g. "SET1") so
`merge_answer_key.py --series SET1` picks it deterministically.

Usage:
    .venv/bin/python scripts/extract_answer_key_digital.py \\
        --pdf ".../RBI-DEPR (Prelims) Set-1 (2025) Anskey.pdf" \\
        --out data/answer_keys/rbi_depr_phase1_p1_set1_2025.json --series SET1
"""

import argparse
import json
import re
from pathlib import Path

import pdfplumber

# "12. (c)" / "12.(c)" / "12. c" / "12) (c)" — letter always a single a-d/A-D, question
# number always the token immediately before it. Applied per-line after normalizing
# whitespace, so multi-column PDFs (several "N. (L)" pairs on one visual line) still match
# every occurrence via re.findall, not just the first per line.
ANSWER_PATTERN = re.compile(r"(\d{1,3})\s*[.)]\s*\(?\s*([A-Da-d])\s*\)?")


def parse_answer_text(text: str) -> dict[str, str]:
    """Pure function, no I/O — parses already-extracted page text into {question_number:
    LETTER}. Uppercases every letter (the source prints lowercase "(d)") to match
    `merge_answer_key.py`'s VALID_LETTERS = {"A","B","C","D"}. Last occurrence of a given
    question number wins (defensive against a running header/footer accidentally matching
    the pattern) rather than first, since real content pages come after any cover page.
    """
    answers: dict[str, str] = {}
    for qnum, letter in ANSWER_PATTERN.findall(text):
        answers[qnum] = letter.upper()
    return answers


def extract_pdf_text(pdf_path: Path) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--series", required=True,
                         help="Synthetic series label for this single-series key, e.g. 'SET1'.")
    parser.add_argument("--exam-label", default=None)
    args = parser.parse_args()

    text = extract_pdf_text(args.pdf)
    answers = parse_answer_text(text)
    if not answers:
        raise SystemExit(f"No '<number>. (<letter>)' pairs found in {args.pdf} — is this "
                          f"really a digital-text PDF? Check with pdfplumber directly before "
                          f"assuming this script is broken.")

    result = {
        "source_pdf": str(args.pdf),
        "exam_label": args.exam_label,
        "series": {
            args.series: {
                "answers": answers,
                "dropped": [],  # no dropped-item marker exists in this key's format
            }
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))

    qnums = sorted(int(q) for q in answers)
    print(f"Parsed {len(answers)} answers, question numbers {qnums[0]}-{qnums[-1]} "
          f"(gaps: {sorted(set(range(qnums[0], qnums[-1] + 1)) - set(qnums)) or 'none'}).")
    print(f"Written to {args.out}")


if __name__ == "__main__":
    main()
