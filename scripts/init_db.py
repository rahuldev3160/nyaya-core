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

-- Real, queryable "institution" dimension (DECIDE-22) — `exam_id`'s `{institution}_{exam}`
-- naming (DECIDE-21) is a convention for humans reading an id, not something SQL can join
-- on. This table is what makes "every exam UPSC conducts" a real JOIN instead of a fragile
-- `exam_id LIKE 'upsc_%'` string match.
CREATE TABLE IF NOT EXISTS institutions (
    institution_id  TEXT PRIMARY KEY,
    name            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS exams (
    exam_id         TEXT PRIMARY KEY,
    institution_id  TEXT REFERENCES institutions(institution_id),
    name            TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_exams_institution ON exams(institution_id);

-- `paper_id` is scoped BY exam (DECIDE-21) — "essay" means something different under
-- upsc_cse than it would under uppcs, so the natural key is the pair, not paper_id alone.
-- A child entity's key shouldn't have to repeat its parent's identity to stay unique.
CREATE TABLE IF NOT EXISTS papers (
    exam_id   TEXT NOT NULL REFERENCES exams(exam_id),
    paper_id  TEXT NOT NULL,
    name      TEXT NOT NULL,
    PRIMARY KEY (exam_id, paper_id)
);
CREATE INDEX IF NOT EXISTS idx_papers_exam ON papers(exam_id);

-- Exam-agnostic canonical topic vocabulary (DECIDE-32/DECIDE-19: resolves a cross-project
-- decision pending since 2026-06 — "should 'Monetary Policy' in IES/RBI point to one
-- canonical entity?" Yes). A topic is NOT owned by an exam; `exam_topics` below is what
-- says which exams (and which paper within an exam) a topic is relevant to, and how much.
CREATE TABLE IF NOT EXISTS topics (
    topic_id         TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    parent_topic_id  TEXT REFERENCES topics(topic_id),
    notes            TEXT  -- free-text curator notes where a source has them (e.g. RBI's
                           -- exam-pattern observations); NOT the chunk_tags EAV table
                           -- (DECIDE-09) — that's keyed by real chunk_id, this is per-topic.
);
CREATE INDEX IF NOT EXISTS idx_topics_parent ON topics(parent_topic_id);

-- Junction table (DECIDE-19, extended DECIDE-21 with paper_id): one topic can serve many
-- exams (and many papers within an exam), each with its own relevance. A UPSC-only topic
-- just gets exactly one row here — reuse costs nothing to not have, costs nothing extra
-- when it does exist. `paper_id` defaults to the sentinel '_all' (a real string, not NULL —
-- SQLite treats every NULL as distinct for uniqueness, so NULL here would silently break
-- idempotent re-seeding of exam-wide topics) meaning "relevant across the whole exam, not
-- one specific paper" — e.g. current_affairs usually isn't paper-specific. Left
-- unconstrained (no FK to `papers`) since '_all' deliberately isn't a real paper row.
CREATE TABLE IF NOT EXISTS exam_topics (
    exam_id   TEXT NOT NULL REFERENCES exams(exam_id),
    paper_id  TEXT NOT NULL DEFAULT '_all',
    topic_id  TEXT NOT NULL REFERENCES topics(topic_id),
    weight    REAL NOT NULL DEFAULT 1.0,   -- e.g. avg PYQ frequency for this exam/paper, where known
    is_core   INTEGER NOT NULL DEFAULT 1 CHECK (is_core IN (0, 1)),
    PRIMARY KEY (exam_id, paper_id, topic_id)
);
CREATE INDEX IF NOT EXISTS idx_exam_topics_topic ON exam_topics(topic_id);

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
    paper_id         TEXT,  -- nullable (not every exam has papers); scoped by exam_id, see FK below
    topic_id         TEXT REFERENCES topics(topic_id),
    question_format  TEXT NOT NULL CHECK (question_format IN ('mcq', 'descriptive')),
    year             INTEGER,
    question_text    TEXT NOT NULL,
    options          TEXT,   -- MCQ-only, JSON-encoded list; NULL for descriptive
    correct_option   TEXT,   -- MCQ-only; NULL for descriptive
    statements       TEXT,   -- MCQ-only, JSON-encoded list; NULL for standalone-option MCQs
                             -- and all descriptive questions (DECIDE-23/BUG-04 — see
                             -- src/schema/models.py's MCQQuestion.statements)
    marks            INTEGER,  -- descriptive-only; NULL for MCQ
    word_limit       INTEGER,  -- descriptive-only; NULL for MCQ
    source_type      TEXT NOT NULL,
    verified_by      TEXT,
    reviewed_at      TEXT,
    FOREIGN KEY (exam_id, paper_id) REFERENCES papers(exam_id, paper_id)
);
CREATE INDEX IF NOT EXISTS idx_pyq_exam ON pyq_bank(exam_id);
CREATE INDEX IF NOT EXISTS idx_pyq_topic ON pyq_bank(topic_id);
CREATE INDEX IF NOT EXISTS idx_pyq_year ON pyq_bank(year);

-- DECIDE-23 (fixes BUG-04, found in Recall's equivalent feature): explanations are
-- generated in a separate, on-demand batch job — never live during a timed quiz — and
-- validated against src/schema/models.py's PYQExplanation before being written. `detail`
-- is a discriminated JSON blob (`option_format`: 'standalone' | 'statement_based') so a
-- statement-based MCQ ("how many statements are correct") gets per-statement rationale
-- instead of four fake independent option notes forced onto a format that doesn't fit —
-- the exact defect that left Recall's wrong-option fields silently empty in every row.
CREATE TABLE IF NOT EXISTS pyq_explanations (
    question_id           TEXT PRIMARY KEY REFERENCES pyq_bank(question_id),
    concept_summary        TEXT NOT NULL,  -- brief, always shown
    detail                 TEXT NOT NULL,  -- JSON-encoded ExplanationDetail (detailed, wrong-attempt-only)
    elimination_strategy   TEXT,           -- real exam-technique reasoning; nullable, not every question has one
    grounding_chunk_ids    TEXT NOT NULL DEFAULT '[]',  -- JSON-encoded list of chunk_id citations
    model_version          TEXT NOT NULL,
    generated_at           TEXT NOT NULL,
    verified_by            TEXT,
    reviewed_at            TEXT
);

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

# Real conducting bodies (DECIDE-22) — the queryable side of DECIDE-21's naming convention.
INSTITUTIONS = [
    ("upsc", "Union Public Service Commission"),
    ("rbi", "Reserve Bank of India"),
    ("uppsc", "Uttar Pradesh Public Service Commission"),
    ("hppsc", "Himachal Pradesh Public Service Commission"),
    ("ukpsc", "Uttarakhand Public Service Commission"),
    ("mppsc", "Madhya Pradesh Public Service Commission"),
]

# Registry rows for exams that already exist elsewhere (PLAN.md Phase 0). Seeded here,
# not hardcoded as a Python Literal, so adding an exam later is an INSERT, not a code change.
#
# Naming convention (DECIDE-21): exam_id = {institution}_{exam}, institution first, always
# the actual exam a candidate applies to — never a paper/subject within it (that's paper_id,
# scoped by exam_id, see `papers`/`PAPERS` below). "UPSC" alone is never a full exam_id —
# UPSC runs CSE, IES, EPFO, CAPF, etc. and each is a genuinely different exam. `institution_id`
# is the real FK (DECIDE-22) — the string prefix is for humans reading an id, this column is
# for SQL actually joining on it.
EXAMS = [
    ("upsc_cse", "upsc", "UPSC Civil Services Examination"),
    ("upsc_ies", "upsc", "UPSC Indian Economic Service"),
    ("rbi_gradeb", "rbi", "RBI Grade B"),
    # Placeholder (DECIDE-21) — Rahul referenced this as a real, distinct RBI exam from
    # Grade B; no content sourced yet.
    ("rbi_depr", "rbi", "RBI DEPR (Department of Economic and Policy Research)"),
    # State PCS exams confirmed feasible for Rahul (RESEARCH-08, 2026-09-06): open to
    # non-domicile candidates in General category, no disqualifying language requirement.
    # Each is already exam-level (not a paper of something else), so no restructuring needed.
    # UP/HP have a distinct commission-vs-exam acronym (UPPSC conducts UPPCS, HPPSC conducts
    # HPAS); UK/MP don't — their commission's own acronym doubles as the exam reference too,
    # a real asymmetry in how these bodies are commonly referred to, not an inconsistency.
    ("uppcs", "uppsc", "Uttar Pradesh PCS (UPPSC)"),
    ("hpas", "hppsc", "Himachal Pradesh Administrative Service (HPPSC)"),
    ("ukpsc", "ukpsc", "Uttarakhand PCS (UKPSC)"),
    ("mppsc", "mppsc", "Madhya Pradesh PCS (MPPSC)"),
]

# paper_id is scoped by exam_id (DECIDE-21) — short and un-prefixed, since `papers`' PK is
# the (exam_id, paper_id) pair, not paper_id alone. upsc_law_optional has no content yet
# (was ASSUME-01's placeholder) — kept as a paper row, not a separate exam.
PAPERS = [
    ("upsc_cse", "prelims_gs", "CSE Prelims — General Studies Paper I"),
    ("upsc_cse", "mains_gs1", "CSE Mains — General Studies I"),
    ("upsc_cse", "mains_gs2", "CSE Mains — General Studies II"),
    ("upsc_cse", "mains_gs3", "CSE Mains — General Studies III"),
    ("upsc_cse", "mains_gs4", "CSE Mains — General Studies IV (Ethics)"),
    ("upsc_cse", "essay", "CSE Mains — Essay"),
    ("upsc_cse", "eco_optional", "CSE Mains — Economics Optional"),
    ("upsc_cse", "law_optional", "CSE Mains — Law Optional (placeholder, no content yet)"),
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
        "INSERT OR IGNORE INTO institutions (institution_id, name) VALUES (?, ?)",
        INSTITUTIONS,
    )
    conn.executemany(
        "INSERT OR IGNORE INTO exams (exam_id, institution_id, name, created_at) VALUES (?, ?, ?, ?)",
        [(exam_id, inst_id, name, now) for exam_id, inst_id, name in EXAMS],
    )
    conn.executemany(
        "INSERT OR IGNORE INTO content_types (type_id, name, is_time_sensitive) VALUES (?, ?, ?)",
        CONTENT_TYPES,
    )
    conn.executemany(
        "INSERT OR IGNORE INTO papers (exam_id, paper_id, name) VALUES (?, ?, ?)",
        PAPERS,
    )
    conn.commit()

    inst_count = conn.execute("SELECT COUNT(*) FROM institutions").fetchone()[0]
    exam_count = conn.execute("SELECT COUNT(*) FROM exams").fetchone()[0]
    ct_count = conn.execute("SELECT COUNT(*) FROM content_types").fetchone()[0]
    paper_count = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    conn.close()
    print(f"core.db ready at {DB_PATH} — {inst_count} institutions, {exam_count} exams, "
          f"{ct_count} content_types, {paper_count} papers seeded.")


if __name__ == "__main__":
    main()
