"""Integration smoke tests for the FastAPI app (src/api/main.py) against the REAL local
data/core.db + data/lancedb — read-only endpoints only, no writes anywhere in this file.
DB_PATH/LANCEDB_PATH aren't dependency-injectable today (matches this repo's existing
scripts, which all hardcode paths too), so this mirrors that pattern rather than adding
new DI machinery for one test file.

/verify_citation (calls the paid Anthropic API) and /ingest's actual subprocess spawn are
deliberately NOT exercised end-to-end here — only their input-validation error paths are,
which cost nothing and touch no external system.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_list_exams_includes_known_real_exams():
    resp = client.get("/exams")
    assert resp.status_code == 200
    exam_ids = {e["exam_id"] for e in resp.json()}
    assert {"pfrda_gradea", "upsc_epfo_apfc_eo_ao"} <= exam_ids


def test_list_papers_for_pfrda():
    resp = client.get("/papers", params={"exam_id": "pfrda_gradea"})
    assert resp.status_code == 200
    paper_ids = {p["paper_id"] for p in resp.json()}
    assert "phase1_p1" in paper_ids


def test_list_topics_for_pfrda_has_weight_and_is_core_populated():
    resp = client.get("/topics", params={"exam_id": "pfrda_gradea"})
    assert resp.status_code == 200
    topics = resp.json()
    assert len(topics) > 0
    assert all(t["weight"] is not None for t in topics)
    assert all(t["is_core"] is not None for t in topics)


def test_query_pyq_returns_real_verified_mcqs_with_dict_shaped_options():
    resp = client.get(
        "/pyq",
        params={"exam_id": "pfrda_gradea", "question_format": "mcq", "status": "verified", "limit": 5},
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) > 0
    for row in rows:
        assert row["status"] == "verified"
        assert row["correct_option"] is not None
        assert isinstance(row["options"], dict)  # not a list — matches real storage, see schemas.py docstring


def test_query_pyq_normalizes_list_shaped_options_for_epfo():
    """Real, pre-existing storage-shape difference found live this session:
    upsc_epfo_apfc_eo_ao (and rbi_depr) store `options` as a plain JSON list, not the
    letter-keyed dict pfrda_gradea uses. The API must always hand back a consistent
    dict shape — see routes.py's `_row_to_pyq_out` and scripts/quiz.py's
    `normalize_options`, the shared fix."""
    resp = client.get(
        "/pyq",
        params={"exam_id": "upsc_epfo_apfc_eo_ao", "question_format": "mcq", "limit": 20},
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) > 0
    for row in rows:
        assert isinstance(row["options"], dict)
        assert set(row["options"]) <= set("ABCDEFGHIJ")


def test_query_pyq_unknown_exam_returns_empty_not_error():
    resp = client.get("/pyq", params={"exam_id": "no_such_exam"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_search_signals_insufficient_grounding_for_pfrda():
    resp = client.get(
        "/search", params={"q": "cost accounting standards", "exam_id": "pfrda_gradea", "k": 5}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["insufficient_grounding"] is True
    assert body["hits"] == []


def test_topic_brief_404_for_unknown_topic():
    resp = client.get("/topic/no_such_topic/brief", params={"exam_id": "pfrda_gradea"})
    assert resp.status_code == 404


def test_ingest_rejects_missing_folder():
    resp = client.post(
        "/ingest",
        json={"folder": "/no/such/folder/anywhere", "exam_id": "pfrda_gradea", "source_type": "official_pyq"},
    )
    assert resp.status_code == 400
    assert "folder not found" in resp.json()["detail"]


def test_ingest_rejects_unregistered_exam():
    resp = client.post(
        "/ingest",
        json={"folder": ".", "exam_id": "not_a_real_exam_id", "source_type": "official_pyq"},
    )
    assert resp.status_code == 400
    assert "not registered" in resp.json()["detail"]


def test_attempt_rejects_unknown_question():
    resp = client.post("/attempt", json={"question_id": "no_such_question", "chosen_option": "A"})
    assert resp.status_code == 404
