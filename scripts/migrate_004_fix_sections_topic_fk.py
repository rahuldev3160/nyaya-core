"""One-time migration (BUG-05): fixes `sections.topic_id`'s foreign key, which has been
silently pointing at a dropped table since migrate_002.

Root cause: migrate_002 ran `ALTER TABLE topics RENAME TO topics_old` then recreated
`topics` and dropped `topics_old`, on the stated assumption that "topics.topic_id is still
the PK, no data there needs touching" for `sections`' FK. That assumption is wrong on this
SQLite build — renaming a table does NOT rewrite other tables' stored FK clauses that
reference it by name (that rewrite is a newer/optional SQLite behavior, not guaranteed).
`sections` was created before migrate_002 ran, so its schema literally says
`REFERENCES "topics_old"(topic_id)` — a table that no longer exists. This was never caught
because `sections` had zero rows until the first real (non-synthetic-smoke-test) ingestion
run, which is what surfaced it (`sqlite3.OperationalError: no such table: main.topics_old`).

Safe to run: `sections` has 0 rows at the time this was written (verified before writing
this script) — a straight recreate, not a data migration. If it ever has real rows when
this runs, the copy step below still preserves them.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "core.db"


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF;")

    current_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='sections'"
    ).fetchone()
    if current_sql is None:
        print("No `sections` table — nothing to migrate. Re-run scripts/init_db.py instead.")
        return
    if "topics_old" not in current_sql[0]:
        print("`sections`.topic_id already references `topics` correctly — nothing to do.")
        return

    rows = conn.execute("SELECT * FROM sections").fetchall()

    conn.execute("ALTER TABLE sections RENAME TO sections_old")
    conn.execute("""CREATE TABLE sections (
        section_id    TEXT PRIMARY KEY,
        doc_id        TEXT NOT NULL,
        exam_id       TEXT NOT NULL REFERENCES exams(exam_id),
        topic_id      TEXT REFERENCES topics(topic_id),
        content_type  TEXT REFERENCES content_types(type_id),
        heading       TEXT,
        full_text     TEXT NOT NULL,
        page_start    INTEGER,
        page_end      INTEGER
    )""")
    if rows:
        conn.executemany(
            "INSERT INTO sections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows
        )
    conn.execute("DROP TABLE sections_old")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.commit()

    n = conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
    conn.close()
    print(f"Fixed: sections.topic_id now references topics(topic_id) correctly. "
          f"{len(rows)} row(s) preserved, {n} total rows now.")


if __name__ == "__main__":
    main()
