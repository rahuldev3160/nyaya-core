"""Create and seed data/core.db.

Re-runnable: CREATE TABLE IF NOT EXISTS + INSERT OR IGNORE, so re-running this after a
fresh clone never duplicates registry rows or wipes ingested content.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "core.db"

SCHEMA = """
-- PRAGMA foreign_keys is OFF by default in SQLite even when a column says REFERENCES —
-- it has to be turned on per-connection, every time, or FKs are silently unenforced.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS exams (
    exam_id     TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS papers (
    paper_id    TEXT PRIMARY KEY,
    exam_id     TEXT NOT NULL REFERENCES exams(exam_id),
    name        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_papers_exam ON papers(exam_id);

CREATE TABLE IF NOT EXISTS topics (
    topic_id         TEXT PRIMARY KEY,
    exam_id          TEXT NOT NULL REFERENCES exams(exam_id),
    name             TEXT NOT NULL,
    parent_topic_id  TEXT REFERENCES topics(topic_id)
);
CREATE INDEX IF NOT EXISTS idx_topics_exam ON topics(exam_id);
CREATE INDEX IF NOT EXISTS idx_topics_parent ON topics(parent_topic_id);

CREATE TABLE IF NOT EXISTS content_types (
    type_id            TEXT PRIMARY KEY,
    name               TEXT NOT NULL,
    is_time_sensitive  INTEGER NOT NULL DEFAULT 0 CHECK (is_time_sensitive IN (0, 1))
);

-- Parent-document layer for auto-merging retrieval (DECIDE-14). One row per Stage-1
-- markdown-header section, NOT the whole source document.
CREATE TABLE IF NOT EXISTS sections (
    section_id    TEXT PRIMARY KEY,
    doc_id        TEXT NOT NULL,
    exam_id       TEXT NOT NULL REFERENCES exams(exam_id),
    topic_id      TEXT REFERENCES topics(topic_id),
    content_type  TEXT REFERENCES content_types(type_id),
    heading       TEXT,
    full_text     TEXT NOT NULL,
    page_start    INTEGER,
    page_end      INTEGER
);
CREATE INDEX IF NOT EXISTS idx_sections_exam ON sections(exam_id);
CREATE INDEX IF NOT EXISTS idx_sections_doc ON sections(doc_id);

-- One table for both PYQ formats, discriminated by question_format (mirrors
-- src/schema/models.py's MCQQuestion/DescriptiveQuestion split).
CREATE TABLE IF NOT EXISTS pyq_bank (
    question_id      TEXT PRIMARY KEY,
    exam_id          TEXT NOT NULL REFERENCES exams(exam_id),
    paper_id         TEXT REFERENCES papers(paper_id),
    topic_id         TEXT REFERENCES topics(topic_id),
    question_format  TEXT NOT NULL CHECK (question_format IN ('mcq', 'descriptive')),
    year             INTEGER,
    question_text    TEXT NOT NULL,
    options          TEXT,   -- MCQ-only, JSON-encoded list; NULL for descriptive
    correct_option   TEXT,   -- MCQ-only; NULL for descriptive
    marks            INTEGER,  -- descriptive-only; NULL for MCQ
    word_limit       INTEGER,  -- descriptive-only; NULL for MCQ
    source_type      TEXT NOT NULL,
    verified_by      TEXT,
    reviewed_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_pyq_exam ON pyq_bank(exam_id);
CREATE INDEX IF NOT EXISTS idx_pyq_topic ON pyq_bank(topic_id);
CREATE INDEX IF NOT EXISTS idx_pyq_year ON pyq_bank(year);

-- EAV side table (DECIDE-09): lets SQL filter "every chunk tagged difficulty=hard"
-- directly. The `tags` JSON column on chunks/pyq_bank (see LanceDB side + PYQBase.tags)
-- covers "give me everything about this one row" instead — the two serve different
-- query shapes, kept deliberately redundant rather than picking one.
CREATE TABLE IF NOT EXISTS chunk_tags (
    chunk_id   TEXT NOT NULL,
    tag_key    TEXT NOT NULL,
    tag_value  TEXT NOT NULL,
    PRIMARY KEY (chunk_id, tag_key)
);
CREATE INDEX IF NOT EXISTS idx_chunk_tags_kv ON chunk_tags(tag_key, tag_value);
"""

# Registry rows for exams that already exist elsewhere (PLAN.md Phase 0). Seeded here,
# not hardcoded as a Python Literal, so adding an exam later is an INSERT, not a code change.
EXAMS = [
    ("upsc_prelims_gs", "UPSC Civil Services Prelims — General Studies"),
    ("upsc_mains_gs", "UPSC Civil Services Mains — General Studies"),
    ("essay", "UPSC Civil Services Mains — Essay"),
    ("ethics", "UPSC Civil Services Mains — Ethics (GS-IV)"),
    ("ies", "Indian Economic Service — General Economics"),
    ("rbi_grade_b", "RBI Grade B"),
    ("upsc_eco_opt", "UPSC Civil Services Mains — Economics Optional"),
    # Placeholders (ASSUME-01) — content pending, Rahul to supply PDFs before Phase 1 ingest.
    ("upsc_law_optional", "UPSC Civil Services Mains — Law Optional (placeholder, no content yet)"),
]

CONTENT_TYPES = [
    ("mains_pyq", "Mains PYQ", 0),
    ("mcq_pyq", "MCQ PYQ", 0),
    ("official_report", "Official Report", 0),
    ("study_material", "Study Material", 0),
    ("current_affairs", "Current Affairs", 1),
    ("monthly_report", "Monthly Report", 1),
    ("yearly_report", "Yearly Report", 1),
    ("model_answer", "Model Answer", 0),
    ("syllabus", "Syllabus", 0),
]


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(SCHEMA)

    now = datetime.now(timezone.utc).isoformat()
    conn.executemany(
        "INSERT OR IGNORE INTO exams (exam_id, name, created_at) VALUES (?, ?, ?)",
        [(exam_id, name, now) for exam_id, name in EXAMS],
    )
    conn.executemany(
        "INSERT OR IGNORE INTO content_types (type_id, name, is_time_sensitive) VALUES (?, ?, ?)",
        CONTENT_TYPES,
    )
    conn.commit()

    exam_count = conn.execute("SELECT COUNT(*) FROM exams").fetchone()[0]
    ct_count = conn.execute("SELECT COUNT(*) FROM content_types").fetchone()[0]
    conn.close()
    print(f"core.db ready at {DB_PATH} — {exam_count} exams, {ct_count} content_types seeded.")


if __name__ == "__main__":
    main()
