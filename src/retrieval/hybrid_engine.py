"""LocalHybridEngine — PLAN.md Phase 2's retrieval core.

Dense (LanceDB vector search) + BM25-equivalent (LanceDB native full-text search) fused
via Reciprocal Rank Fusion (k=60), then reranked by a FlashRank cross-encoder. Below
RERANK_SCORE_FLOOR, a query returns `insufficient_grounding=True` instead of a silent
weak result (DECIDE-10) — not hypothetical: nyaya-core's own `chunks` table has zero
PFRDA rows and only 125 thin EPFO rows today, so this path fires for real from day one.

Trust-weighting (PLAN.md Phase 2): `source_type='ai_generated'` chunks are excluded from
grounding by default — don't let AI output silently become "ground truth" for more
generation. `is_current=False` (superseded) chunks are always excluded (DECIDE-11).

Auto-merge (DECIDE-14): after rerank, if >=2 of the top hits share a `section_id`, the
full `sections.full_text` is substituted for those hits (deduped to one), trimmed back to
the individual chunks only if the merge would exceed the caller's token budget.
"""
from __future__ import annotations

import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Optional

from flashrank import Ranker, RerankRequest
from lancedb.index import FTS

from src.ingestion.embed import embed_text, get_chunks_table
from src.retrieval.models import SearchHit, SearchResult

DB_PATH = Path(__file__).parent.parent.parent / "data" / "core.db"
FLASHRANK_CACHE_DIR = Path(__file__).parent.parent.parent / "data" / ".flashrank_cache"

RRF_K = 60
DENSE_CANDIDATES = 25
FTS_CANDIDATES = 25
RERANK_SCORE_FLOOR = 0.10  # FlashRank cross-encoder score is roughly 0-1; below = noise
DEFAULT_EXCLUDED_SOURCE_TYPES: tuple[str, ...] = ("ai_generated",)

# exam_id/paper_id/topic_id/source_type are interpolated into a LanceDB SQL filter string
# (lancedb's `.where()` takes a raw predicate, not parameter binding) — this is a
# local-only, single-user admin API, but every value is validated against this pattern
# first as a defensive floor against injection via a malformed caller.
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")

_ranker: Optional[Ranker] = None


def get_ranker() -> Ranker:
    """Lazily instantiate the shared FlashRank cross-encoder (downloads once, ~3MB, then
    cached under data/.flashrank_cache — never re-fetched after)."""
    global _ranker
    if _ranker is None:
        _ranker = Ranker(cache_dir=str(FLASHRANK_CACHE_DIR))
    return _ranker


def _validate_id(value: Optional[str], field: str) -> None:
    if value is not None and not _SAFE_ID.match(value):
        raise ValueError(f"invalid {field}: {value!r}")


def ensure_fts_index(table) -> None:
    """LanceDB's FTS index doesn't exist until built once (confirmed empty via
    list_indices() on the live table) — lazily create it on the `content` column."""
    existing = table.list_indices()
    if any("content" in idx.columns for idx in existing):
        return
    table.create_index("content", config=FTS())


def _build_filter(
    exam_id: str,
    paper_id: Optional[str],
    topic_id: Optional[str],
    exclude_source_types: tuple[str, ...],
) -> str:
    _validate_id(exam_id, "exam_id")
    _validate_id(paper_id, "paper_id")
    _validate_id(topic_id, "topic_id")
    for st in exclude_source_types:
        _validate_id(st, "source_type")

    clauses = [f"exam_id = '{exam_id}'", "is_current = true"]
    if paper_id:
        clauses.append(f"paper_id = '{paper_id}'")
    if topic_id:
        clauses.append(f"topic_id = '{topic_id}'")
    for st in exclude_source_types:
        clauses.append(f"source_type != '{st}'")
    return " AND ".join(clauses)


def dense_search(table, query_text: str, filter_sql: str, k: int) -> list[dict]:
    vector = embed_text(query_text)
    return (
        table.search(vector, vector_column_name="vector")
        .where(filter_sql, prefilter=True)
        .limit(k)
        .to_list()
    )


def fts_search(table, query_text: str, filter_sql: str, k: int) -> list[dict]:
    ensure_fts_index(table)
    return (
        table.search(query_text, query_type="fts")
        .where(filter_sql, prefilter=True)
        .limit(k)
        .to_list()
    )


def reciprocal_rank_fusion(*ranked_lists: list[dict], k: int = RRF_K) -> dict[str, float]:
    """score(d) = sum over lists containing d of 1/(k + rank); a chunk absent from a list
    contributes 0 from that list. Standard RRF formula, not per-list-normalized."""
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, row in enumerate(ranked, start=1):
            scores[row["chunk_id"]] = scores.get(row["chunk_id"], 0.0) + 1.0 / (k + rank)
    return scores


