"""One-time migration (DECIDE-19): rebuilds `topics` as exam-agnostic and introduces the
`exam_topics` junction table. Resolves DECIDE-32 (pending since 2026-06 in Descriptive-exams'
AUDIT-008) — a topic is now a canonical entity, not owned by one exam.

Safe to run against the live `data/core.db` at the point this was written: 271 topic rows,
all `exam_id='upsc_prelims_gs'`, zero dependent `sections`/`chunks`/`pyq_bank` rows. If this
is ever re-run later with real content ingested, it still works (copies every existing
(topic_id, exam_id) pair into `exam_topics`), but by then `scripts/init_db.py`'s schema
should already be correct on a fresh clone — this script exists for migrating an
already-initialized database, not as an ongoing part of setup.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "core.db"


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF;")  # rebuilding a referenced table mid-migration

    old_rows = conn.execute("SELECT topic_id, exam_id, name, parent_topic_id FROM topics").fetchall()
    if not old_rows:
        print("No rows in topics — nothing to migrate. Re-run scripts/init_db.py instead.")
        return

    already_migrated = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='exam_topics'"
    ).fetchone()[0]
    if already_migrated:
        print("exam_topics already exists — migration already applied, doing nothing.")
        return

    conn.execute("ALTER TABLE topics RENAME TO topics_old")
    # SQLite keeps an index's declared name pointing at the renamed table — drop the old
    # ones explicitly or CREATE INDEX on the new `topics` below collides on the name.
    conn.execute("DROP INDEX IF EXISTS idx_topics_exam")
    conn.execute("DROP INDEX IF EXISTS idx_topics_parent")
    conn.execute("""CREATE TABLE topics (
        topic_id TEXT PRIMARY KEY, name TEXT NOT NULL, parent_topic_id TEXT REFERENCES topics(topic_id)
    )""")
    conn.execute("CREATE INDEX idx_topics_parent ON topics(parent_topic_id)")
    conn.execute("""CREATE TABLE exam_topics (
        exam_id TEXT NOT NULL REFERENCES exams(exam_id), topic_id TEXT NOT NULL REFERENCES topics(topic_id),
        weight REAL NOT NULL DEFAULT 1.0, is_core INTEGER NOT NULL DEFAULT 1 CHECK (is_core IN (0, 1)),
        PRIMARY KEY (exam_id, topic_id)
    )""")
    conn.execute("CREATE INDEX idx_exam_topics_topic ON exam_topics(topic_id)")

    seen_topic_ids: set[str] = set()
    for topic_id, exam_id, name, parent_topic_id in old_rows:
        if topic_id not in seen_topic_ids:
            conn.execute(
                "INSERT INTO topics (topic_id, name, parent_topic_id) VALUES (?, ?, ?)",
                (topic_id, name, parent_topic_id),
            )
            seen_topic_ids.add(topic_id)
        conn.execute(
            "INSERT OR IGNORE INTO exam_topics (exam_id, topic_id) VALUES (?, ?)", (exam_id, topic_id)
        )

    # Point sections.topic_id's FK-in-spirit references at nothing that changed shape —
    # topics.topic_id is still the PK, no data there needs touching.
    conn.execute("DROP TABLE topics_old")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.commit()

    n_topics = conn.execute("SELECT COUNT(*) FROM topics").fetchone()[0]
    n_exam_topics = conn.execute("SELECT COUNT(*) FROM exam_topics").fetchone()[0]
    conn.close()
    print(f"Migrated: {len(old_rows)} old rows -> {n_topics} canonical topics, "
          f"{n_exam_topics} exam_topics relevance rows.")


if __name__ == "__main__":
    main()
