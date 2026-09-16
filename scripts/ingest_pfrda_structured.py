"""One-time loader for the 3 real PFRDA Grade A recollected paper-books (2021/2022/2025),
following DECIDE-31 (see docs/decisions.md): these are coaching-site "recollected question"
compilations, not official released papers, so the goal is coverage intelligence (which
topics/subtopics are tested, how deep, what style) rather than a flawless practice-quiz
answer key. Every correct_option/status value was already resolved by a prior verification
pass (cross-source corroboration + fact-checking) and structured into
data/raw_ingest_staging/pfrda/{2021,2022,2025}_structured.json — this script does a pure
mechanical load, zero LLM involvement, consistent with DECIDE-26/27's "never let an LLM
determine correct_option" rule.

Two mechanical fixups applied here (not present in the structured JSON, which two
independent structuring agents produced with a naming drift):
- paper_id normalization: the 2022/2025 files used "phase1_p2"/"phase2_p2" instead of the
  registered "phase1_p2_general"/"phase2_p2_general" paper_ids.
- Phase 1 Paper 1 subtopic remap: the structuring agents' `proposed_subtopic_label` free-text
  strings are mapped here to the canonical subtopic taxonomy seeded from
  data/syllabi/pfrda_gradea_phase1p1_subtopics.json (consolidated from both years' real
  proposed labels).

Weight recompute (resolves RISK-07): exam_topics.weight for every PFRDA topic/subtopic that
received real data is recomputed as a recency-decayed real frequency count (per the
layered-coverage skill's Q2 formula: weight = sum of 0.9^years_ago over each real observed
occurrence), not a flat placeholder. Subject-level (parent) weight = decayed count of all
real questions under that subject, itself + every child subtopic (a rollup, not summed from
children's own stored values). Topics with zero real data keep their existing 1.0 placeholder
untouched, honestly reflecting that no real frequency signal exists yet for them.

Run: .venv/bin/python scripts/ingest_pfrda_structured.py
"""
import json
import re
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "core.db"
STAGING = Path(__file__).parent.parent / "data" / "raw_ingest_staging" / "pfrda"
EXAM_ID = "pfrda_gradea"
CURRENT_YEAR = 2026

PAPER_ID_FIX = {
    "phase1_p2": "phase1_p2_general",
    "phase2_p2": "phase2_p2_general",
    "phase1_p1": "phase1_p1",
    "phase2_p1": "phase2_p1",
}

