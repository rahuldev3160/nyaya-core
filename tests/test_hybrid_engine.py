"""Unit tests for src/retrieval/hybrid_engine.py.

Pure-logic pieces (RRF fusion, auto-merge, id validation) are tested against synthetic
data — no real DB/LanceDB needed. One integration test runs against the REAL local
data/core.db + data/lancedb (read-only — no writes anywhere in this file) to lock in the
exact regression case found this session: an exam with zero indexed chunks must return
`insufficient_grounding=True`, never crash or silently return an empty-but-"ok" result.
"""
from __future__ import annotations

import sqlite3

import pytest

from src.retrieval.hybrid_engine import (
    _build_filter,
    _validate_id,
    auto_merge,
    reciprocal_rank_fusion,
    search,
)


def test_validate_id_accepts_safe_values():
    _validate_id("pfrda_gradea", "exam_id")
    _validate_id(None, "exam_id")  # optional fields may be None


def test_validate_id_rejects_injection_attempt():
    with pytest.raises(ValueError):
        _validate_id("pfrda'; DROP TABLE chunks; --", "exam_id")


def test_build_filter_excludes_ai_generated_and_superseded_by_default():
    filter_sql = _build_filter("pfrda_gradea", None, None, ("ai_generated",))
    assert "exam_id = 'pfrda_gradea'" in filter_sql
    assert "is_current = true" in filter_sql
    assert "source_type != 'ai_generated'" in filter_sql


def test_build_filter_scopes_by_paper_and_topic_when_given():
    filter_sql = _build_filter("pfrda_gradea", "phase1_p1", "pfrda_costing", ())
    assert "paper_id = 'phase1_p1'" in filter_sql
    assert "topic_id = 'pfrda_costing'" in filter_sql


def test_reciprocal_rank_fusion_rewards_agreement_across_lists():
    dense = [{"chunk_id": "a"}, {"chunk_id": "b"}, {"chunk_id": "c"}]
    fts = [{"chunk_id": "b"}, {"chunk_id": "a"}, {"chunk_id": "d"}]
    scores = reciprocal_rank_fusion(dense, fts, k=60)
    # "a" and "b" appear in both lists near the top; "c"/"d" appear in only one list each.
    assert scores["a"] > scores["c"]
    assert scores["b"] > scores["d"]
    assert set(scores) == {"a", "b", "c", "d"}


def test_reciprocal_rank_fusion_empty_lists_is_empty():
    assert reciprocal_rank_fusion([], []) == {}


def _sections_conn(rows: dict[str, str]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE sections (section_id TEXT PRIMARY KEY, full_text TEXT NOT NULL)")
    for sid, text in rows.items():
        conn.execute("INSERT INTO sections (section_id, full_text) VALUES (?, ?)", (sid, text))
    conn.commit()
    return conn


def test_auto_merge_substitutes_full_text_when_two_hits_share_a_section():
    conn = _sections_conn({"sec1": "the full merged section text, longer than either chunk"})
    hits = [
        {"chunk_id": "c1", "section_id": "sec1", "content": "chunk 1 text"},
        {"chunk_id": "c2", "section_id": "sec1", "content": "chunk 2 text"},
        {"chunk_id": "c3", "section_id": "sec2", "content": "unrelated chunk"},
    ]
    merged = auto_merge(hits, conn, token_budget=10_000)
    merged_texts = [h["content"] for h in merged]
    assert merged_texts.count("the full merged section text, longer than either chunk") == 1
    assert "unrelated chunk" in merged_texts
    assert len(merged) == 2  # c1+c2 collapsed into one merged hit, c3 untouched


def test_auto_merge_leaves_hits_alone_when_no_section_is_shared():
    conn = _sections_conn({})
    hits = [
        {"chunk_id": "c1", "section_id": "sec1", "content": "a"},
        {"chunk_id": "c2", "section_id": "sec2", "content": "b"},
    ]
    assert auto_merge(hits, conn, token_budget=10_000) == hits


def test_auto_merge_falls_back_to_individual_chunks_when_over_budget():
    huge_text = "x" * 100_000  # ~25k tokens at the 4-chars/token estimate
    conn = _sections_conn({"sec1": huge_text})
    hits = [
        {"chunk_id": "c1", "section_id": "sec1", "content": "chunk 1"},
        {"chunk_id": "c2", "section_id": "sec1", "content": "chunk 2"},
    ]
    merged = auto_merge(hits, conn, token_budget=100)
    # Budget too small for the merged text — original two chunks preserved, not dropped.
    assert len(merged) == 2
    assert merged[0]["content"] == "chunk 1"
    assert merged[1]["content"] == "chunk 2"


# --- Integration test against real local data (read-only) ---------------------------


def test_search_returns_insufficient_grounding_for_an_exam_with_zero_chunks():
    """Regression test for the exact gap found this session: pfrda_gradea has 470 real
    PYQs but zero indexed chunks in LanceDB. /search must signal this explicitly, never
    crash and never silently return an empty-but-"ok" result."""
    result = search("cost accounting standards", "pfrda_gradea", k=5)
    assert result.insufficient_grounding is True
    assert result.hits == []


def test_search_does_not_crash_for_an_exam_with_some_chunks():
    """upsc_epfo_apfc_eo_ao has 125 real chunks — a real query should not error, whichever
    way it resolves (result depends on live data, not asserted here)."""
    result = search("employees provident fund contribution rate", "upsc_epfo_apfc_eo_ao", k=5)
    assert isinstance(result.insufficient_grounding, bool)
    assert isinstance(result.hits, list)
