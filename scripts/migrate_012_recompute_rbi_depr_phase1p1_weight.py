"""Migration (this session's RBI DEPR Set-1 ingestion, see docs/decisions.md): recomputes
`exam_topics.weight` for `rbi_depr`'s `phase1_p1` paper from the first-ever real ingested
content for this exam (65 real MCQs, Next IAS's digital-text reproduction of the real 2025
RBI DEPR Prelims Set-1 paper, merged against its own real answer key — zero LLM-guessed
`correct_option`, see `scripts/merge_answer_key.py`). Replaces DECIDE-32/migrate_009's flat
1.0 placeholder for all 8 `phase1_p1` topics with a real recency-decayed frequency count —
same `layered-coverage` skill Q2 formula already used by `scripts/ingest_pfrda_structured.py`
(DECIDE-31): weight = sum of 0.9^(CURRENT_YEAR - year) over each real observed occurrence.

All 8 `phase1_p1` topics (macro/micro/intl_econ/growth/pub_finance/env_econ/indian_econ/
depr_quant_methods_econ) are top-level (no parent_topic_id) within this exam's taxonomy —
unlike DECIDE-31's PFRDA subtopic rollup, no parent-child aggregation is needed here; each
question's own `topic_id` already IS a registered `exam_topics` row for this paper.

Only `rbi_depr`/`phase1_p1` weights are touched. Every other paper/exam's weights
(phase1_p2/phase2_p1/phase2_p2's still-placeholder rows, every other exam) are left
untouched — this is real signal for exactly the paper that received real content, not a
broader retroactive change.

Run: .venv/bin/python scripts/migrate_012_recompute_rbi_depr_phase1p1_weight.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "core.db"
EXAM_ID = "rbi_depr"
PAPER_ID = "phase1_p1"
CURRENT_YEAR = 2026


def recompute_weights(conn: sqlite3.Connection) -> dict[str, float]:
    """Returns the new {topic_id: weight} map actually written. Pure real-frequency
    recompute — every row read here already has a real merged `correct_option`
    (`status='verified'`) or an honest `unverified`/`void` (neither exists in this batch),
    never an LLM-guessed one; this recompute only counts real observed topic occurrences,
    it never touches `correct_option` itself.
    """
    rows = conn.execute(
        "SELECT topic_id, year FROM pyq_bank "
        "WHERE exam_id = ? AND paper_id = ? AND question_format = 'mcq'",
        (EXAM_ID, PAPER_ID),
    ).fetchall()

    weight: dict[str, float] = {}
    for topic_id, year in rows:
        decay = 0.9 ** (CURRENT_YEAR - year)
        weight[topic_id] = weight.get(topic_id, 0.0) + decay

    for topic_id, w in weight.items():
        conn.execute(
            "UPDATE exam_topics SET weight = ? WHERE exam_id = ? AND paper_id = ? AND topic_id = ?",
            (w, EXAM_ID, PAPER_ID, topic_id),
        )
    conn.commit()
    return weight


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    before = dict(conn.execute(
        "SELECT topic_id, weight FROM exam_topics WHERE exam_id = ? AND paper_id = ?",
        (EXAM_ID, PAPER_ID),
    ).fetchall())

    weight = recompute_weights(conn)

    after = dict(conn.execute(
        "SELECT topic_id, weight FROM exam_topics WHERE exam_id = ? AND paper_id = ?",
        (EXAM_ID, PAPER_ID),
    ).fetchall())
    conn.close()

    print(f"{EXAM_ID}/{PAPER_ID} weight recompute ({len(weight)} topics touched, real "
          f"observed frequency from {sum(1 for _ in weight)} distinct topics):")
    for topic_id in sorted(after):
        b = before.get(topic_id)
        print(f"  {topic_id}: {b} -> {after[topic_id]:.4f}")


if __name__ == "__main__":
    main()
