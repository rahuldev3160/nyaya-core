"""Extracts a real, scanned UPSC-format answer key PDF into structured
{question_number: option_letter} data (DECIDE-27).

This is transcription, not solving: Haiku is shown an image of a printed grid (e.g.
"1 B 16 D 31 D ...") and asked to read it back as JSON — the exact same category of task as
OCR'ing question text, never asked to judge which option is correct. The real correctness
already exists on the printed page; this script only makes it machine-readable.

Also captures the exam's own header fields (Series letter, dropped-item numbers) since a
key only lines up with a question paper of the SAME series (UPSC EPFO papers run 4 series —
A/B/C/D — with different question ordering per series), and a dropped item has no valid
option letter at all — it must come through as `void`, never a guessed/blank letter.

Usage:
    .venv/bin/python scripts/extract_answer_key.py --pdf /path/to/key.pdf --out key.json
"""

import argparse
import base64
import json
import os
import sys
import tempfile
from pathlib import Path

import anthropic
import pdfplumber
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(Path(__file__).parent.parent / ".env")

MODEL = os.getenv("AI_MODEL_FAST", "claude-haiku-4-5-20251001")

SYSTEM_PROMPT = """You are transcribing a scanned official UPSC exam answer-key sheet. This \
is a literal reading task, not a judgment task — you are copying printed characters off a \
page, the same as OCR. Never decide or infer which answer is correct; only report what is \
printed.

The sheet is a grid of (question number, option letter) pairs, e.g. "1 B 16 D 31 D 46 D", \
meaning question 1's key is B, question 16's is D, etc. It may also show header fields \
(Examination name/date, Series letter, Max marks, No. of items dropped, Items taken for \
scoring) and may mark a dropped/voided question with an "X" or a crossed-out cell instead \
of a letter.

Output ONLY a single JSON object, no markdown fences, no explanation:
{
  "series": "<the Series letter printed on this sheet, e.g. 'A', or null if not visible on this page>",
  "exam_label": "<the exam name/date/code printed on this sheet, or null if not visible on this page>",
  "answers": {"<question_number>": "<option_letter>", ...},
  "dropped": [<question numbers marked as dropped/void/X on this page, as ints>]
}
Include only question numbers actually visible on THIS page/image — do not guess numbers \
that aren't shown. If a cell is illegible, omit that question number rather than guessing.
"""


def render_pages(pdf_path: Path, resolution: int = 200) -> list[bytes]:
    images = []
    with pdfplumber.open(pdf_path) as pdf, tempfile.TemporaryDirectory() as tmp:
        buf_path = Path(tmp) / "page.png"
        for page in pdf.pages:
            im = page.to_image(resolution=resolution)
            im.save(str(buf_path))
            images.append(buf_path.read_bytes())
    return images


def extract_page(client: anthropic.Anthropic, image_bytes: bytes) -> dict:
    b64 = base64.standard_b64encode(image_bytes).decode()
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                {"type": "text", "text": "Transcribe this answer-key page as the JSON shape described."},
            ],
        }],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    client = anthropic.Anthropic()
    pages = render_pages(args.pdf)

    # These official key PDFs consistently carry ONE series' full grid per page (UPSC runs
    # 4 series — A/B/C/D — with different question ordering per series, confirmed via a
    # handwritten note on the real 2017 key and directly observed: page 1 = Series A, page 2
    # = Series B, etc. on the 2023 key). Keyed by series, never merged across pages — a
    # first naive merge-everything-together attempt produced ~100 false conflicts because
    # Series A's Q1=D and Series B's Q1=D-different-question were treated as the same cell.
    by_series: dict[str, dict] = {}
    exam_label: str | None = None

    for i, img in enumerate(pages):
        page_data = extract_page(client, img)
        exam_label = exam_label or page_data.get("exam_label")
        series = page_data.get("series") or f"page{i+1}"
        answers = page_data.get("answers") or {}
        if not answers:
            continue
        by_series[series] = {
            "answers": answers,
            "dropped": sorted(page_data.get("dropped") or []),
        }
        print(f"page {i+1}/{len(pages)}: series={series!r}, {len(answers)} answers read")

    result = {
        "source_pdf": str(args.pdf),
        "exam_label": exam_label,
        "series": by_series,
    }
    args.out.write_text(json.dumps(result, indent=2))

    series_summary = ", ".join(f"{s} ({len(d['answers'])} answers)" for s, d in by_series.items())
    print(f"\nExam label: {exam_label!r}. Series found: {series_summary}")
    print(f"Written to {args.out}")
    print("Pick the series matching the actual question-paper PDF's own printed series "
          "before merging — do not assume Series A.")


if __name__ == "__main__":
    main()
