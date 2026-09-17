"""POST /attempt — new, beyond PLAN.md's original Phase 2 spec (flagged in the plan this
was built from). Lets any consumer (scripts/quiz.py's CLI, or a future Devthorium web
client) log to the same real `user_attempts`/`topic_coverage` tables instead of forking a
second, disconnected attempt history for the same real questions.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

from src.api.schemas import AttemptRequest, AttemptResponse

REPO_ROOT = Path(__file__).parent.parent.parent
DB_PATH = REPO_ROOT / "data" / "core.db"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from quiz import log_attempt, recompute_topic_coverage  # noqa: E402 — reuse the real, tested logic

router = APIRouter()


@router.post("/attempt", response_model=AttemptResponse)
def record_attempt(req: AttemptRequest):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        row = conn.execute(
            "SELECT exam_id, topic_id, correct_option FROM pyq_bank WHERE question_id = ?",
            (req.question_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"question_id '{req.question_id}' not found")
        exam_id, topic_id, correct_option = row
        if not correct_option:
            raise HTTPException(
                status_code=400, detail="question has no recorded correct_option — not quizzable"
            )
        if not topic_id:
            raise HTTPException(status_code=400, detail="question has no topic_id — can't compute coverage")

        is_correct = req.chosen_option.strip().upper() == correct_option.strip().upper()
        log_attempt(conn, req.question_id, req.chosen_option, correct_option, is_correct)
        coverage = recompute_topic_coverage(conn, exam_id, topic_id)

        return AttemptResponse(
            question_id=req.question_id,
            chosen_option=req.chosen_option,
            correct_option=correct_option,
            is_correct=is_correct,
            topic_coverage=coverage,
        )
    finally:
        conn.close()
