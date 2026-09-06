"""Import IES and RBI Grade B's real, already-curated topic taxonomies from
Descriptive-exams' own databases — no new research needed (RESEARCH-07 already found
these; this just wires them into nyaya-core's exam-agnostic `topics`/`exam_topics`).

Both source DBs are read-only inputs here — this script never writes back to them.

IES (`ies.db`'s `topics` table, 156 rows): already has a real 3-level hierarchy
(topic/subtopic via `subtopic_of`) AND real `paper_id` values (`ge_01`-`ge_04`) — imported
1:1, `syllabus_weight` becomes `exam_topics.weight`, `paper_id` preserved (DECIDE-21).

RBI Grade B (`rbi.db`'s `rbi_topic_weights`, 29 rows): flatter — `subject` (9 groups:
macro, micro, growth, indian_econ, intl_econ, pub_finance, quant, env_econ, rbi_banking)
becomes a parent topic (`RBI_SUBJECT_NAMES` below gives each a readable name — the
`subject` codes themselves aren't self-explanatory), each row's `topic` becomes a child.
`base_weight` becomes `exam_topics.weight`. No `paper_id` in the source (RBI Grade B's own
paper breakdown isn't registered in `papers` yet — no real content sourced for it — so
these link at paper_id='_all', exam-wide, until that changes) — real full-text `notes`
(genuinely useful, e.g. "Mundell-Fleming appeared TWICE in 2024") go into `topics.notes`,
NOT `chunk_tags` (that table is keyed by real chunk_id, a topic is a different entity).

Checked before writing this: zero topic_id collisions between these 185 rows and the 316
already in nyaya-core's `topics` (UPSC + 4 State PCS) — safe to import as-is, no renaming
needed to avoid accidentally merging two different real-world concepts under one id.
"""

import json
import sqlite3
from pathlib import Path

CORE_DB_PATH = Path(__file__).parent.parent / "data" / "core.db"
IES_DB_PATH = Path("/Users/rahulsingh/Desktop/Claude Projects/Descriptive-exams/data/ies.db")
RBI_DB_PATH = Path("/Users/rahulsingh/Desktop/Claude Projects/Descriptive-exams/data/rbi.db")

RBI_SUBJECT_NAMES = {
    "macro": "Macroeconomics", "micro": "Microeconomics", "growth": "Growth & Development Theory",
    "indian_econ": "Indian Economy", "intl_econ": "International Economics",
    "pub_finance": "Public Finance", "quant": "Quantitative Methods", "env_econ": "Environmental Economics",
    "rbi_banking": "Banking & RBI Functions",
}


def import_ies(core_conn: sqlite3.Connection) -> tuple[int, int]:
    ies_conn = sqlite3.connect(IES_DB_PATH)
    rows = ies_conn.execute(
        "SELECT topic_id, paper_id, topic_name, subtopic_of, syllabus_weight FROM topics"
    ).fetchall()
    ies_conn.close()

    core_conn.executemany(
        "INSERT OR IGNORE INTO topics (topic_id, name, parent_topic_id) VALUES (?, ?, ?)",
        [(tid, name, parent) for tid, _paper, name, parent, _w in rows],
    )
    core_conn.executemany(
        "INSERT OR IGNORE INTO exam_topics (exam_id, paper_id, topic_id, weight) VALUES (?, ?, ?, ?)",
        [("upsc_ies", paper, tid, weight) for tid, paper, _name, _parent, weight in rows],
    )
    return len(rows), len({r[1] for r in rows})


def import_rbi(core_conn: sqlite3.Connection) -> int:
    rbi_conn = sqlite3.connect(RBI_DB_PATH)
    rows = rbi_conn.execute("SELECT topic, subject, base_weight, notes FROM rbi_topic_weights").fetchall()
    rbi_conn.close()

    core_conn.executemany(
        "INSERT OR IGNORE INTO topics (topic_id, name, parent_topic_id) VALUES (?, ?, NULL)",
        [(sid, name, ) for sid, name in RBI_SUBJECT_NAMES.items()],
    )
    core_conn.executemany(
        "INSERT OR IGNORE INTO exam_topics (exam_id, paper_id, topic_id, weight) VALUES ('rbi_gradeb', '_all', ?, 1.0)",
        [(sid,) for sid in RBI_SUBJECT_NAMES],
    )

    core_conn.executemany(
        "INSERT OR IGNORE INTO topics (topic_id, name, parent_topic_id, notes) VALUES (?, ?, ?, ?)",
        [(topic, topic.replace("_", " ").title(), subject, notes) for topic, subject, _w, notes in rows],
    )
    core_conn.executemany(
        "INSERT OR IGNORE INTO exam_topics (exam_id, paper_id, topic_id, weight) VALUES ('rbi_gradeb', '_all', ?, ?)",
        [(topic, weight) for topic, _s, weight, _n in rows],
    )
    return len(rows)


def main() -> None:
    conn = sqlite3.connect(CORE_DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")

    ies_count, ies_papers = import_ies(conn)
    rbi_count = import_rbi(conn)
    conn.commit()

    ies_total = conn.execute(
        "SELECT COUNT(*) FROM exam_topics WHERE exam_id = 'upsc_ies'"
    ).fetchone()[0]
    rbi_total = conn.execute(
        "SELECT COUNT(*) FROM exam_topics WHERE exam_id = 'rbi_gradeb'"
    ).fetchone()[0]
    conn.close()
    print(f"IES: {ies_count} topics across {ies_papers} papers imported from ies.db "
          f"({ies_total} exam_topics rows now linked to upsc_ies).")
    print(f"RBI: {rbi_count} topics + 9 subject-groupings imported from rbi.db "
          f"({rbi_total} exam_topics rows now linked to rbi_gradeb).")


if __name__ == "__main__":
    main()
