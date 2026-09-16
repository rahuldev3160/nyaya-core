"""Migration (DECIDE-33, see docs/decisions.md): resolves RISK-08 — additively cross-links
PFRDA's `pfrda_budget_economic_survey` topic (General stream, phase1_p2_general +
phase2_p2_general) to the canonical `indian_econ` topic already shared by RBI DEPR/DSIM,
UPSC CSE Eco-Optional, and UPSC IES (DECIDE-32). `pfrda_budget_economic_survey` itself is
kept, not replaced — this only adds the coarser canonical link alongside it, matching
DECIDE-32's IES precedent (additive, not destructive).

Depth/scope comparison (DECIDE-29's method): DECIDE-30 rejected a broad PFRDA-General-
Economics link to canonical Macro/Micro because PFRDA General's economics is genuinely
UG-101 level, below the postgrad depth `indian_econ`'s theory topics assume. That concern
doesn't transfer here — Union Budget & Economic Survey are annual primary-source government
documents, not theory of varying depth; every candidate across every exam studies the same
actual Budget/Survey each year. `indian_econ`'s existing children (india_macro_data: GDP/CPI/
fiscal-deficit/CAD; schemes_indices: PMJDY/MUDRA/PSL/etc; DECIDE-32's fiscal_policy_india,
sectoral_developments_india) are exactly the content Budget/Economic-Survey source documents
report — a genuine scope match, not a depth-mismatch link.

Real-frequency caveat (GL-07 in ~/.claude/GLOBAL_LEARNINGS.md): PFRDA's 3 real recalled
paper-books show zero occurrences of this topic (DECIDE-31) — but that dataset is
candidate-recall, not official, and 3 years isn't exhaustive. Zero-in-recall is weak/
incomplete signal, not confirmed absence. `pfrda_budget_economic_survey`'s weight stays the
DECIDE-30 flat 1.0 placeholder — this migration does NOT claim a real frequency, only that
the topic is genuinely in scope and semantically matches `indian_econ`.

Run: .venv/bin/python scripts/migrate_010_resolve_risk08_budget_ecosurvey.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "core.db"

# Additive canonical cross-link — alongside, not replacing, pfrda_budget_economic_survey.
NEW_LINKS = [
    ("pfrda_gradea", "phase1_p2_general", "indian_econ", 1.0),
    ("pfrda_gradea", "phase2_p2_general", "indian_econ", 1.0),
]

TOPIC_NOTE = (
    "Cross-linked to canonical `indian_econ` (DECIDE-33, resolves RISK-08) — Union Budget & "
    "Economic Survey are current-developments primary-source documents, genuine scope match "
    "to indian_econ's children (india_macro_data/schemes_indices/fiscal_policy_india/"
    "sectoral_developments_india), not the UG/PG theory-depth mismatch that blocked DECIDE-30's "
    "broader Economics link. Real PFRDA PYQ frequency for this topic remains unconfirmed (0/3 "
    "recall-based paper-books, small non-exhaustive sample) — weight stays an honest 1.0 "
    "placeholder, not asserted as confirmed-zero. See GL-07 in ~/.claude/GLOBAL_LEARNINGS.md."
)


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")

    conn.executemany(
        "INSERT OR IGNORE INTO exam_topics (exam_id, paper_id, topic_id, weight) "
        "VALUES (?, ?, ?, ?)",
        NEW_LINKS,
    )
    conn.execute(
        "UPDATE topics SET notes = ? WHERE topic_id = 'pfrda_budget_economic_survey'",
        (TOPIC_NOTE,),
    )
    conn.commit()

    n_links = conn.execute(
        "SELECT COUNT(*) FROM exam_topics WHERE exam_id='pfrda_gradea' AND topic_id='indian_econ'"
    ).fetchone()[0]
    note = conn.execute(
        "SELECT notes FROM topics WHERE topic_id='pfrda_budget_economic_survey'"
    ).fetchone()[0]
    print(f"pfrda_gradea -> indian_econ links: {n_links}")
    print(f"pfrda_budget_economic_survey note set: {bool(note)}")
    conn.close()


if __name__ == "__main__":
    main()
