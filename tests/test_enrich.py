"""Sanity tests for src/ingestion/enrich.py — no real API calls (uses a fake client that
returns canned responses), proves the parsing/validation logic, not the prompt itself."""

import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

import json

from src.ingestion.enrich import ReviewNeededError, build_chunk_metadata, build_pyqs, enrich_chunk, parse_enrichment
from src.schema.models import MCQQuestion, TextChunk

TOPICS = {"constitutional_framework", "parliament"}


def _fake_chunk() -> TextChunk:
    return TextChunk(
        content="Article 21 guarantees protection of life and personal liberty.",
        source_doc="constitution.pdf", page_number=5, section_id="constitution.pdf_s3", chunk_index=2,
    )


def test_json_fence_stripping():
    raw = '```json\n{"content_type": "study_material", "topic_id": "constitutional_framework", "context_prefix": "x", "pyqs": []}\n```'
    data = parse_enrichment(raw)
    assert data["content_type"] == "study_material"


def test_happy_path_produces_valid_chunk_metadata():
    data = {
        "content_type": "study_material", "topic_id": "constitutional_framework",
        "context_prefix": "From the Constitution's fundamental rights chapter.",
        "pyqs": [],
    }
    metadata = build_chunk_metadata(_fake_chunk(), exam_id="upsc_prelims_gs",
                                     source_type="official_pyq", data=data)
    assert metadata.chunk_id == "upsc_prelims_gs_constitution.pdf_5_2"
    assert metadata.topic_id == "constitutional_framework"


def test_null_topic_id_raises_review_needed_not_silent_default():
    data = {"content_type": "study_material", "topic_id": None, "context_prefix": "x", "pyqs": []}
    try:
        build_chunk_metadata(_fake_chunk(), "upsc_prelims_gs", "official_pyq", data)
        assert False, "should have raised"
    except ReviewNeededError:
        pass


def test_mcq_pyq_extraction():
    data = {
        "content_type": "mcq_pyq", "topic_id": "constitutional_framework", "context_prefix": "x",
        "pyqs": [{"question_format": "mcq", "question_text": "Article 21 protects?",
                  "year": 2023, "options": ["Life", "Property", "Speech", "None"],
                  "correct_option": "Life"}],
    }
    pyqs, failures = build_pyqs("upsc_prelims_gs_constitution.pdf_5_2", "upsc_prelims_gs",
                                 "official_pyq", data, TOPICS)
    assert failures == []
    assert len(pyqs) == 1
    assert isinstance(pyqs[0], MCQQuestion)
    assert pyqs[0].year == 2023
    assert pyqs[0].correct_option == "Life"
    assert pyqs[0].question_id == "upsc_prelims_gs_constitution.pdf_5_2_pyq_0"
    assert pyqs[0].topic_id == "constitutional_framework"


def test_multiple_pyqs_in_one_chunk_get_distinct_ids():
    """Real content (dense MCQ test booklets) can pack more than one complete question into
    one chunk — each must survive extraction and get a unique question_id, not silently
    collapse to just the first (BUG-07, discovered ingesting the real 2025 APFC/EO/AO paper)."""
    data = {
        "content_type": "mcq_pyq", "topic_id": "constitutional_framework", "context_prefix": "x",
        "pyqs": [
            {"question_format": "mcq", "question_text": "Q1?", "year": 2023,
             "options": ["a", "b"], "correct_option": "a"},
            {"question_format": "mcq", "question_text": "Q2?", "year": 2023,
             "options": ["c", "d"], "correct_option": "d"},
        ],
    }
    pyqs, failures = build_pyqs("chunk_1", "upsc_prelims_gs", "official_pyq", data, TOPICS)
    assert failures == []
    assert len(pyqs) == 2
    assert {p.question_id for p in pyqs} == {"chunk_1_pyq_0", "chunk_1_pyq_1"}
    assert pyqs[0].question_text == "Q1?"
    assert pyqs[1].correct_option == "d"


