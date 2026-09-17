"""FastAPI routes for nyaya-core's Phase 2 API surface. Read-only browse/search/pyq
endpoints, one composite endpoint, one opt-in verification endpoint, one admin ingest
trigger. /attempt (a write) lives in routes_attempts.py, kept separate from these reads.
"""
from __future__ import annotations

import json
import os
import subprocess
import sqlite3
import sys
from pathlib import Path
from typing import Optional

import anthropic
from fastapi import APIRouter, HTTPException, Query

from src.api.schemas import (
    ExamOut,
    IngestRequest,
    IngestResponse,
    PaperOut,
    PYQOut,
    TopicBriefOut,
    TopicOut,
    VerifyCitationRequest,
    VerifyCitationResponse,
)
from src.ingestion.embed import get_chunks_table
from src.retrieval.hybrid_engine import search as hybrid_search

REPO_ROOT = Path(__file__).parent.parent.parent
DB_PATH = REPO_ROOT / "data" / "core.db"
VERIFY_MODEL = os.getenv("AI_MODEL_FAST", "claude-haiku-4-5-20251001")

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from quiz import normalize_options  # noqa: E402 — one shared fix for pyq_bank's dict-vs-list options

router = APIRouter()


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/exams", response_model=list[ExamOut])
def list_exams():
    conn = get_conn()
    try:
        rows = conn.execute("SELECT exam_id, name, institution_id FROM exams ORDER BY exam_id").fetchall()
        return [ExamOut(**dict(r)) for r in rows]
    finally:
        conn.close()


@router.get("/papers", response_model=list[PaperOut])
def list_papers(exam_id: str = Query(...)):
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT exam_id, paper_id, name FROM papers WHERE exam_id = ? ORDER BY paper_id",
            (exam_id,),
        ).fetchall()
        return [PaperOut(**dict(r)) for r in rows]
    finally:
        conn.close()


@router.get("/topics", response_model=list[TopicOut])
def list_topics(exam_id: str = Query(...), paper_id: Optional[str] = Query(None)):
    """DECIDE-04/19: `topics` is exam-agnostic; scoping to one exam/paper happens via
    `exam_topics`. weight/is_core are only meaningful in that scoped context (a topic can
    be core in one exam and optional in another) — always populated here, never a bare
    registry dump."""
    conn = get_conn()
    try:
        query = (
            "SELECT t.topic_id, t.name, t.parent_topic_id, t.notes, et.weight, et.is_core "
            "FROM exam_topics et JOIN topics t ON t.topic_id = et.topic_id "
            "WHERE et.exam_id = ?"
        )
        params: list = [exam_id]
        if paper_id:
            query += " AND et.paper_id = ?"
            params.append(paper_id)
        rows = conn.execute(query, params).fetchall()
        return [
            TopicOut(
                topic_id=r["topic_id"],
                name=r["name"],
                parent_topic_id=r["parent_topic_id"],
                notes=r["notes"],
                weight=r["weight"],
                is_core=bool(r["is_core"]),
            )
            for r in rows
        ]
    finally:
        conn.close()