# Ordered (more specific phrase first) keyword -> canonical Phase1-P1 subtopic_id.
APTITUDE_LABEL_RULES = [
    ("boat", "pfrda_quant_boats_streams"),
    ("data interpretation", "pfrda_quant_data_interpretation"),
    ("linear equation", "pfrda_quant_linear_equations"),
    ("mixture", "pfrda_quant_mixtures_alligation"),
    ("alligation", "pfrda_quant_mixtures_alligation"),
    ("number series", "pfrda_quant_number_series"),
    ("partnership", "pfrda_quant_partnership"),
    ("quadratic", "pfrda_quant_quadratic_equations"),
    ("ratio", "pfrda_quant_ratio_proportion"),
    ("time & work", "pfrda_quant_time_work"),
    ("time and work", "pfrda_quant_time_work"),
    ("speed", "pfrda_quant_time_speed_distance"),
    ("problems on ages", "pfrda_quant_ages"),
    ("ages", "pfrda_quant_ages"),
    ("compound interest", "pfrda_quant_si_ci"),
    ("simple & compound", "pfrda_quant_si_ci"),
    ("mensuration", "pfrda_quant_mensuration"),
    ("average", "pfrda_quant_averages"),
    ("coding", "pfrda_reasoning_coding_decoding"),
    ("input-output", "pfrda_reasoning_coding_decoding"),
    ("input output", "pfrda_reasoning_coding_decoding"),
    ("symbol arrangement", "pfrda_reasoning_arrangement"),
    ("scheduling", "pfrda_reasoning_puzzle_scheduling"),
    ("seating", "pfrda_reasoning_puzzle_seating"),
    ("floor puzzle", "pfrda_reasoning_puzzle_seating"),
    ("matching", "pfrda_reasoning_puzzle_matching"),
    ("statement & assumption", "pfrda_reasoning_statement_assumption"),
    ("statement and assumption", "pfrda_reasoning_statement_assumption"),
    ("syllogism", "pfrda_reasoning_syllogism"),
    ("cause and effect", "pfrda_reasoning_cause_effect"),
    ("cause & effect", "pfrda_reasoning_cause_effect"),
    ("statement & argument", "pfrda_reasoning_statement_argument"),
    ("critical reasoning", "pfrda_reasoning_statement_argument"),
    ("cloze", "pfrda_eng_cloze_test"),
    ("error spotting", "pfrda_eng_error_spotting"),
    ("para jumble", "pfrda_eng_para_jumble"),
    ("para-jumble", "pfrda_eng_para_jumble"),
    ("sentence rearrangement", "pfrda_eng_para_jumble"),
    ("reading comprehension", "pfrda_eng_reading_comprehension"),
    ("fill in the blank", "pfrda_eng_fill_blanks"),
    ("word/phrase interchange", "pfrda_eng_word_interchange"),
    ("word / phrase interchange", "pfrda_eng_word_interchange"),
    ("synonym", "pfrda_eng_synonyms_vocab"),
    ("word usage", "pfrda_eng_synonyms_vocab"),
    ("vocabulary", "pfrda_eng_synonyms_vocab"),
    ("regulatory bodies", "pfrda_ga_regulatory_bodies"),
    ("institution", "pfrda_ga_regulatory_bodies"),
    ("banking", "pfrda_ga_banking_finance_current"),
    ("finance current", "pfrda_ga_banking_finance_current"),
    ("abbreviation", "pfrda_ga_banking_finance_current"),
    ("digital payment", "pfrda_ga_banking_finance_current"),
    ("fintech", "pfrda_ga_banking_finance_current"),
    ("economy", "pfrda_ga_economy_current"),
    ("inflation", "pfrda_ga_economy_current"),
    ("taxation", "pfrda_ga_economy_current"),
    ("government scheme", "pfrda_ga_govt_schemes"),
    ("government polic", "pfrda_ga_govt_schemes"),
    ("report", "pfrda_ga_reports_indices"),
    ("indices", "pfrda_ga_reports_indices"),
    ("index", "pfrda_ga_reports_indices"),
    ("sports", "pfrda_ga_sports_awards"),
    ("award", "pfrda_ga_sports_awards"),
    ("brand ambassador", "pfrda_ga_sports_awards"),
    ("appointment", "pfrda_ga_sports_awards"),
    ("defence", "pfrda_ga_defence"),
    ("static gk", "pfrda_ga_static_gk"),
    ("books & authors", "pfrda_ga_static_gk"),
    ("important day", "pfrda_ga_static_gk"),
    ("corporate", "pfrda_ga_corporate_industry"),
    ("industry", "pfrda_ga_corporate_industry"),
    ("international organi", "pfrda_ga_international_orgs"),
    ("committee", "pfrda_ga_international_orgs"),
    ("environment", "pfrda_ga_environment"),
    ("global agreement", "pfrda_ga_environment"),
    ("science", "pfrda_ga_science_health"),
    ("health", "pfrda_ga_science_health"),
]


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def map_aptitude_label(label: str, fallback_parent: str) -> tuple[str, bool]:
    norm = label.lower()
    for keyword, topic_id in APTITUDE_LABEL_RULES:
        if keyword in norm:
            return topic_id, True
    return fallback_parent, False


