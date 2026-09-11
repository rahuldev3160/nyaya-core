"""Sanity tests for src/ingestion/enrich.py — no real API calls (uses a fake client that
returns canned responses), proves the parsing/validation logic, not the prompt itself."""

import sqlite3
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

import json

from src.ingestion.enrich import ReviewNeededError, build_chunk_metadata, build_pyqs, enrich_chunk, parse_enrichment, persist_pyq
from src.schema.models import MCQQuestion, TextChunk

TOPICS = {"constitutional_framework", "parliament"}

PYQ_BANK_SCHEMA = """
CREATE TABLE pyq_bank (
    question_id TEXT PRIMARY KEY, exam_id TEXT NOT NULL, paper_id TEXT, topic_id TEXT,
    question_format TEXT NOT NULL, year INTEGER, question_number INTEGER,
    question_text TEXT NOT NULL, options TEXT, correct_option TEXT,
    status TEXT NOT NULL DEFAULT 'unverified', statements TEXT, marks INTEGER,
    word_limit INTEGER, source_type TEXT NOT NULL, source_file TEXT, verified_by TEXT,
    answer_key_file TEXT, reviewed_at TEXT
)
"""


def _pyq_bank_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(PYQ_BANK_SCHEMA)
    return conn


def _mcq(question_id: str, question_number: int, paper_id: str = "gat") -> MCQQuestion:
    return MCQQuestion(
        question_id=question_id, exam_id="upsc_epfo_apfc_eo_ao", paper_id=paper_id,
        topic_id="constitutional_framework", year=2023, question_number=question_number,
        question_text="x?", options=["a", "b"], source_type="official_pyq",
    )


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
    assert pyqs[0].correct_option is None  # never Haiku-guessed (DECIDE-26/27)
    assert pyqs[0].status == "unverified"
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
    assert pyqs[1].correct_option is None  # never Haiku-guessed (DECIDE-26/27)


def test_one_bad_question_does_not_discard_its_good_siblings():
    """A chunk with several valid questions and ONE genuinely bad one (no year statable or
    inferable) must keep the good ones, not discard the whole chunk. Confirmed against real
    data: one real chunk had a failure at question index 6, meaning 6 good questions were
    being silently destroyed before this fix. NOTE: a missing correct_option is no longer a
    failure at all (DECIDE-26/27) — see test_mcq_pyq_missing_correct_option_kept_unverified."""
    data = {
        "content_type": "mcq_pyq", "topic_id": "constitutional_framework", "context_prefix": "x",
        "pyqs": [
            {"question_format": "mcq", "question_text": "Good Q1?", "year": 2023,
             "options": ["a", "b"]},
            {"question_format": "mcq", "question_text": "No year Q2?", "year": None,
             "options": ["a", "b"]},
            {"question_format": "mcq", "question_text": "Good Q3?", "year": 2023,
             "options": ["c", "d"]},
        ],
    }
    pyqs, failures = build_pyqs("chunk_1", "upsc_prelims_gs", "official_pyq", data, TOPICS)
    assert len(pyqs) == 2
    assert {p.question_text for p in pyqs} == {"Good Q1?", "Good Q3?"}
    assert len(failures) == 1
    assert "PYQ #1" in failures[0] and "no year" in failures[0]


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


def test_mcq_pyq_with_null_option_entry_flagged_not_crashed():
    """Real bug found ingesting the 2023 EPFO GAT paper: Haiku returned an `options` array
    with a null entry (a genuinely illegible/malformed cell) instead of 4 strings, which
    crashed MCQQuestion's Pydantic validation and took down the whole ingestion run. A
    per-item extraction defect must be a flagged failure, not an uncaught exception."""
    data = {
        "content_type": "mcq_pyq", "topic_id": "constitutional_framework", "context_prefix": "x",
        "pyqs": [{"question_format": "mcq", "question_text": "Q?", "year": 2023,
                  "options": ["a", "b", None, "d"]}],
    }
    pyqs, failures = build_pyqs("chunk_1", "upsc_prelims_gs", "official_pyq", data, TOPICS)
    assert pyqs == []
    assert len(failures) == 1
    assert "malformed" in failures[0]