def rerank(query_text: str, candidates: dict[str, dict]) -> list[dict]:
    """FlashRank cross-encoder rerank over RRF's fused candidate set."""
    if not candidates:
        return []
    passages = [{"id": cid, "text": row["content"]} for cid, row in candidates.items()]
    ranked = get_ranker().rerank(RerankRequest(query=query_text, passages=passages))
    out = []
    for p in ranked:
        row = dict(candidates[p["id"]])
        row["_rerank_score"] = float(p["score"])
        out.append(row)
    return out


def auto_merge(hits: list[dict], conn: sqlite3.Connection, token_budget: int) -> list[dict]:
    """DECIDE-14: if >=2 of the top hits share a section_id, substitute sections.full_text
    for those hits (deduped to one merged hit per section), unless the merge alone would
    exceed the caller's token budget — in which case those hits are left as individual
    chunks rather than silently dropped."""
    section_counts = Counter(h["section_id"] for h in hits if h.get("section_id"))
    merge_targets = {sid for sid, count in section_counts.items() if count >= 2}
    if not merge_targets:
        return hits

    merged: list[dict] = []
    seen_sections: set[str] = set()
    for h in hits:
        sid = h.get("section_id")
        if sid not in merge_targets:
            merged.append(h)
            continue
        if sid in seen_sections:
            continue  # this section's merged hit was already emitted
        row = conn.execute("SELECT full_text FROM sections WHERE section_id = ?", (sid,)).fetchone()
        if row is None:
            merged.append(h)
            continue
        full_text = row[0]
        if len(full_text) // 4 > token_budget:  # rough token estimate; never split content mid-chunk
            merged.append(h)
            continue
        seen_sections.add(sid)
        merged_hit = dict(h)
        merged_hit["content"] = full_text
        merged.append(merged_hit)
    return merged


def search(
    query_text: str,
    exam_id: str,
    paper_id: Optional[str] = None,
    topic_id: Optional[str] = None,
    k: int = 8,
    token_budget: int = 4000,
    exclude_source_types: tuple[str, ...] = DEFAULT_EXCLUDED_SOURCE_TYPES,
    table=None,
    conn: Optional[sqlite3.Connection] = None,
) -> SearchResult:
    """Caller-supplied k/token_budget (DECIDE-08) — batch callers request a generous
    budget, interactive callers a small one. Never truncates a chunk mid-content to fit;
    drops whole lower-ranked chunks instead."""
    table = table if table is not None else get_chunks_table()
    own_conn = conn is None
    conn = conn if conn is not None else sqlite3.connect(DB_PATH)

    try:
        filter_sql = _build_filter(exam_id, paper_id, topic_id, exclude_source_types)
        dense_hits = dense_search(table, query_text, filter_sql, DENSE_CANDIDATES)
        fts_hits = fts_search(table, query_text, filter_sql, FTS_CANDIDATES)

        by_id = {r["chunk_id"]: r for r in dense_hits}
        by_id.update({r["chunk_id"]: r for r in fts_hits})
        if not by_id:
            return SearchResult(query=query_text, hits=[], insufficient_grounding=True)

        rrf_scores = reciprocal_rank_fusion(dense_hits, fts_hits)
        rrf_ranked_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)
        rrf_ranked_ids = rrf_ranked_ids[: max(DENSE_CANDIDATES, FTS_CANDIDATES)]
        reranked = rerank(query_text, {cid: by_id[cid] for cid in rrf_ranked_ids})

        cleared = [r for r in reranked if r["_rerank_score"] >= RERANK_SCORE_FLOOR][:k]
        if not cleared:
            return SearchResult(query=query_text, hits=[], insufficient_grounding=True)

        merged = auto_merge(cleared, conn, token_budget)

        hits = [
            SearchHit(
                chunk_id=r["chunk_id"],
                content=r["content"],
                context_prefix=r["context_prefix"],
                exam_id=r["exam_id"],
                paper_id=r.get("paper_id"),
                topic_id=r["topic_id"],
                content_type=r["content_type"],
                section_id=r["section_id"],
                source_doc=r["source_doc"],
                page_number=r["page_number"],
                source_type=r["source_type"],
                score=r["_rerank_score"],
            )
            for r in merged
        ]
        return SearchResult(query=query_text, hits=hits, insufficient_grounding=False)
    finally:
        if own_conn:
            conn.close()