@router.get("/search")
def search_endpoint(
    q: str = Query(..., description="query text"),
    exam_id: str = Query(...),
    paper_id: Optional[str] = Query(None),
    topic_id: Optional[str] = Query(None),
    k: int = Query(8, ge=1, le=50),
    token_budget: int = Query(4000, ge=100),
):
    try:
        return hybrid_search(
            q, exam_id, paper_id=paper_id, topic_id=topic_id, k=k, token_budget=token_budget
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _row_to_pyq_out(r: sqlite3.Row) -> PYQOut:
    # pyq_bank.options is real JSON but not uniformly a dict — pfrda_gradea stores
    # `{"A": "...", ...}`, rbi_depr/upsc_epfo_apfc_eo_ao store a plain list instead (a
    # real, pre-existing per-exam difference found live testing this endpoint).
    # normalize_options (scripts/quiz.py) is the one shared fix for both consumers.
    options = normalize_options(r["options"]) or None
    statements = json.loads(r["statements"]) if r["statements"] else None
    return PYQOut(
        question_id=r["question_id"],
        exam_id=r["exam_id"],
        paper_id=r["paper_id"],
        topic_id=r["topic_id"],
        question_format=r["question_format"],
        year=r["year"],
        question_number=r["question_number"],
        question_text=r["question_text"],
        options=options,
        statements=statements,
        correct_option=r["correct_option"],
        marks=r["marks"],
        word_limit=r["word_limit"],
        source_type=r["source_type"],
        status=r["status"],
        source_file=r["source_file"],
        answer_key_file=r["answer_key_file"],
    )


@router.get("/pyq", response_model=list[PYQOut])
def query_pyq(
    exam_id: str = Query(...),
    paper_id: Optional[str] = Query(None),
    topic_id: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    question_format: Optional[str] = Query(None, description="mcq | descriptive"),
    status: Optional[str] = Query(None, description="unverified | verified | void"),
    limit: int = Query(200, ge=1, le=2000),
):
    conn = get_conn()
    try:
        query = "SELECT * FROM pyq_bank WHERE exam_id = ?"
        params: list = [exam_id]
        for col, val in (
            ("paper_id", paper_id),
            ("topic_id", topic_id),
            ("year", year),
            ("question_format", question_format),
            ("status", status),
        ):
            if val is not None:
                query += f" AND {col} = ?"
                params.append(val)
        query += " LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [_row_to_pyq_out(r) for r in rows]
    finally:
        conn.close()


@router.get("/topic/{topic_id}/brief", response_model=TopicBriefOut)
def topic_brief(
    topic_id: str,
    exam_id: str = Query(...),
    paper_id: Optional[str] = Query(None),
    chunk_k: int = Query(5, ge=1, le=20),
    pyq_limit: int = Query(10, ge=1, le=100),
):
    """Composite: the 'explain X + give real PYQs on it' use case in one call."""
    conn = get_conn()
    try:
        topic_row = conn.execute("SELECT name FROM topics WHERE topic_id = ?", (topic_id,)).fetchone()
        if topic_row is None:
            raise HTTPException(status_code=404, detail=f"topic_id '{topic_id}' not found")
        topic_name = topic_row["name"]

        search_result = hybrid_search(
            topic_name, exam_id, paper_id=paper_id, topic_id=topic_id, k=chunk_k, conn=conn
        )

        mcq_rows = conn.execute(
            "SELECT * FROM pyq_bank WHERE exam_id = ? AND topic_id = ? AND question_format = 'mcq' "
            "AND status != 'void' LIMIT ?",
            (exam_id, topic_id, pyq_limit),
        ).fetchall()
        mains_rows = conn.execute(
            "SELECT * FROM pyq_bank WHERE exam_id = ? AND topic_id = ? "
            "AND question_format = 'descriptive' LIMIT ?",
            (exam_id, topic_id, pyq_limit),
        ).fetchall()

        return TopicBriefOut(
            topic_id=topic_id,
            exam_id=exam_id,
            explanation_chunks=[h.model_dump() for h in search_result.hits],
            insufficient_grounding=search_result.insufficient_grounding,
            mcq_pyqs=[_row_to_pyq_out(r) for r in mcq_rows],
            mains_pyqs=[_row_to_pyq_out(r) for r in mains_rows],
        )
    finally:
        conn.close()


@router.post("/verify_citation", response_model=VerifyCitationResponse)
def verify_citation(req: VerifyCitationRequest):
    """DECIDE-15: opt-in per call, never automatic. High-stakes/low-volume consumers
    (Scribe's Mains generation) call this deliberately; cheap/frequent callers (Recall's
    MCQ drills) don't."""
    table = get_chunks_table()
    rows = table.search().where(f"chunk_id = '{req.chunk_id}'", prefilter=True).limit(1).to_list()
    if not rows:
        raise HTTPException(status_code=404, detail=f"chunk_id '{req.chunk_id}' not found")
    chunk_text = rows[0]["content"]  # real source text, not the context_prefix blurb (DECIDE-13)

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=VERIFY_MODEL,
        max_tokens=300,
        messages=[
            {
                "role": "user",
                "content": (
                    "Does the SOURCE TEXT support the CLAIM? Answer strictly as JSON: "
                    '{"entailed": true|false, "reasoning": "one sentence"}.\n\n'
                    f"SOURCE TEXT:\n{chunk_text}\n\nCLAIM:\n{req.claim}"
                ),
            }
        ],
    )
    raw = response.content[0].text
    start, end = raw.find("{"), raw.rfind("}")
    parsed = json.loads(raw[start : end + 1])
    return VerifyCitationResponse(
        claim=req.claim,
        chunk_id=req.chunk_id,
        entailed=bool(parsed["entailed"]),
        reasoning=parsed["reasoning"],
    )


@router.post("/ingest", response_model=IngestResponse)
def trigger_ingest(req: IngestRequest):
    """Admin-only, local. A real ingestion run calls the paid Haiku API once per chunk of
    every file in the folder — FOUNDATION.md's "large paid ingestion batches" approval-gate
    territory — so this kicks off the existing, tested scripts/ingest.py as a background
    subprocess rather than blocking the request or re-implementing its logic inline. Poll
    data/ingestion_log.json (grows after every file) and data/flagged_chunks.jsonl for
    progress and items needing manual review."""
    folder = Path(req.folder)
    if not folder.is_dir():
        raise HTTPException(status_code=400, detail=f"folder not found: {req.folder}")

    conn = get_conn()
    try:
        exists = conn.execute("SELECT 1 FROM exams WHERE exam_id = ?", (req.exam_id,)).fetchone()
    finally:
        conn.close()
    if not exists:
        raise HTTPException(status_code=400, detail=f"exam_id '{req.exam_id}' not registered in exams table")

    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "ingest.py"),
        "--folder", str(folder),
        "--exam-id", req.exam_id,
        "--source-type", req.source_type,
    ]
    if req.paper_id:
        cmd += ["--paper-id", req.paper_id]
    if req.force:
        cmd += ["--force"]

    proc = subprocess.Popen(cmd, cwd=str(REPO_ROOT))
    return IngestResponse(
        status="started",
        pid=proc.pid,
        log_file=str(REPO_ROOT / "data" / "ingestion_log.json"),
        note=(
            "Runs in the background and calls the paid Haiku API per chunk. Check "
            "data/ingestion_log.json (grows per file) and data/flagged_chunks.jsonl for "
            "progress and items needing review."
        ),
    )