def test_one_bad_question_does_not_discard_its_good_siblings():
    """The core fix from the real 2025 ingestion run: a chunk with several valid questions
    and ONE unanswerable one (no official answer key exists for most dense MCQ content)
    must keep the good ones, not discard the whole chunk. Confirmed against real data: one
    real chunk had a failure at question index 6, meaning 6 good questions were being
    silently destroyed before this fix."""
    data = {
        "content_type": "mcq_pyq", "topic_id": "constitutional_framework", "context_prefix": "x",
        "pyqs": [
            {"question_format": "mcq", "question_text": "Good Q1?", "year": 2023,
             "options": ["a", "b"], "correct_option": "a"},
            {"question_format": "mcq", "question_text": "Unanswerable Q2?", "year": 2023,
             "options": ["a", "b"], "correct_option": None},
            {"question_format": "mcq", "question_text": "Good Q3?", "year": 2023,
             "options": ["c", "d"], "correct_option": "d"},
        ],
    }
    pyqs, failures = build_pyqs("chunk_1", "upsc_prelims_gs", "official_pyq", data, TOPICS)
    assert len(pyqs) == 2
    assert {p.question_text for p in pyqs} == {"Good Q1?", "Good Q3?"}
    assert len(failures) == 1
    assert "PYQ #1" in failures[0] and "no correct_option" in failures[0]


def test_per_question_topic_id_overrides_chunk_level():
    """A chunk spanning a subject boundary (no headers to key off — real for dense MCQ
    content) must let each question carry its own topic, not inherit the chunk's."""
    data = {
        "content_type": "mcq_pyq", "topic_id": "constitutional_framework", "context_prefix": "x",
        "pyqs": [
            {"topic_id": "parliament", "question_format": "mcq", "question_text": "Q1?",
             "year": 2023, "options": ["a", "b"], "correct_option": "a"},
            {"question_format": "mcq", "question_text": "Q2?", "year": 2023,  # no own topic_id -> falls back
             "options": ["c", "d"], "correct_option": "d"},
        ],
    }
    pyqs, failures = build_pyqs("chunk_1", "upsc_prelims_gs", "official_pyq", data, TOPICS)
    assert failures == []
    assert pyqs[0].topic_id == "parliament"
    assert pyqs[1].topic_id == "constitutional_framework"


def test_invalid_per_question_topic_id_flagged_not_crashed():
    """topic_id is a real database foreign key — an invented value must be caught here as a
    per-item failure, not allowed through to crash the INSERT later."""
    data = {
        "content_type": "mcq_pyq", "topic_id": "constitutional_framework", "context_prefix": "x",
        "pyqs": [{"topic_id": "made_up_topic_that_does_not_exist", "question_format": "mcq",
                  "question_text": "Q1?", "year": 2023, "options": ["a", "b"], "correct_option": "a"}],
    }
    pyqs, failures = build_pyqs("chunk_1", "upsc_prelims_gs", "official_pyq", data, TOPICS)
    assert pyqs == []
    assert len(failures) == 1
    assert "not a registered topic" in failures[0]


def test_mcq_pyq_missing_correct_option_flagged_not_raised():
    data = {
        "content_type": "mcq_pyq", "topic_id": "constitutional_framework", "context_prefix": "x",
        "pyqs": [{"question_format": "mcq", "question_text": "Article 21 protects?",
                  "year": 2023, "options": ["Life", "Property"], "correct_option": None}],
    }
    pyqs, failures = build_pyqs("chunk_1", "upsc_prelims_gs", "official_pyq", data, TOPICS)
    assert pyqs == []
    assert len(failures) == 1
    assert "no correct_option" in failures[0]


def test_pyq_missing_year_backfilled_from_published_date():
    """An official current-cycle paper never states its own year inline (only a prior-year
    reference would appear in question text) — published_date (from --published-date) must
    backfill it rather than forcing every question in the paper to get flagged."""
    data = {
        "content_type": "mcq_pyq", "topic_id": "constitutional_framework", "context_prefix": "x",
        "pyqs": [{"question_format": "mcq", "question_text": "x?", "year": None,
                  "options": ["a", "b"], "correct_option": "a"}],
    }
    pyqs, failures = build_pyqs("chunk_1", "upsc_prelims_gs", "official_pyq", data, TOPICS,
                                 published_date=date(2025, 11, 30))
    assert failures == []
    assert len(pyqs) == 1
    assert pyqs[0].year == 2025


