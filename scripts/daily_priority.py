"""Daily study-priority scheduler.

Applies the `layered-coverage` skill's Q4 scheduling formula
(`priority_score = weight * (1 - coverage_depth)`) to real `exam_topics.weight` data in
`data/core.db`, so Rahul gets an actual ranked "study this today" list instead of manual
judgment.

**UPDATE (2026-09-16, DECIDE-34):** `coverage_depth` now reads real data. `scripts/quiz.py`
plus `migrate_011_user_attempts_coverage.py` added a real per-user attempt log
(`user_attempts`) and a computed `topic_coverage` table (exam_id, topic_id ->
attempts_count/accuracy/coverage_depth), populated by actually quizzing on real `pyq_bank`
questions. `fetch_coverage_depth()` below now looks up `topic_coverage` for the given
(exam_id, topic_id) and returns its real `coverage_depth` when a row exists. Most topics
still have no row — Rahul has only quizzed a handful so far — and per the layered-coverage
skill's anti-false-positive rule, "no row" still means untested, which still scores exactly
0.0 (max urgency), never a fabricated default. So today's output is a real mix: a few
topics with real accuracy-based coverage, most still ranked at max priority by weight alone.
This behaviour (some real coverage, most still 0.0) is expected and will keep shifting
as more quiz sessions are run — it is not a bug.

Usage:
    .venv/bin/python scripts/daily_priority.py [--exam_id pfrda_gradea] [--paper_id ID] [--top 15]

With no --paper_id, and --exam_id pfrda_gradea specifically, this runs once per real
paper_id registered under that exam (General stream, Research stream, and the two
streams-in-common papers) and prints/writes each as its own clearly-labeled table, so the
Research stream's flat-weight caveat sits right next to its output instead of being buried
in a combined list.
"""

from __future__ import annotations

import argparse
import sqlite3
import statistics
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "core.db"
DOCS_DIR = Path(__file__).parent.parent / "docs"

# Defensive floors (layered-coverage implementation checklist) — exam_topics.weight is
# `NOT NULL DEFAULT 1.0` in the live schema so these should never trigger on real data, but
# a NULL/zero weight must never divide-by-zero or silently vanish from the ranking.
DEFAULT_WEIGHT = 1.0
MIN_WEIGHT = 0.01

# Fallback for a topic with no topic_coverage row yet (untested). Per the layered-coverage
# skill's anti-false-positive rule, untested = 0.0 = max urgency, never a fabricated default.
COVERAGE_DEPTH = 0.0

COVERAGE_NOTE = (
    "coverage_depth is real where it exists: scripts/quiz.py logs attempts to user_attempts "
    "and recomputes topic_coverage (accuracy-based depth) after each session. A topic with "
    "no topic_coverage row has never been quizzed — it falls back to coverage_depth = 0.0, "
    "the layered-coverage skill's prescribed value for untested items (untested = max "
    "urgency, never a fabricated default), not a sign the signal is missing entirely. Most "
    "topics still have no row (only a handful have been quizzed so far) — expect a mix of "
    "real accuracy-driven ranking and weight-only ranking until more sessions are run."
)

RESEARCH_CAVEAT = (
    "CAVEAT (Research stream): every topic here carries a flat placeholder weight of 1.0 "
    "(DECIDE-30). Zero real PYQ content has been ingested for this stream — DECIDE-31's "
    "ingestion only covered the General stream — and per docs/research.md#research-11 "
    "(6 coaching sources checked, none cover it), likely never will from a coaching source. "
    "Ranking within this stream is currently meaningless: treat it as an unordered topic "
    "checklist, not a real priority order."
)


def fetch_coverage_depth(conn: sqlite3.Connection, exam_id: str, topic_id: str) -> float:
    """Real per-user coverage signal from topic_coverage — falls back to COVERAGE_DEPTH
    (0.0, untested) when no row exists for this (exam_id, topic_id). See module docstring."""
    row = conn.execute(
        "SELECT coverage_depth FROM topic_coverage WHERE exam_id = ? AND topic_id = ?",
        (exam_id, topic_id),
    ).fetchone()
    return row[0] if row is not None else COVERAGE_DEPTH


