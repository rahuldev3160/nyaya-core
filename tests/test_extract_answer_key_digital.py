"""Tests for scripts/extract_answer_key_digital.py's pure parsing function — no PDF I/O,
no LLM call (this script never invokes one, unlike the scanned-key extract_answer_key.py).
Covers the real RBI DEPR Set-1 key's format ("1. (d)") plus edge cases the regex must
handle or reject."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from extract_answer_key_digital import parse_answer_text


def test_parses_dotted_parenthesized_format():
    text = "1. (d)\n2. (c)\n3. (b)"
    assert parse_answer_text(text) == {"1": "D", "2": "C", "3": "B"}


def test_uppercases_lowercase_letters():
    # The real Next IAS key prints lowercase letters throughout.
    text = "14. (c)\n15. (a)"
    assert parse_answer_text(text) == {"14": "C", "15": "A"}


def test_handles_multi_column_layout_on_one_extracted_line():
    # pdfplumber can flatten a 4-column PDF table into one line of running text.
    text = "1.  (d)     14.  (c)     27.  (d)     40.  (b)     53.  (b)"
    assert parse_answer_text(text) == {"1": "D", "14": "C", "27": "D", "40": "B", "53": "B"}


def test_accepts_no_parentheses_and_no_space_variants():
    text = "1.d\n2. c\n3.(B)"
    assert parse_answer_text(text) == {"1": "D", "2": "C", "3": "B"}


def test_ignores_unrelated_numeric_text():
    text = "RBI DEPR (Prelims) Set-1\nAnswer Keys\n1. (d)\nPage 2 of 3\n2. (c)"
    result = parse_answer_text(text)
    assert result == {"1": "D", "2": "C"}


def test_empty_text_returns_empty_dict():
    assert parse_answer_text("") == {}


def test_last_occurrence_of_a_question_number_wins():
    # Defensive against a running header/footer coincidentally matching the pattern.
    text = "1. (a)\n...\n1. (d)"
    assert parse_answer_text(text) == {"1": "D"}


def test_real_set1_sample_matches_visually_verified_source():
    # Sample drawn directly from the real RBI-DEPR (Prelims) Set-1 (2025) Anskey.pdf,
    # visually cross-checked against the source PDF before this session's ingestion.
    text = (
        "1. (d)\n2. (c)\n3. (b)\n4. (d)\n5. (b)\n"
        "...\n"
        "14. (c)\n...\n27. (d)\n...\n40. (b)\n...\n53. (b)\n...\n65. (c)"
    )
    result = parse_answer_text(text)
    assert result["1"] == "D"
    assert result["14"] == "C"
    assert result["27"] == "D"
    assert result["40"] == "B"
    assert result["53"] == "B"
    assert result["65"] == "C"
