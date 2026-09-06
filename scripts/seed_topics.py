"""Seed the canonical `topics` table (+ `exam_topics` relevance) for one exam from a
syllabus JSON (DECIDE-18, DECIDE-19, DECIDE-20).

Phase 0 seeded `exams`/`content_types` but left `topics` empty — the enrichment step
(Phase 1) needs a closed, real set of topic_ids to classify chunks against (DECIDE-04:
topic_id is a registry FK, never free text Haiku invents per chunk). Devthorium's
`data/syllabus.json` is the only real taxonomy that exists today, covering
`upsc_prelims_gs` — a 4-level hierarchy (subject > topic > subtopic > dimension). Only the
top 3 levels are imported as `topics` rows; `dimension` is PYQ-weighting granularity
(Devthorium's own `priority_scorer.py` concern), finer than what a retrieval topic_id needs
to be useful.

`topics` itself is exam-agnostic (DECIDE-19) — running this again for a second exam whose
syllabus JSON reuses a topic_id already seeded (e.g. IES's taxonomy also has a
"monetary_policy" topic RBI already seeded) links that exam to the EXISTING topic via
`exam_topics`, rather than creating a duplicate. `topic_id` collision across two genuinely
different concepts that happen to share an id would be a real bug — pick topic_ids
carefully when writing a new syllabus JSON for an exam with no prior taxonomy.

Two input shapes (DECIDE-20 — State PCS exams are mostly UPSC GS content plus one
genuinely state-specific branch, so a file describes both in one place):
- `subjects`: Devthorium's shape (subject > topic > subtopic) — creates new topic rows,
  links them all to `--exam-id`. Use for content with no prior taxonomy anywhere.
- `reused_topics`: a flat list of EXISTING topic_ids (e.g. `["polity", "geography", ...]`
  already seeded for another exam) — creates no new topic rows, only new `exam_topics`
  links. Use for content that genuinely overlaps an already-seeded exam's syllabus.
A file may have either key, or both.

Re-runnable: INSERT OR IGNORE, same idempotent pattern as init_db.py.
"""

import argparse
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "core.db"


def seed_subjects(data: dict, exam_id: str, paper_id: str, conn: sqlite3.Connection) -> int:
    topic_rows: list[tuple[str, str, str | None]] = []
    exam_topic_rows: list[tuple[str, str, str, float]] = []

    for subject in data.get("subjects", []):
        weight = float(subject.get("avg_questions_per_year") or 1.0)
        topic_rows.append((subject["id"], subject["name"], None))
        exam_topic_rows.append((exam_id, paper_id, subject["id"], weight))
        for topic in subject.get("topics", []):
            topic_rows.append((topic["id"], topic["name"], subject["id"]))
            exam_topic_rows.append((exam_id, paper_id, topic["id"], 1.0))  # no per-topic frequency in this source
            for subtopic in topic.get("subtopics", []):
                topic_rows.append((subtopic["id"], subtopic["name"], topic["id"]))
                exam_topic_rows.append((exam_id, paper_id, subtopic["id"], 1.0))

    conn.executemany(
        "INSERT OR IGNORE INTO topics (topic_id, name, parent_topic_id) VALUES (?, ?, ?)",
        topic_rows,
    )
    conn.executemany(
        "INSERT OR IGNORE INTO exam_topics (exam_id, paper_id, topic_id, weight) VALUES (?, ?, ?, ?)",
        exam_topic_rows,
    )
    return len(topic_rows)


def seed_reused_topics(data: dict, exam_id: str, paper_id: str, conn: sqlite3.Connection) -> int:
    reused = data.get("reused_topics", [])
    if not reused:
        return 0
    missing = [
        tid for tid in reused
        if not conn.execute("SELECT 1 FROM topics WHERE topic_id = ?", (tid,)).fetchone()
    ]
    if missing:
        raise ValueError(
            f"reused_topics references topic_id(s) not yet in `topics`: {missing} — "
            f"seed the exam that owns them first, or fix a typo."
        )
    conn.executemany(
        "INSERT OR IGNORE INTO exam_topics (exam_id, paper_id, topic_id, weight) VALUES (?, ?, ?, 1.0)",
        [(exam_id, paper_id, tid) for tid in reused],
    )
    return len(reused)


def seed_from_json(
    syllabus_path: Path, exam_id: str, conn: sqlite3.Connection, paper_id: str = "_all"
) -> tuple[int, int]:
    data = json.loads(syllabus_path.read_text())
    n_new = seed_subjects(data, exam_id, paper_id, conn)
    n_reused = seed_reused_topics(data, exam_id, paper_id, conn)
    conn.commit()
    return n_new, n_reused


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--syllabus", type=Path, required=True, help="Path to a syllabus JSON")
    parser.add_argument("--exam-id", required=True, help="exams.exam_id this taxonomy belongs to")
    parser.add_argument("--paper-id", default="_all",
                         help="papers.paper_id to scope this taxonomy to (DECIDE-21) — omit for "
                              "topics relevant across the whole exam, not one specific paper.")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    n_new, n_reused = seed_from_json(args.syllabus, args.exam_id, conn, paper_id=args.paper_id)
    total = conn.execute(
        "SELECT COUNT(*) FROM exam_topics WHERE exam_id = ? AND paper_id = ?",
        (args.exam_id, args.paper_id),
    ).fetchone()[0]
    conn.close()
    print(f"{args.syllabus.name} -> '{args.exam_id}'/'{args.paper_id}': {n_new} new topic rows, "
          f"{n_reused} links to existing topics, {total} total topics now linked to this exam/paper.")


if __name__ == "__main__":
    main()
