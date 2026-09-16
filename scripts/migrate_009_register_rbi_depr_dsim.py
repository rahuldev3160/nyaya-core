"""Migration (DECIDE-32, see docs/decisions.md): registers RBI DEPR's real paper/topic
structure (the exam row already existed as a placeholder, DECIDE-30) and a new RBI DSIM
exam, both from the real official notification (RBISB/DA/01/2026-27, dated 29.04.2026,
`~/Desktop/opportunities/govt notifications/DEPR29042026....pdf`, read via vision this
session). Also implements RESEARCH-11's proposed cross-exam topic-linking plan: reuses
`rbi_gradeb`'s existing but previously-unlinked canonical topics (macro/micro/growth/
pub_finance/intl_econ/env_econ, and their existing real children) across DEPR, UPSC CSE's
Economics Optional papers (previously zero topics), and UPSC IES's ge_01/ge_02/ge_03 papers
(additive alongside their existing fine-grained taxonomy, not replacing it). A new
`indian_economy_structural` topic is created deliberately separate from `indian_econ` —
`indian_econ`'s existing children (india_macro_data/rbi_monetary_data/schemes_indices) are
confirmed "current developments" flavored, not the deep structural/historical India content
eco_optional_2 and IES ge_04 need (exactly the depth-mismatch trap DECIDE-29 already taught).

PFRDA Research stream is deliberately NOT auto-linked to DSIM here despite strong syllabus-
name overlap — RESEARCH-11 found zero real PYQ evidence for PFRDA Research stream, so a hard
depth-equivalence claim would be unverified. Instead each PFRDA Research topic gets a `notes`
annotation pointing to its plausible DSIM correspondence, for a human to confirm once real
PFRDA Research content exists.

Run: .venv/bin/python scripts/migrate_009_register_rbi_depr_dsim.py
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "core.db"

DEPR_PAPERS = [
    ("phase1_p1", "Phase I, Paper 1 — Objective Type (Economics)"),
    ("phase1_p2", "Phase I, Paper 2 — Descriptive (English)"),
    ("phase2_p1", "Phase II, Paper 1 — Descriptive (Economics: Micro + Macro modules)"),
    ("phase2_p2", "Phase II, Paper 2 — Descriptive (Economics: Quant/Econometrics + Indian Economy Policy modules)"),
]

DSIM_PAPERS = [
    ("p1", "Paper I — Objective Type (Statistics)"),
    ("p2", "Paper II — Descriptive Type (Statistics)"),
    ("p3", "Paper III — English Descriptive"),
]

# (topic_id, name, parent_topic_id) — only genuinely NEW topics, real reused ones handled separately.
NEW_TOPICS = [
    ("depr_quant_methods_econ", "Quantitative Methods in Economics (Mathematical/Statistical Methods, Econometrics)", None),
    ("depr_english_descriptive", "RBI DEPR Phase I Paper II — English Descriptive Writing", None),
    ("distribution_theories", "Distribution Theories — Ricardo, Marx, Kalecki, Kaldor", "micro"),
    ("national_income_accounting", "National Income Accounting — Measurement Methods", "macro"),
    ("mathematical_methods_econ", "Mathematical Methods in Economics — Differentiation/Integration/Optimisation/Linear Algebra/LP", "depr_quant_methods_econ"),
    ("statistical_methods_econ", "Statistical Methods in Economics — Central Tendency/Dispersion/Probability/Time Series/Index Numbers", "depr_quant_methods_econ"),
    ("econometrics_advanced_econ", "Econometrics & Advanced Applications — Regression, Panel Data, Time Series Econometrics, Bayesian, AI/ML Basics", "depr_quant_methods_econ"),
    ("fiscal_policy_india", "Fiscal Policy in India — Evolution, Scope, Limitations, Current Trends", "indian_econ"),
    ("monetary_policy_india", "Monetary Policy in India — Evolution, RBI Functions, Monetary-Fiscal Coordination, Inflation Targeting", "indian_econ"),
    ("banking_financial_sector_india", "Banking & Financial Sector Development in India", "indian_econ"),
    ("inflation_trends_india", "Inflation in India — Trends & Drivers", "indian_econ"),
    ("external_sector_india", "External Sector Developments in India — Exchange Rate, External Debt, BoP", "indian_econ"),
    ("sectoral_developments_india", "Sectoral Developments in India — Agriculture, Industry, Services, Social Sector", "indian_econ"),
    ("indian_economy_structural", "Indian Economy — Structural/Historical (Planning History, Federal Finance, Reforms, Sector-wise Structural Analysis)", None),
    ("dsim_probability_sampling", "Theory of Probability, Probability Distributions & Sampling Theory (RBI DSIM)", None),
    ("dsim_linear_models_econ_stats", "Linear Models & Economic Statistics (RBI DSIM)", None),
    ("dsim_statistical_inference", "Statistical Inference — Estimation, Hypothesis Testing, Non-Parametric Tests (RBI DSIM)", None),
    ("dsim_stochastic_processes", "Stochastic Processes (RBI DSIM)", None),
    ("dsim_multivariate_analysis", "Multivariate Analysis (RBI DSIM)", None),
    ("dsim_econometrics_time_series", "Econometrics & Time Series (RBI DSIM)", None),
    ("dsim_optimization_stat_computing", "Optimization & Statistical Computing (RBI DSIM)", None),
    ("dsim_data_science_ai_ml", "Data Science, AI & ML Techniques (RBI DSIM)", None),
    ("dsim_database_dw_management", "Database & Data Warehouse Management (RBI DSIM)", None),
    ("dsim_english_descriptive", "RBI DSIM Paper III — English Descriptive", None),
]

# (exam_id, paper_id, topic_id, weight) — reuse of EXISTING canonical topics.
REUSE_LINKS = [
    # DEPR Phase I Paper 1 — 8 real objective-economics items, no stated numeric split -> flat.
    ("rbi_depr", "phase1_p1", "macro", 1.0),
    ("rbi_depr", "phase1_p1", "micro", 1.0),
    ("rbi_depr", "phase1_p1", "intl_econ", 1.0),
    ("rbi_depr", "phase1_p1", "growth", 1.0),
    ("rbi_depr", "phase1_p1", "pub_finance", 1.0),
    ("rbi_depr", "phase1_p1", "env_econ", 1.0),
    ("rbi_depr", "phase1_p1", "indian_econ", 1.0),
    ("rbi_depr", "phase1_p1", "depr_quant_methods_econ", 1.0),
    # DEPR Phase II Paper 1 — real "equal weightage" Micro/Macro modules.
    ("rbi_depr", "phase2_p1", "micro", 0.5),
    ("rbi_depr", "phase2_p1", "macro", 0.5),
    ("rbi_depr", "phase2_p1", "consumer_theory", 1.0),
    ("rbi_depr", "phase2_p1", "production_theory", 1.0),
    ("rbi_depr", "phase2_p1", "market_structures", 1.0),
    ("rbi_depr", "phase2_p1", "welfare_game", 1.0),
    ("rbi_depr", "phase2_p1", "distribution_theories", 1.0),
    ("rbi_depr", "phase2_p1", "money_banking", 1.0),
    ("rbi_depr", "phase2_p1", "qtm_monetary", 1.0),
    ("rbi_depr", "phase2_p1", "phillips_lucas", 1.0),
    ("rbi_depr", "phase2_p1", "is_lm", 1.0),
    ("rbi_depr", "phase2_p1", "national_income_accounting", 1.0),
    ("rbi_depr", "phase2_p1", "growth", 1.0),
    ("rbi_depr", "phase2_p1", "intl_econ", 1.0),
    ("rbi_depr", "phase2_p1", "pub_finance", 1.0),
    # DEPR Phase II Paper 2 — real "equal weightage" Quant/Econometrics + Indian Economy Policy.
    ("rbi_depr", "phase2_p2", "depr_quant_methods_econ", 0.5),
    ("rbi_depr", "phase2_p2", "mathematical_methods_econ", 1.0),
    ("rbi_depr", "phase2_p2", "statistical_methods_econ", 1.0),
    ("rbi_depr", "phase2_p2", "econometrics_advanced_econ", 1.0),
    ("rbi_depr", "phase2_p2", "indian_econ", 0.5),
    ("rbi_depr", "phase2_p2", "fiscal_policy_india", 1.0),
    ("rbi_depr", "phase2_p2", "monetary_policy_india", 1.0),
    ("rbi_depr", "phase2_p2", "banking_financial_sector_india", 1.0),
    ("rbi_depr", "phase2_p2", "inflation_trends_india", 1.0),
    ("rbi_depr", "phase2_p2", "external_sector_india", 1.0),
    ("rbi_depr", "phase2_p2", "sectoral_developments_india", 1.0),
    # DEPR Phase I Paper 2 (English) — DEPR-specific, not a broad reuse.
    ("rbi_depr", "phase1_p2", "depr_english_descriptive", 1.0),
    # DSIM Paper I & II share the same real 9-topic syllabus (PG-standard, no stated split).
    ("rbi_dsim", "p1", "dsim_probability_sampling", 1.0),
    ("rbi_dsim", "p1", "dsim_linear_models_econ_stats", 1.0),
    ("rbi_dsim", "p1", "dsim_statistical_inference", 1.0),
    ("rbi_dsim", "p1", "dsim_stochastic_processes", 1.0),
    ("rbi_dsim", "p1", "dsim_multivariate_analysis", 1.0),
    ("rbi_dsim", "p1", "dsim_econometrics_time_series", 1.0),
    ("rbi_dsim", "p1", "dsim_optimization_stat_computing", 1.0),
    ("rbi_dsim", "p1", "dsim_data_science_ai_ml", 1.0),
    ("rbi_dsim", "p1", "dsim_database_dw_management", 1.0),
    ("rbi_dsim", "p2", "dsim_probability_sampling", 1.0),
    ("rbi_dsim", "p2", "dsim_linear_models_econ_stats", 1.0),
    ("rbi_dsim", "p2", "dsim_statistical_inference", 1.0),
    ("rbi_dsim", "p2", "dsim_stochastic_processes", 1.0),
    ("rbi_dsim", "p2", "dsim_multivariate_analysis", 1.0),
    ("rbi_dsim", "p2", "dsim_econometrics_time_series", 1.0),
    ("rbi_dsim", "p2", "dsim_optimization_stat_computing", 1.0),
    ("rbi_dsim", "p2", "dsim_data_science_ai_ml", 1.0),
    ("rbi_dsim", "p2", "dsim_database_dw_management", 1.0),
    ("rbi_dsim", "p3", "dsim_english_descriptive", 1.0),
    # RESEARCH-11 cross-links: UPSC CSE Economics Optional (previously zero topics).
    ("upsc_cse", "eco_optional_1", "macro", 1.0),
    ("upsc_cse", "eco_optional_1", "micro", 1.0),
    ("upsc_cse", "eco_optional_1", "intl_econ", 1.0),
    ("upsc_cse", "eco_optional_1", "growth", 1.0),
    ("upsc_cse", "eco_optional_1", "pub_finance", 1.0),
    ("upsc_cse", "eco_optional_1", "env_econ", 1.0),
    ("upsc_cse", "eco_optional_2", "indian_economy_structural", 1.0),
    # RESEARCH-11 cross-links: IES, additive alongside its existing fine-grained taxonomy.
    ("upsc_ies", "ge_01", "micro", 1.0),
    ("upsc_ies", "ge_02", "macro", 1.0),
    ("upsc_ies", "ge_02", "growth", 1.0),
    ("upsc_ies", "ge_02", "intl_econ", 1.0),
    ("upsc_ies", "ge_03", "env_econ", 1.0),
    ("upsc_ies", "ge_04", "indian_economy_structural", 1.0),
]

# PFRDA Research topics -> plausible (unverified) DSIM correspondence, notes only, no exam_topics link.
PFRDA_RESEARCH_DSIM_NOTES = {
    "pfrda_probability_theory": "Plausible real correspondence: RBI DSIM's dsim_probability_sampling — NOT auto-linked (RESEARCH-11 found zero real PFRDA Research-stream PYQ evidence to confirm matching depth).",
    "pfrda_descriptive_statistics": "Plausible real correspondence: part of RBI DSIM's dsim_linear_models_econ_stats — NOT auto-linked (unverified PFRDA Research-stream depth, see RESEARCH-11).",
    "pfrda_probability_distributions": "Plausible real correspondence: RBI DSIM's dsim_probability_sampling — NOT auto-linked (unverified PFRDA Research-stream depth, see RESEARCH-11).",
    "pfrda_statistical_inference": "Plausible real correspondence: RBI DSIM's dsim_statistical_inference (exact name match) — NOT auto-linked (unverified PFRDA Research-stream depth, see RESEARCH-11).",
    "pfrda_sampling_techniques": "Plausible real correspondence: part of RBI DSIM's dsim_probability_sampling — NOT auto-linked (unverified PFRDA Research-stream depth, see RESEARCH-11).",
    "pfrda_hypothesis_testing": "Plausible real correspondence: part of RBI DSIM's dsim_statistical_inference — NOT auto-linked (unverified PFRDA Research-stream depth, see RESEARCH-11).",
    "pfrda_economic_statistics": "Plausible real correspondence: RBI DSIM's dsim_linear_models_econ_stats — NOT auto-linked (unverified PFRDA Research-stream depth, see RESEARCH-11).",
    "pfrda_time_series_analysis": "Plausible real correspondence: part of RBI DSIM's dsim_econometrics_time_series — NOT auto-linked (unverified PFRDA Research-stream depth, see RESEARCH-11).",
    "pfrda_operations_research": "Plausible real correspondence: part of RBI DSIM's dsim_optimization_stat_computing — NOT auto-linked (unverified PFRDA Research-stream depth, see RESEARCH-11).",
    "pfrda_statistical_quality_control": "No clean DSIM correspondence found — DSIM's syllabus has no explicit SQC item; likely PFRDA-specific.",
    "pfrda_statistical_computing": "Plausible real correspondence: part of RBI DSIM's dsim_optimization_stat_computing — NOT auto-linked (unverified PFRDA Research-stream depth, see RESEARCH-11).",
}


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")

    conn.executemany(
        "INSERT OR IGNORE INTO papers (exam_id, paper_id, name) VALUES ('rbi_depr', ?, ?)",
        DEPR_PAPERS,
    )
    conn.execute(
        "INSERT OR IGNORE INTO exams (exam_id, name, created_at, institution_id) VALUES (?, ?, ?, ?)",
        ("rbi_dsim", "RBI Officer Grade 'B' (DR) — DSIM Cadre",
         datetime.now(timezone.utc).isoformat(), "rbi"),
    )
    conn.executemany(
        "INSERT OR IGNORE INTO papers (exam_id, paper_id, name) VALUES ('rbi_dsim', ?, ?)",
        DSIM_PAPERS,
    )
    conn.executemany(
        "INSERT OR IGNORE INTO topics (topic_id, name, parent_topic_id) VALUES (?, ?, ?)",
        NEW_TOPICS,
    )
    conn.executemany(
        "INSERT OR IGNORE INTO exam_topics (exam_id, paper_id, topic_id, weight) VALUES (?, ?, ?, ?)",
        REUSE_LINKS,
    )
    conn.executemany(
        "UPDATE topics SET notes = ? WHERE topic_id = ?",
        [(note, topic_id) for topic_id, note in PFRDA_RESEARCH_DSIM_NOTES.items()],
    )
    conn.commit()

    n_exams = conn.execute("SELECT COUNT(*) FROM exams").fetchone()[0]
    n_depr = conn.execute(
        "SELECT COUNT(*) FROM exam_topics WHERE exam_id='rbi_depr'"
    ).fetchone()[0]
    n_dsim = conn.execute(
        "SELECT COUNT(*) FROM exam_topics WHERE exam_id='rbi_dsim'"
    ).fetchone()[0]
    n_eco_opt = conn.execute(
        "SELECT COUNT(*) FROM exam_topics WHERE exam_id='upsc_cse' AND paper_id LIKE '%eco_optional%'"
    ).fetchone()[0]
    n_ies_new = conn.execute(
        "SELECT COUNT(*) FROM exam_topics WHERE exam_id='upsc_ies' AND paper_id IN ('ge_01','ge_02','ge_03','ge_04') "
        "AND topic_id IN ('micro','macro','growth','intl_econ','env_econ','indian_economy_structural')"
    ).fetchone()[0]
    print(f"exams now registered: {n_exams}")
    print(f"rbi_depr exam_topics rows: {n_depr}")
    print(f"rbi_dsim exam_topics rows: {n_dsim}")
    print(f"upsc_cse eco_optional_1/2 exam_topics rows: {n_eco_opt}")
    print(f"upsc_ies cross-linked canonical rows: {n_ies_new}")
    conn.close()


if __name__ == "__main__":
    main()
