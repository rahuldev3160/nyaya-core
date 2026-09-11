"""One-time migration (DECIDE-29): replaces upsc_epfo_apfc_eo_ao's reused UPSC-Prelims-style
topics with a fresh, EPFO-specific taxonomy grounded in the real official syllabus.

Real source: UPSC EPFO 2026 notification, Appendix-I ("Scheme, Syllabus, Weightage") —
`~/Desktop/opportunities/govt notifications/epfo 2026 notification.pdf`, page 22. The
syllabus broadly comprises 9 real subjects:
  i. General English
  ii. Indian Culture, Heritage and Freedom Movements
  iii. Developmental Issues and Present Trends in Indian Economy
  iv. Governance and Constitution of India
  v. General Science and Basic Knowledge of Computer Applications
  vi. Elementary Mathematics, Statistics and General Mental Ability
  vii. Industrial Relations, Labour Codes and Social Security in India
  viii. Principles of Accountancy, Auditing and Insurance
  ix. Current Events of National and International Importance

Rahul's real-content investigation found 6 of the exam's 25 seeded topics were actually the
SAME shared canonical rows reused by upsc_cse/State PCS (`polity`, `economy`,
`current_affairs`, `history_amac`, `modern_history`, `reading_comprehension` — the last even
parented under `comprehension` -> `csat`, a UPSC-CSE-only concept EPFO doesn't have at all).
Rahul's explicit instruction: EPFO's actual coverage/depth for these subjects is not the
same as UPSC Prelims' — curate fresh, EPFO-scoped topics instead of reusing the shared ones.
Subject vi (quant/mental ability) was entirely missing (RISK-05) — real content from the
already-ingested 2016/2023 papers couldn't extract because of this.

Also recomputes every `exam_topics.weight` for this exam from real observed `pyq_bank`
frequency across the 5 now-ingested years (546 real questions) — resolves RISK-04's
single-year-seed weakness in the same pass.

Run: .venv/bin/python scripts/migrate_007_epfo_fresh_taxonomy.py
"""
import sqlite3
from pathlib import Path

import lancedb

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "core.db"
LANCEDB_PATH = Path(__file__).resolve().parent.parent / "data" / "lancedb"
EXAM_ID = "upsc_epfo_apfc_eo_ao"

# (new_topic_id, name, parent_topic_id, old_topic_id_being_replaced_for_this_exam)
NEW_TOPICS = [
    ("epfo_culture_heritage_freedom", "Indian Culture, Heritage and Freedom Movements", None, None),
    ("epfo_ancient_medieval_culture", "Ancient & Medieval History, Art & Culture (EPFO)",
     "epfo_culture_heritage_freedom", "history_amac"),
    ("epfo_modern_freedom_struggle", "Modern History & Freedom Struggle (EPFO)",
     "epfo_culture_heritage_freedom", "modern_history"),
    ("epfo_economy_dev_issues", "Developmental Issues and Present Trends in Indian Economy",
     None, "economy"),
    ("epfo_governance_constitution", "Governance and Constitution of India", None, "polity"),
    ("epfo_quant_stats_mental_ability",
     "Elementary Mathematics, Statistics and General Mental Ability", None, None),
    ("epfo_current_events", "Current Events of National and International Importance",
     None, "current_affairs"),
    ("epfo_reading_comprehension", "Reading Comprehension Passages (EPFO)",
     "general_english", "reading_comprehension"),
]

# exam_topics rows for these topic_ids get deleted for this exam (old shared rows the
# canonical topic itself is untouched — other exams keep using it fine).
OLD_TOPIC_IDS_TO_UNLINK = [
    "csat", "current_affairs", "economy", "history_amac", "modern_history",
    "reading_comprehension", "polity",
]


def _already_migrated(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM topics WHERE topic_id = 'epfo_quant_stats_mental_ability'"
    ).fetchone()
    return row is not None


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    if _already_migrated(conn):
        print("Already migrated — nothing to do.")
        conn.close()
        return

    lance_db = lancedb.connect(LANCEDB_PATH)
    chunks_tbl = lance_db.open_table("chunks")

    # 1. Create the new topic rows.
    for topic_id, name, parent, _old in NEW_TOPICS:
        conn.execute(
            "INSERT OR IGNORE INTO topics (topic_id, name, parent_topic_id) VALUES (?, ?, ?)",
            (topic_id, name, parent),
        )
    print(f"Created {len(NEW_TOPICS)} new EPFO-specific topics.")

    # 2. Retag pyq_bank and LanceDB chunks from old shared topic_id -> new EPFO-specific one.
    for topic_id, _name, _parent, old_id in NEW_TOPICS:
        if old_id is None:
            continue
        n_pyq = conn.execute(
            "UPDATE pyq_bank SET topic_id = ? WHERE exam_id = ? AND topic_id = ?",
            (topic_id, EXAM_ID, old_id),
        ).rowcount
        chunks_tbl.update(where=f"exam_id = '{EXAM_ID}' AND topic_id = '{old_id}'",
                           values={"topic_id": topic_id})
        n_chunks = chunks_tbl.count_rows(f"exam_id = '{EXAM_ID}' AND topic_id = '{topic_id}'")
        print(f"  {old_id} -> {topic_id}: {n_pyq} pyq_bank row(s) retagged, "
              f"chunks table now has {n_chunks} row(s) at this new topic_id")

    # 3. Link the new topics to this exam (exam-wide, real syllabus applies across both
    #    papers) and unlink the old shared ones.
    conn.executemany(
        "INSERT OR IGNORE INTO exam_topics (exam_id, paper_id, topic_id, weight, is_core) "
        "VALUES (?, '_all', ?, 1.0, 1)",
        [(EXAM_ID, topic_id) for topic_id, *_ in NEW_TOPICS],
    )
    placeholders = ",".join("?" * len(OLD_TOPIC_IDS_TO_UNLINK))
    unlinked = conn.execute(
        f"DELETE FROM exam_topics WHERE exam_id = ? AND topic_id IN ({placeholders})",
        [EXAM_ID, *OLD_TOPIC_IDS_TO_UNLINK],
    ).rowcount
    print(f"Unlinked {unlinked} old shared-topic exam_topics row(s) from {EXAM_ID}.")

    conn.commit()

    # 4. Recompute every exam_topics.weight for this exam from real observed frequency
    #    across all 5 ingested years (RISK-04's payoff — no longer single-year-seeded).
    freq = conn.execute(
        "SELECT topic_id, COUNT(*) FROM pyq_bank WHERE exam_id = ? GROUP BY topic_id",
        (EXAM_ID,),
    ).fetchall()
    total = sum(c for _, c in freq)
    for topic_id, count in freq:
        weight = round(100.0 * count / total, 2)
        conn.execute(
            "UPDATE exam_topics SET weight = ? WHERE exam_id = ? AND paper_id = '_all' AND topic_id = ?",
            (weight, EXAM_ID, topic_id),
        )
    conn.commit()
    print(f"Recomputed weight for {len(freq)} topics from {total} real observed questions "
          f"across all 5 ingested years (RISK-04).")

    conn.close()


if __name__ == "__main__":
    main()
