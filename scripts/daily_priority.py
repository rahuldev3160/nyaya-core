"""Daily study-priority scheduler.

Applies the `layered-coverage` skill's Q4 scheduling formula
(`priority_score = weight * (1 - coverage_depth)`) to real `exam_topics.weight` data in
`data/core.db`, so Rahul gets an actual ranked "study this today" list instead of manual
judgment.

COVERAGE_DEPTH IS HARDCODED TO 0.0 FOR EVERY ITEM — read this before changing anything.
Verified directly against the live `core.db` schema (2026-09-16): the only tables are
`institutions`, `exams`, `papers`, `topics`, `exam_topics`, `content_types`, `sections`,
`pyq_bank`, `pyq_explanations`, `chunk_tags`. `pyq_bank` tracks question CONTENT and its own
verification status (verified/void/unverified) — it has no column for what a *user*
answered, so no per-user attempt/accuracy/coverage signal exists anywhere in this DB. That
tracking lives in the separate Recall/Scribe app databases, not here. Per the layered-
coverage skill's anti-false-positive rule, an untested item scores exactly 0 (max urgency),
never a fabricated default like 0.5 — so today, every item in this script ranks purely by
weight (priority_score == weight for all rows). This is documented behaviour, not a bug.
The day nyaya-core gains a real per-user attempt table, replace `COVERAGE_DEPTH` and the
`fetch_coverage_depth()` stub below with a real query — nothing else in this script assumes
coverage is always 0.

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

# See module docstring: no real per-user coverage/attempt signal exists in nyaya-core yet.
COVERAGE_DEPTH = 0.0

COVERAGE_NOTE = (
    "No real per-user coverage/attempt signal exists in nyaya-core yet (verified against "
    "core.db's live schema — no such table). Every item below is ranked at max priority by "
    "weight alone: coverage_depth = 0.0 for all items, which is the layered-coverage skill's "
    "prescribed value for untested items (untested = 0 = max urgency), not a bug or a filler "
    "default. Real per-user accuracy tracking lives in the separate Recall/Scribe app "
    "databases, not in nyaya-core."
)

RESEARCH_CAVEAT = (
    "CAVEAT (Research stream): every topic here carries a flat placeholder weight of 1.0 "
    "(DECIDE-30). Zero real PYQ content has been ingested for this stream — DECIDE-31's "
    "ingestion only covered the General stream — and per docs/research.md#research-11 "
    "(6 coaching sources checked, none cover it), likely never will from a coaching source. "
    "Ranking within this stream is currently meaningless: treat it as an unordered topic "
    "checklist, not a real priority order."
)


def fetch_coverage_depth(topic_id: str) -> float:
    """Stub for a real per-user coverage signal. Always 0.0 today — see module docstring."""
    return COVERAGE_DEPTH


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
        coverage_depth = fetch_coverage_depth(topic_id)
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

    Coverage is 0.0 for every item here, so this always reduces to "weight above median" —
    stated plainly in the report rather than presented as independent, higher-precision
    signal than it actually is.
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
    md += [
        f"- Total items in scope: {len(ranked_all)}",
        f"- Uncovered items (coverage = 0): {len(ranked_all)} (all of them — see coverage note below)",
        f"- At-risk items (weight > median AND coverage < 50%): {len(at_risk)} "
        f"{'— i.e. all above-median-weight items, since coverage is 0 everywhere' if at_risk else ''}",
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
        print(f"Total items: {len(ranked_all)} | Uncovered (coverage=0): {len(ranked_all)} "
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