def test_mcq_pyq_missing_correct_option_kept_unverified():
    """DECIDE-26/27: a missing answer is no longer a reason to drop an extraction — most
    real official papers have no printed key at all, and losing the question along with the
    unknown answer was the exact bug (36/120 real yield) that led to this policy change."""
    data = {
        "content_type": "mcq_pyq", "topic_id": "constitutional_framework", "context_prefix": "x",
        "pyqs": [{"question_format": "mcq", "question_text": "Article 21 protects?",
                  "year": 2023, "options": ["Life", "Property"]}],
    }
    pyqs, failures = build_pyqs("chunk_1", "upsc_prelims_gs", "official_pyq", data, TOPICS)
    assert failures == []
    assert len(pyqs) == 1
    assert pyqs[0].correct_option is None
    assert pyqs[0].status == "unverified"


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
    assert pyqs[0].correct_option is None  # never Haiku-guessed (DECIDE-26/27)


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


def _fake_client_raw_text(text: str):
    content_block = SimpleNamespace(text=text)
    usage = SimpleNamespace(input_tokens=10, output_tokens=20,
                             cache_creation_input_tokens=0, cache_read_input_tokens=0)
    response = SimpleNamespace(content=[content_block], usage=usage)
    return SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))


def test_enrich_chunk_flags_truncated_json_instead_of_crashing():
    """Real failure on the 2017 EPFO paper: a chunk packed with dense MCQs produced a
    response cut off mid-string by max_tokens, and json.loads crashed the entire ingestion
    run instead of flagging just that one chunk."""
    truncated = '{"content_type": "mcq_pyq", "topic_id": "parliament", "pyqs": [{"question_text": "unterminat'
    metadata, pyqs, pyq_failures, metadata_failure, usage = enrich_chunk(
        _fake_chunk(), "upsc_prelims_gs", "official_pyq",
        system_prompt="irrelevant for this fake client",
        client=_fake_client_raw_text(truncated),
        topics=[("parliament", "Parliament")],
    )
    assert metadata is None
    assert pyqs == []
    assert pyq_failures == []
    assert metadata_failure is not None and "not valid JSON" in metadata_failure
    assert usage["input_tokens"] == 10  # still billed, still counted


def test_persist_pyq_writes_new_row():
    conn = _pyq_bank_conn()
    inserted = persist_pyq(_mcq("chunk_1_pyq_0", question_number=5), conn)
    assert inserted is True
    row = conn.execute("SELECT question_number, source_file FROM pyq_bank").fetchone()
    assert row[0] == 5


def test_persist_pyq_dedupes_same_question_number_different_chunk():
    """BUG-13: the same real question can be extracted from two adjacent chunks with two
    different chunk-derived question_ids. persist_pyq must recognize the second as the same
    real question (same exam/paper/year/question_number) and skip it, not double-insert."""
    conn = _pyq_bank_conn()
    assert persist_pyq(_mcq("chunk_1_pyq_0", question_number=5), conn) is True
    assert persist_pyq(_mcq("chunk_2_pyq_0", question_number=5), conn) is False
    assert conn.execute("SELECT COUNT(*) FROM pyq_bank").fetchone()[0] == 1


def test_persist_pyq_does_not_dedupe_across_different_papers():
    """Same question_number under a DIFFERENT paper_id is a genuinely different question
    (e.g. Q5 of the GAT paper vs Q5 of the GS paper) — must not be treated as a duplicate."""
    conn = _pyq_bank_conn()
    assert persist_pyq(_mcq("chunk_1_pyq_0", question_number=5, paper_id="gat"), conn) is True
    assert persist_pyq(_mcq("chunk_2_pyq_0", question_number=5, paper_id="gs"), conn) is True
    assert conn.execute("SELECT COUNT(*) FROM pyq_bank").fetchone()[0] == 2


def test_build_pyqs_threads_source_file_through():
    data = {
        "content_type": "mcq_pyq", "topic_id": "constitutional_framework", "context_prefix": "x",
        "pyqs": [{"question_format": "mcq", "question_text": "Q?", "year": 2023,
                  "options": ["a", "b"], "question_number": 5}],
    }
    pyqs, failures = build_pyqs("chunk_1", "upsc_prelims_gs", "official_pyq", data, TOPICS,
                                 source_file="data/raw_ingest_staging/foo/bar.pdf")
    assert failures == []
    assert pyqs[0].source_file == "data/raw_ingest_staging/foo/bar.pdf"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"PASS: {name}")