def test_pyq_missing_year_flagged_not_raised():
    data = {
        "content_type": "mcq_pyq", "topic_id": "constitutional_framework", "context_prefix": "x",
        "pyqs": [{"question_format": "mcq", "question_text": "x?", "year": None,
                  "options": ["a", "b"], "correct_option": "a"}],
    }
    pyqs, failures = build_pyqs("chunk_1", "upsc_prelims_gs", "official_pyq", data, TOPICS)
    assert pyqs == []
    assert len(failures) == 1
    assert "no year" in failures[0]


def test_non_pyq_chunk_returns_empty_list():
    data = {"content_type": "study_material", "topic_id": "constitutional_framework",
            "context_prefix": "x", "pyqs": []}
    pyqs, failures = build_pyqs("chunk_1", "upsc_prelims_gs", "official_pyq", data, TOPICS)
    assert pyqs == [] and failures == []


def test_statement_based_mcq_captures_statements():
    data = {
        "content_type": "mcq_pyq", "topic_id": "parliament", "context_prefix": "x",
        "pyqs": [{
            "question_format": "mcq",
            "question_text": "Consider the following statements. How many of the above are correct?",
            "year": 2022,
            "options": ["Only one", "Only two", "All three", "None"],
            "correct_option": "Only two",
            "statements": [
                "The Speaker of the Lok Sabha is elected by its members.",
                "The Rajya Sabha cannot be dissolved.",
                "Money Bills can originate in either House.",
            ],
        }],
    }
    pyqs, failures = build_pyqs("upsc_cse_paper_1_1", "upsc_cse", "official_pyq", data, TOPICS)
    assert failures == []
    assert isinstance(pyqs[0], MCQQuestion)
    assert pyqs[0].statements is not None
    assert len(pyqs[0].statements) == 3
    assert pyqs[0].correct_option == "Only two"


def test_standalone_mcq_has_no_statements():
    data = {
        "content_type": "mcq_pyq", "topic_id": "constitutional_framework", "context_prefix": "x",
        "pyqs": [{"question_format": "mcq", "question_text": "Article 21 protects?",
                  "year": 2023, "options": ["Life", "Property", "Speech", "None"],
                  "correct_option": "Life"}],  # no "statements" key at all
    }
    pyqs, failures = build_pyqs("chunk_1", "upsc_prelims_gs", "official_pyq", data, TOPICS)
    assert isinstance(pyqs[0], MCQQuestion)
    assert pyqs[0].statements is None


def _fake_client(response_data: dict):
    """A minimal stand-in for anthropic.Anthropic() — no real API call. Mimics only the
    shape enrich_chunk actually reads off a response."""
    content_block = SimpleNamespace(text=json.dumps(response_data))
    usage = SimpleNamespace(input_tokens=10, output_tokens=20,
                             cache_creation_input_tokens=0, cache_read_input_tokens=0)
    response = SimpleNamespace(content=[content_block], usage=usage)
    return SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))


def test_enrich_chunk_keeps_valid_pyqs_when_chunk_level_topic_fails():
    """The real refinement from this session: a chunk whose OWN overall topic is
    unclassifiable must not also discard the individually-topic-tagged questions inside it —
    metadata is None (caller skips write_chunk) but pyqs still come through."""
    response_data = {
        "content_type": "mcq_pyq", "topic_id": None,  # chunk-level: unclassifiable
        "context_prefix": "x",
        "pyqs": [{"topic_id": "parliament", "question_format": "mcq", "question_text": "Q1?",
                  "year": 2023, "options": ["a", "b"], "correct_option": "a"}],
    }
    metadata, pyqs, pyq_failures, metadata_failure, usage = enrich_chunk(
        _fake_chunk(), "upsc_prelims_gs", "official_pyq",
        system_prompt="irrelevant for this fake client",
        client=_fake_client(response_data),
        topics=[("parliament", "Parliament"), ("constitutional_framework", "Constitutional Framework")],
    )
    assert metadata is None
    assert metadata_failure is not None and "no registered topic matched" in metadata_failure
    assert pyq_failures == []
    assert len(pyqs) == 1
    assert pyqs[0].topic_id == "parliament"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"PASS: {name}")