def get_scopes(conn: sqlite3.Connection, exam_id: str, paper_id: str | None) -> list[tuple[str, str]]:
    """Return [(paper_id, display_label), ...] to run separately.

    If paper_id is given explicitly, that's the only scope. Otherwise, iterate every real
    paper_id that actually has exam_topics rows for this exam (for pfrda_gradea that's all
    6 real papers — General/Research streams plus the 2 common Phase papers; for an exam
    with no `papers` rows at all it's just the '_all' sentinel).
    """
    if paper_id is not None:
        return [(paper_id, paper_display_name(conn, exam_id, paper_id))]

    rows = conn.execute(
        "SELECT DISTINCT paper_id FROM exam_topics WHERE exam_id = ? ORDER BY paper_id",
        (exam_id,),
    ).fetchall()
    return [(r[0], paper_display_name(conn, exam_id, r[0])) for r in rows]


def paper_display_name(conn: sqlite3.Connection, exam_id: str, paper_id: str) -> str:
    row = conn.execute(
        "SELECT name FROM papers WHERE exam_id = ? AND paper_id = ?", (exam_id, paper_id)
    ).fetchone()
    return row[0] if row else paper_id


def stream_label(paper_id: str) -> str:
    """Best-effort stream classification from paper_id, for clear table headers."""
    low = paper_id.lower()
    if "research" in low:
        return "Research stream"
    if "general" in low:
        return "General stream"
    return "Common (all streams)"


