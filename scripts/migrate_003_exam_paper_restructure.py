"""One-time migration (DECIDE-21): restructures exam_id/paper_id naming and scoping.

Before: essay/ethics/upsc_mains_gs/upsc_eco_optional/upsc_law_optional/upsc_prelims_gs were
each modeled as a separate top-level EXAM — but they're really PAPERS of one exam, UPSC's
Civil Services Examination. `ies` and `rbi_grade_b` were bare/ambiguous (UPSC and RBI each
run multiple distinct exams). This migration:
1. Merges the 6 UPSC exams above into one `upsc_cse` exam with 8 `papers` rows.
2. Renames `ies` -> `upsc_ies`, `rbi_grade_b` -> `rbi_gradeb` (institution_exam convention).
3. Adds `rbi_depr` as a new placeholder exam (Rahul referenced it as a real, distinct RBI
   exam from Grade B).
4. Rebuilds `papers` with a composite (exam_id, paper_id) PK — paper_id no longer needs
   global uniqueness, matching how `topic_id` already works (a child needn't repeat its
   parent's identity).
5. Rebuilds `exam_topics` with a `paper_id` column (default '_all' sentinel) so a topic's
   relevance can be paper-specific, not just exam-wide — required once Essay/Ethics/
   Eco-Optional share one exam_id; without this they'd all see each other's topics.
6. Migrates the 271 existing `upsc_prelims_gs` exam_topics rows to
   (exam_id='upsc_cse', paper_id='prelims_gs').

Safe to run against the live `data/core.db` at the point this was written: only
`upsc_prelims_gs` has any real dependent data (271 exam_topics rows); everything else being
restructured has zero sections/pyq_bank/chunks. Idempotent: checks `papers`' shape before
doing anything.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "core.db"

NEW_EXAMS = [
    ("upsc_cse", "UPSC Civil Services Examination"),
    ("upsc_ies", "UPSC Indian Economic Service"),
    ("rbi_gradeb", "RBI Grade B"),
    ("rbi_depr", "RBI DEPR (Department of Economic and Policy Research)"),
]

NEW_PAPERS = [
    ("upsc_cse", "prelims_gs", "CSE Prelims — General Studies Paper I"),
    ("upsc_cse", "mains_gs1", "CSE Mains — General Studies I"),
    ("upsc_cse", "mains_gs2", "CSE Mains — General Studies II"),
    ("upsc_cse", "mains_gs3", "CSE Mains — General Studies III"),
    ("upsc_cse", "mains_gs4", "CSE Mains — General Studies IV (Ethics)"),
    ("upsc_cse", "essay", "CSE Mains — Essay"),
    ("upsc_cse", "eco_optional", "CSE Mains — Economics Optional"),
    ("upsc_cse", "law_optional", "CSE Mains — Law Optional (placeholder, no content yet)"),
]

RETIRED_UPSC_EXAM_IDS = [
    "upsc_prelims_gs", "upsc_mains_gs", "essay", "ethics", "upsc_eco_optional", "upsc_law_optional",
]


def _already_migrated(conn: sqlite3.Connection) -> bool:
    cols = [row[1] for row in conn.execute("PRAGMA table_info(papers)").fetchall()]
    return "exam_id" in cols and conn.execute(
        "SELECT COUNT(*) FROM pragma_table_info('papers') WHERE pk > 0"
    ).fetchone()[0] >= 2  # composite PK has 2+ columns with pk rank > 0


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF;")  # rebuilding referenced tables mid-migration

    if _already_migrated(conn):
        print("papers already has a composite PK — migration already applied, doing nothing.")
        return

    old_exam_topics = conn.execute("SELECT exam_id, topic_id, weight, is_core FROM exam_topics").fetchall()

    # --- exams: rename/add, then retire the 6 that become papers ---
    now = datetime.now(timezone.utc).isoformat()
    conn.executemany(
        "INSERT OR IGNORE INTO exams (exam_id, name, created_at) VALUES (?, ?, ?)",
        [(eid, name, now) for eid, name in NEW_EXAMS],
    )
    conn.execute("DELETE FROM exams WHERE exam_id IN ('ies', 'rbi_grade_b')")
    conn.execute(
        f"DELETE FROM exams WHERE exam_id IN ({','.join('?' * len(RETIRED_UPSC_EXAM_IDS))})",
        RETIRED_UPSC_EXAM_IDS,
    )

    # --- papers: rebuild with composite PK ---
    conn.execute("DROP TABLE IF EXISTS papers")
    conn.execute("""CREATE TABLE papers (
        exam_id TEXT NOT NULL REFERENCES exams(exam_id), paper_id TEXT NOT NULL, name TEXT NOT NULL,
        PRIMARY KEY (exam_id, paper_id)
    )""")
    conn.execute("CREATE INDEX idx_papers_exam ON papers(exam_id)")
    conn.executemany("INSERT INTO papers (exam_id, paper_id, name) VALUES (?, ?, ?)", NEW_PAPERS)

    # --- exam_topics: rebuild with paper_id column, migrate upsc_prelims_gs rows ---
    conn.execute("DROP TABLE IF EXISTS exam_topics")
    conn.execute("""CREATE TABLE exam_topics (
        exam_id TEXT NOT NULL REFERENCES exams(exam_id), paper_id TEXT NOT NULL DEFAULT '_all',
        topic_id TEXT NOT NULL REFERENCES topics(topic_id), weight REAL NOT NULL DEFAULT 1.0,
        is_core INTEGER NOT NULL DEFAULT 1 CHECK (is_core IN (0, 1)),
        PRIMARY KEY (exam_id, paper_id, topic_id)
    )""")
    conn.execute("CREATE INDEX idx_exam_topics_topic ON exam_topics(topic_id)")
    for exam_id, topic_id, weight, is_core in old_exam_topics:
        new_exam_id = "upsc_cse" if exam_id == "upsc_prelims_gs" else exam_id
        new_paper_id = "prelims_gs" if exam_id == "upsc_prelims_gs" else "_all"
        conn.execute(
            "INSERT INTO exam_topics (exam_id, paper_id, topic_id, weight, is_core) VALUES (?, ?, ?, ?, ?)",
            (new_exam_id, new_paper_id, topic_id, weight, is_core),
        )

    # --- pyq_bank: rebuild for the new composite FK shape (empty table, no data to move) ---
    pyq_count = conn.execute("SELECT COUNT(*) FROM pyq_bank").fetchone()[0]
    if pyq_count == 0:
        conn.execute("DROP TABLE IF EXISTS pyq_bank")
        conn.execute("""CREATE TABLE pyq_bank (
            question_id TEXT PRIMARY KEY, exam_id TEXT NOT NULL REFERENCES exams(exam_id),
            paper_id TEXT, topic_id TEXT REFERENCES topics(topic_id),
            question_format TEXT NOT NULL CHECK (question_format IN ('mcq', 'descriptive')),
            year INTEGER, question_text TEXT NOT NULL, options TEXT, correct_option TEXT,
            marks INTEGER, word_limit INTEGER, source_type TEXT NOT NULL,
            verified_by TEXT, reviewed_at TEXT,
            FOREIGN KEY (exam_id, paper_id) REFERENCES papers(exam_id, paper_id)
        )""")
        conn.execute("CREATE INDEX idx_pyq_exam ON pyq_bank(exam_id)")
        conn.execute("CREATE INDEX idx_pyq_topic ON pyq_bank(topic_id)")
        conn.execute("CREATE INDEX idx_pyq_year ON pyq_bank(year)")
    else:
        print(f"WARNING: pyq_bank has {pyq_count} rows — not rebuilt, FK still points at old papers shape.")

    conn.execute("PRAGMA foreign_keys = ON;")
    conn.commit()

    n_exams = conn.execute("SELECT COUNT(*) FROM exams").fetchone()[0]
    n_papers = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    n_et = conn.execute("SELECT COUNT(*) FROM exam_topics").fetchone()[0]
    conn.close()
    print(f"Migrated: {n_exams} exams, {n_papers} papers, {n_et} exam_topics rows "
          f"(upsc_prelims_gs's 271 rows now under upsc_cse/prelims_gs).")


if __name__ == "__main__":
    main()
