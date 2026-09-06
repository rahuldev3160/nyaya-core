"""Sanity tests for src/ingestion/enrich.py — no real API calls (uses a fake client that
returns canned responses), proves the parsing/validation logic, not the prompt itself."""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.enrich import ReviewNeededError, build_chunk_metadata, build_pyq, parse_enrichment
from src.schema.models import MCQQuestion, TextChunk


def _fake_chunk() -> TextChunk:
    return TextChunk(
        content="Article 21 guarantees protection of life and personal liberty.",
        source_doc="constitution.pdf", page_number=5, section_id="constitution.pdf_s3", chunk_index=2,
    )


def test_json_fence_stripping():
    raw = '```json\n{"content_type": "study_material", "topic_id": "constitutional_framework", "context_prefix": "x", "is_pyq": false, "pyq": null}\n```'
    data = parse_enrichment(raw)
    assert data["content_type"] == "study_material"


def test_happy_path_produces_valid_chunk_metadata():
    data = {
        "content_type": "study_material", "topic_id": "constitutional_framework",
        "context_prefix": "From the Constitution's fundamental rights chapter.",
        "is_pyq": False, "pyq": None,
    }
    metadata = build_chunk_metadata(_fake_chunk(), exam_id="upsc_prelims_gs",
                                     source_type="official_pyq", data=data)
    assert metadata.chunk_id == "upsc_prelims_gs_constitution.pdf_5_2"
    assert metadata.topic_id == "constitutional_framework"


def test_null_topic_id_raises_review_needed_not_silent_default():
    data = {"content_type": "study_material", "topic_id": None, "context_prefix": "x",
            "is_pyq": False, "pyq": None}
    try:
        build_chunk_metadata(_fake_chunk(), "upsc_prelims_gs", "official_pyq", data)
        assert False, "should have raised"
    except ReviewNeededError:
        pass


def test_mcq_pyq_extraction():
    data = {
        "content_type": "mcq_pyq", "topic_id": "constitutional_framework", "context_prefix": "x",
        "is_pyq": True,
        "pyq": {"question_format": "mcq", "question_text": "Article 21 protects?",
                "year": 2023, "options": ["Life", "Property", "Speech", "None"],
                "correct_option": "Life"},
    }
    pyq = build_pyq("upsc_prelims_gs_constitution.pdf_5_2", "upsc_prelims_gs", "official_pyq", data)
    assert isinstance(pyq, MCQQuestion)
    assert pyq.year == 2023
    assert pyq.correct_option == "Life"


def test_mcq_pyq_missing_correct_option_raises_review_needed():
    data = {
        "content_type": "mcq_pyq", "topic_id": "constitutional_framework", "context_prefix": "x",
        "is_pyq": True,
        "pyq": {"question_format": "mcq", "question_text": "Article 21 protects?",
                "year": 2023, "options": ["Life", "Property"], "correct_option": None},
    }
    try:
        build_pyq("chunk_1", "upsc_prelims_gs", "official_pyq", data)
        assert False, "should have raised"
    except ReviewNeededError:
        pass


def test_pyq_missing_year_raises_review_needed():
    data = {
        "content_type": "mcq_pyq", "topic_id": "constitutional_framework", "context_prefix": "x",
        "is_pyq": True,
        "pyq": {"question_format": "mcq", "question_text": "x?", "year": None,
                "options": ["a", "b"], "correct_option": "a"},
    }
    try:
        build_pyq("chunk_1", "upsc_prelims_gs", "official_pyq", data)
        assert False, "should have raised"
    except ReviewNeededError:
        pass


def test_non_pyq_chunk_returns_no_pyq():
    data = {"content_type": "study_material", "topic_id": "constitutional_framework",
            "context_prefix": "x", "is_pyq": False, "pyq": None}
    assert build_pyq("chunk_1", "upsc_prelims_gs", "official_pyq", data) is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"PASS: {name}")