def fetch_items(conn: sqlite3.Connection, exam_id: str, paper_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT et.topic_id, t.name, t.parent_topic_id, et.weight
        FROM exam_topics et
        JOIN topics t ON t.topic_id = et.topic_id
        WHERE et.exam_id = ? AND et.paper_id = ?
        """,
        (exam_id, paper_id),
    ).fetchall()

    items = []
    for topic_id, name, parent_topic_id, weight in rows:
        w = weight if weight is not None else DEFAULT_WEIGHT
        w = max(w, MIN_WEIGHT)
        coverage_depth = fetch_coverage_depth(conn, exam_id, topic_id)
        items.append(
            {
                "topic_id": topic_id,
                "name": name,
                "parent_topic_id": parent_topic_id,
                "weight": w,
                "coverage_depth": coverage_depth,
                "priority_score": w * (1 - coverage_depth),
            }
        )
    return items


def compute_at_risk(items: list[dict]) -> list[dict]:
    """layered-coverage anti-false-positive rule: weight > median AND coverage < 50%.

    Most items still have coverage_depth == 0.0 (never quizzed), so this still mostly
    reduces to "weight above median" today — but a topic with real quiz history and
    accuracy < 50% now genuinely qualifies too, not just untested ones.
    """
    if not items:
        return []
    median_weight = statistics.median(item["weight"] for item in items)
    return [item for item in items if item["weight"] > median_weight and item["coverage_depth"] < 0.5]


def format_table(items: list[dict]) -> list[str]:
    lines = [
        "| Rank | topic_id | name | weight | priority_score |",
        "|---|---|---|---|---|",
    ]
    for rank, item in enumerate(items, start=1):
        lines.append(
            f"| {rank} | {item['topic_id']} | {item['name']} | {item['weight']:.4f} | "
            f"{item['priority_score']:.4f} |"
        )
    return lines


def print_table(items: list[dict]) -> None:
    header = f"{'Rank':<5} {'topic_id':<38} {'weight':>8} {'priority_score':>15}  name"
    print(header)
    print("-" * len(header))
    for rank, item in enumerate(items, start=1):
        print(
            f"{rank:<5} {item['topic_id']:<38} {item['weight']:>8.4f} "
            f"{item['priority_score']:>15.4f}  {item['name']}"
        )


def build_scope_report(
    exam_id: str, paper_id: str, label: str, paper_name: str, items: list[dict], top_n: int
) -> tuple[list[str], list[dict]]:
    """Compute + render one (exam_id, paper_id) scope. Returns (markdown_lines, ranked_top_n)."""
    ranked_all = sorted(items, key=lambda i: i["priority_score"], reverse=True)
    ranked_top = ranked_all[:top_n]
    at_risk = compute_at_risk(ranked_all)

    md = [f"## {label} — `{paper_id}` ({paper_name})", ""]
    if label == "Research stream":
        md += [f"> {RESEARCH_CAVEAT}", ""]
    uncovered = [i for i in ranked_all if i["coverage_depth"] == 0.0]
    md += [
        f"- Total items in scope: {len(ranked_all)}",
        f"- Uncovered items (coverage = 0, never quizzed): {len(uncovered)} of {len(ranked_all)}",
        f"- At-risk items (weight > median AND coverage < 50%): {len(at_risk)}",
        "",
        f"Showing top {min(top_n, len(ranked_all))} of {len(ranked_all)}:",
        "",
    ]
    md += format_table(ranked_top)
    md.append("")
    return md, ranked_top


def run(exam_id: str, paper_id_filter: str | None, top_n: int) -> None:
    if not DB_PATH.exists():
        print(f"ERROR: {DB_PATH} not found.", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")

    exam_row = conn.execute("SELECT name FROM exams WHERE exam_id = ?", (exam_id,)).fetchone()
    if exam_row is None:
        print(f"ERROR: exam_id '{exam_id}' not found in exams table.", file=sys.stderr)
        sys.exit(1)
    exam_name = exam_row[0]

    scopes = get_scopes(conn, exam_id, paper_id_filter)
    if not scopes:
        print(f"No exam_topics rows found for exam_id='{exam_id}'" +
              (f", paper_id='{paper_id_filter}'." if paper_id_filter else "."))
        conn.close()
        return

    print(f"Daily priority — {exam_name} ({exam_id})")
    print(COVERAGE_NOTE)
    print()

    md_lines = [
        f"# Daily priority — {exam_name} (`{exam_id}`)",
        "",
        f"> {COVERAGE_NOTE}",
        "",
    ]

    for pid, paper_name in scopes:
        label = stream_label(pid)
        items = fetch_items(conn, exam_id, pid)
        if not items:
            print(f"[{label}] {pid} ({paper_name}): no topics found, skipping.")
            continue

        print(f"=== {label} — {pid} ({paper_name}) ===")
        if label == "Research stream":
            print(RESEARCH_CAVEAT)
        ranked_all = sorted(items, key=lambda i: i["priority_score"], reverse=True)
        at_risk = compute_at_risk(ranked_all)
        uncovered = [i for i in ranked_all if i["coverage_depth"] == 0.0]
        print(f"Total items: {len(ranked_all)} | Uncovered (coverage=0, never quizzed): "
              f"{len(uncovered)} of {len(ranked_all)} "
              f"| At-risk (weight>median, coverage<50%): {len(at_risk)}")
        ranked_top = ranked_all[:top_n]
        print_table(ranked_top)
        print()

        scope_md, _ = build_scope_report(exam_id, pid, label, paper_name, items, top_n)
        md_lines += scope_md

    conn.close()

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DOCS_DIR / f"daily_priority_{exam_id}.md"
    out_path.write_text("\n".join(md_lines) + "\n")
    print(f"Written: {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank exam topics/subtopics by study priority.")
    parser.add_argument("--exam_id", default="pfrda_gradea")
    parser.add_argument("--paper_id", default=None)
    parser.add_argument("--top", type=int, default=15)
    args = parser.parse_args()
    run(args.exam_id, args.paper_id, args.top)


if __name__ == "__main__":
    main()