def load_structured(year: int) -> dict:
    path = STAGING / f"{year}_structured.json"
    return json.loads(path.read_text())


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")

    valid_topics = {row[0] for row in conn.execute("SELECT topic_id FROM topics")}
    valid_papers = {row[0] for row in conn.execute(
        "SELECT paper_id FROM papers WHERE exam_id = ?", (EXAM_ID,)
    )}

    rows = []
    unmapped_labels: set[str] = set()
    counts = {"mcq": 0, "descriptive": 0, "skipped_bad_paper": 0, "skipped_bad_topic": 0}

    for year in (2021, 2022, 2025):
        data = load_structured(year)
        source_file = data["source_file"]
        for q in data["questions"]:
            paper_id = PAPER_ID_FIX.get(q["paper_id"], q["paper_id"])
            if paper_id not in valid_papers:
                counts["skipped_bad_paper"] += 1
                print(f"SKIP (bad paper_id {q['paper_id']!r}): {year} {q.get('question_number')}")
                continue

            topic_id = q["topic_id"]
            if paper_id == "phase1_p1" and q.get("proposed_subtopic_label"):
                topic_id, matched = map_aptitude_label(q["proposed_subtopic_label"], q["subject_topic_id"])
                if not matched:
                    unmapped_labels.add(q["proposed_subtopic_label"])

            if topic_id not in valid_topics:
                counts["skipped_bad_topic"] += 1
                print(f"SKIP (bad topic_id {topic_id!r}): {year} {q.get('question_number')}")
                continue

            subject_slug = slugify(q["subject_topic_id"].replace("pfrda_", ""))
            question_id = f"pfrda_{year}_{paper_id}_{subject_slug}_{q['question_number']}"

            options_json = json.dumps(q["options"]) if q.get("options") else None
            rows.append((
                question_id, EXAM_ID, paper_id, topic_id, q["question_format"],
                year, q["question_text"], options_json, q.get("correct_option"),
                None, None, "coaching_derived", None, None, None,
                q.get("question_number"), q.get("status", "unverified"),
                source_file, None,
            ))
            counts[q["question_format"] if q["question_format"] == "descriptive" else "mcq"] += 1

    if unmapped_labels:
        print(f"\nWARNING: {len(unmapped_labels)} aptitude labels matched no keyword rule, "
              f"fell back to parent subject topic_id: {sorted(unmapped_labels)}\n")

    conn.executemany(
        """INSERT OR IGNORE INTO pyq_bank
           (question_id, exam_id, paper_id, topic_id, question_format, year, question_text,
            options, correct_option, marks, word_limit, source_type, verified_by,
            reviewed_at, statements, question_number, status, source_file, answer_key_file)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    conn.commit()

    inserted = conn.execute(
        "SELECT COUNT(*) FROM pyq_bank WHERE exam_id = ? AND source_type = 'coaching_derived'",
        (EXAM_ID,),
    ).fetchone()[0]
    print(f"\npyq_bank rows now present for {EXAM_ID} (coaching_derived): {inserted}")
    print(f"Attempted: {counts['mcq']} MCQ + {counts['descriptive']} descriptive "
          f"({counts['skipped_bad_paper']} skipped bad-paper, {counts['skipped_bad_topic']} skipped bad-topic)")

    # --- Recompute exam_topics.weight from real observed frequency (RISK-07) ---
    decay_rows = conn.execute(
        """SELECT topic_id, year FROM pyq_bank
           WHERE exam_id = ? AND source_type = 'coaching_derived' AND question_format = 'mcq'""",
        (EXAM_ID,),
    ).fetchall()
    parent_of = dict(conn.execute("SELECT topic_id, parent_topic_id FROM topics"))

    weight: dict[str, float] = {}
    for topic_id, year in decay_rows:
        decay = 0.9 ** (CURRENT_YEAR - year)
        weight[topic_id] = weight.get(topic_id, 0.0) + decay
        parent = parent_of.get(topic_id)
        if parent:
            weight[parent] = weight.get(parent, 0.0) + decay

    updated = 0
    for paper_id in ("phase1_p1", "phase1_p2_general", "phase2_p2_general"):
        for topic_id, w in weight.items():
            cur = conn.execute(
                "SELECT 1 FROM exam_topics WHERE exam_id=? AND paper_id=? AND topic_id=?",
                (EXAM_ID, paper_id, topic_id),
            ).fetchone()
            if cur:
                conn.execute(
                    "UPDATE exam_topics SET weight=? WHERE exam_id=? AND paper_id=? AND topic_id=?",
                    (round(w, 4), EXAM_ID, paper_id, topic_id),
                )
                updated += 1
    conn.commit()
    print(f"exam_topics.weight updated for {updated} (paper_id, topic_id) rows with real data.")
    conn.close()


if __name__ == "__main__":
    main()
