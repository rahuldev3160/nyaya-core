"""Extract English-only pages from a bilingual scanned PDF (e.g. UPSC EPFO test booklets,
which print Part-B content twice — a Hindi page immediately followed by an English page for
the same questions). Ingesting both halves would double API cost for zero new content and
risk polluting chunks with English-OCR garbage read off Devanagari script (confirmed: an
eng-only Tesseract pass on a Hindi page produces coherent-looking but meaningless "words"
like "fermarraa" rather than empty output, so it silently passes a naive not-blank check).

Detection heuristic: OCR each page in English, count hits against a small English stopword
list. A raw "count ASCII-alphabetic tokens" filter does NOT work here — verified empirically
that Tesseract's eng model, fed a Devanagari page, still emits plenty of ASCII-alphabetic
garbage ("fermarraa", "arareren") that scores just as high as real English text on that
metric. Stopwords are the real discriminator: genuine English text is dense with them
("the", "which", "following", "select" recur constantly in this document family's
boilerplate); OCR garbage off Hindi script essentially never produces a real stopword by
chance. Empirically: real English pages scored 60-120 stopword hits, Hindi/blank pages
scored 0-3 — a wide, safe margin. This is a coarse filter tuned for this document family
(UPSC-style bilingual test booklets), not a general-purpose language detector.

Usage:
    .venv/bin/python scripts/extract_english_pages.py --input <bilingual.pdf> --output <english_only.pdf>
"""

import argparse
from pathlib import Path

import pytesseract
from pdf2image import convert_from_path

MIN_STOPWORD_HITS = 20
STOPWORDS = {
    "the", "of", "and", "is", "are", "in", "to", "which", "following", "select", "answer",
    "correct", "statement", "given", "below", "with", "codes", "using", "one", "not", "only",
    "for", "on", "as", "be", "or", "if", "by", "from", "this", "that",
}


def is_english_page(text: str) -> bool:
    tokens = [w.strip(".,;:()?").lower() for w in text.split()]
    return sum(1 for w in tokens if w in STOPWORDS) >= MIN_STOPWORD_HITS


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dpi", type=int, default=300)
    args = parser.parse_args()

    images = convert_from_path(str(args.input), dpi=args.dpi)
    kept = []
    for i, img in enumerate(images, start=1):
        text = pytesseract.image_to_string(img, lang="eng")
        hits = sum(1 for w in (t.strip(".,;:()?").lower() for t in text.split()) if w in STOPWORDS)
        keep = hits >= MIN_STOPWORD_HITS
        print(f"page {i}: {'KEEP' if keep else 'drop'} ({hits} stopword hits)")
        if keep:
            kept.append(img)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not kept:
        raise SystemExit("No English pages detected — check the input file or lower --dpi/threshold.")
    kept[0].save(str(args.output), save_all=True, append_images=kept[1:])
    print(f"Wrote {len(kept)}/{len(images)} pages to {args.output}")


if __name__ == "__main__":
    main()
