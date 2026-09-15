"""One-time migration (DECIDE-30): registers PFRDA Officer Grade 'A' (Assistant Manager)
2026 as a new exam, with a fresh, real-syllabus-derived topic taxonomy for its General and
Research streams.

Real source: PFRDA notification, Advt. No. 03/2026, dated 03.09.2026 —
`~/Desktop/opportunities/govt notifications/Recruitment of Officer Grade A (Assistant
Manager)-2026.pdf` (32 pages, read via vision this session). Rahul is applying to both
General and Research streams.

Modeled as ONE exam (`pfrda_gradea`), not two, per DECIDE-21/25's precedent (a candidate
applies to one recruitment; streams are papers within it, like eco_optional_1/2) — but
General's and Research's Phase-I/II Paper-2 syllabi are completely disjoint, so they get
separate paper rows, not a shared one:
  - phase1_p1          — common to all streams: English/Quant Aptitude/Reasoning/GA (90
                          questions total: 20/20/30/20 — real per-notification split, used
                          as real weight, not guessed)
  - phase1_p2_general   — General stream's Phase-I Paper 2
  - phase1_p2_research  — Research stream's Phase-I Paper 2
  - phase2_p1           — common: English descriptive (precis/essay/comprehension)
  - phase2_p2_general   — same syllabus as phase1_p2_general, greater depth (Phase-II)
  - phase2_p2_research  — same syllabus as phase1_p2_research, greater depth (Phase-II)

Per DECIDE-29's precedent (EPFO): fresh, exam-specific topics rather than reusing canonical
UPSC/RBI/IES topics, even where a topic sounds similar (e.g. "Economics") — real PYQ
sampling this session (2025 PFRDA paper-book) confirmed PFRDA General's Economics section is
genuinely UG-101 level, well below the postgrad depth of the canonical Macro Theory topics
CSE/RBI/IES share. Forcing a link would misrepresent depth for future retrieval/question-bank
use. Real follow-up noted in DECIDE-30, not done here: PFRDA's "Union Budget & Economic
Survey" line may genuinely match the canonical Indian-Economy/current-affairs topic's depth
and could be cross-linked later — deliberately deferred rather than guessed in this pass.

Weighting: Phase-I Paper 1's 4 sections have real per-section question counts stated in the
notification (20/20/30/20 of 90) — used directly as weight. The General/Research Paper-2
subject lists have NO stated per-subject breakdown anywhere in the real notification (just a
flat list for 50 questions/100 marks) and no real PYQ-frequency data exists yet (the 3 real
paper-books on disk haven't been ingested) — so every Paper-2 topic gets an honest flat
placeholder weight of 1.0, the same pattern already used for State PCS's not-yet-frequency-
derived topics (see RISK-04's original problem). Do not treat these placeholder weights as
real until a future ingestion run computes them from actual PYQ frequency.

Run: .venv/bin/python scripts/migrate_008_register_pfrda.py
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "core.db"

EXAM_ID = "pfrda_gradea"
INSTITUTION_ID = "pfrda"

PAPERS = [
    ("phase1_p1", "Phase I, Paper 1 — English/Quant Aptitude/Reasoning/GA (all streams)"),
    ("phase1_p2_general", "Phase I, Paper 2 — General stream"),
    ("phase1_p2_research", "Phase I, Paper 2 — Research stream"),
    ("phase2_p1", "Phase II, Paper 1 — English descriptive (all streams)"),
    ("phase2_p2_general", "Phase II, Paper 2 — General stream"),
    ("phase2_p2_research", "Phase II, Paper 2 — Research stream"),
]

# (topic_id, name) — Phase-I Paper 1, real per-section question count as weight (of 90).
PHASE1_P1_TOPICS = [
    ("pfrda_english_language", "English Language (PFRDA)", 20),
    ("pfrda_quantitative_aptitude", "Quantitative Aptitude (PFRDA)", 20),
    ("pfrda_reasoning", "Test of Reasoning (PFRDA)", 30),
    ("pfrda_general_awareness_financial", "General Awareness incl. Financial Sector (PFRDA)", 20),
]

PHASE2_P1_TOPICS = [
    ("pfrda_english_descriptive", "English Descriptive Writing — Precis/Essay/Comprehension (PFRDA)", 1.0),
]

# General stream Paper-2 syllabus — no real per-subject weight breakdown exists; flat 1.0.
GENERAL_P2_TOPICS = [
    ("pfrda_act_2013", "PFRDA Act 2013 & Amendments"),
    ("pfrda_budget_economic_survey", "Union Budget & Economic Survey (PFRDA)"),
    ("pfrda_commerce_accountancy", "Commerce & Accountancy (PFRDA)"),
    ("pfrda_management", "Management — Processes, Leadership, HRD, Motivation Theories (PFRDA)"),
    ("pfrda_finance", "Finance — Financial System/Markets/Derivatives/Fiscal Policy (PFRDA)"),
    ("pfrda_costing", "Costing — Cost/Management Accounting, Lean/Six Sigma (PFRDA)"),
    ("pfrda_companies_act", "Companies Act 2013 — Chapters III/IV/VIII/X/XI/XII/XXVII"),
    ("pfrda_economics_basic", "Economics — UG-level (PFRDA General; NOT linked to postgrad-depth canonical Macro Theory topics)"),
    ("pfrda_pension_sector", "Pension Sector — NPS, APY, Annuities (PFRDA)"),
    ("pfrda_ai_ml", "AI/ML Fundamentals (PFRDA)"),
    ("pfrda_media", "Media — Convergence, Digital Divide, Algorithms (PFRDA)"),
    ("pfrda_marketing_communication", "Marketing & Communication (PFRDA)"),
]

# Research stream Paper-2 syllabus — pure statistics/OR, zero overlap with General stream.
RESEARCH_P2_TOPICS = [
    ("pfrda_probability_theory", "Probability Theory (PFRDA Research)"),
    ("pfrda_descriptive_statistics", "Descriptive Statistics (PFRDA Research)"),
    ("pfrda_probability_distributions", "Probability Distributions (PFRDA Research)"),
    ("pfrda_statistical_inference", "Statistical Inference (PFRDA Research)"),
    ("pfrda_sampling_techniques", "Sampling Techniques (PFRDA Research)"),
    ("pfrda_hypothesis_testing", "Hypothesis Testing (PFRDA Research)"),
    ("pfrda_economic_statistics", "Economic Statistics (PFRDA Research)"),
    ("pfrda_time_series_analysis", "Time Series Analysis (PFRDA Research)"),
    ("pfrda_operations_research", "Operations Research (PFRDA Research)"),
    ("pfrda_statistical_quality_control", "Statistical Quality Control (PFRDA Research)"),
    ("pfrda_statistical_computing", "Statistical Computing (PFRDA Research)"),
]


def _already_migrated(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM exams WHERE exam_id = ?", (EXAM_ID,)).fetchone() is not None


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    if _already_migrated(conn):
        print("Already migrated — nothing to do.")
        conn.close()
        return

    conn.execute(
        "INSERT OR IGNORE INTO institutions (institution_id, name) VALUES (?, ?)",
        (INSTITUTION_ID, "Pension Fund Regulatory and Development Authority"),
    )
    conn.execute(
        "INSERT INTO exams (exam_id, name, created_at, institution_id) VALUES (?, ?, ?, ?)",
        (EXAM_ID, "PFRDA Officer Grade 'A' (Assistant Manager)",
         datetime.now(timezone.utc).isoformat(), INSTITUTION_ID),
    )
    conn.executemany(
        "INSERT INTO papers (exam_id, paper_id, name) VALUES (?, ?, ?)",
        [(EXAM_ID, pid, name) for pid, name in PAPERS],
    )
    print(f"Registered exam {EXAM_ID} under institution {INSTITUTION_ID}, {len(PAPERS)} papers.")

    def seed(topics, paper_ids, weight_fn):
        for topic_id, name, *rest in topics:
            conn.execute(
                "INSERT OR IGNORE INTO topics (topic_id, name) VALUES (?, ?)", (topic_id, name)
            )
            weight = weight_fn(rest)
            for paper_id in paper_ids:
                conn.execute(
                    "INSERT INTO exam_topics (exam_id, paper_id, topic_id, weight, is_core) "
                    "VALUES (?, ?, ?, ?, 1)",
                    (EXAM_ID, paper_id, topic_id, weight),
                )

    seed(PHASE1_P1_TOPICS, ["phase1_p1"], lambda rest: round(100.0 * rest[0] / 90, 2))
    seed(PHASE2_P1_TOPICS, ["phase2_p1"], lambda rest: rest[0])
    seed(GENERAL_P2_TOPICS, ["phase1_p2_general", "phase2_p2_general"], lambda rest: 1.0)
    seed(RESEARCH_P2_TOPICS, ["phase1_p2_research", "phase2_p2_research"], lambda rest: 1.0)

    n_topics = len(PHASE1_P1_TOPICS) + len(PHASE2_P1_TOPICS) + len(GENERAL_P2_TOPICS) + len(RESEARCH_P2_TOPICS)
    print(f"Seeded {n_topics} PFRDA-specific topics "
          f"({len(GENERAL_P2_TOPICS)} General P2 + {len(RESEARCH_P2_TOPICS)} Research P2 "
          f"at flat placeholder weight 1.0 — no real per-subject frequency data yet).")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
