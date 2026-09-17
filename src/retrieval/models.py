"""Response shapes for nyaya-core's retrieval layer (PLAN.md Phase 2). Additive — does
not touch src/schema/models.py's ingestion contracts.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SearchHit(BaseModel):
    chunk_id: str
    content: str
    context_prefix: str
    exam_id: str
    paper_id: Optional[str] = None
    topic_id: str
    content_type: str
    section_id: str
    source_doc: str
    page_number: int
    source_type: str
    score: float  # fused+reranked relevance score (FlashRank cross-encoder), higher = better


class SearchResult(BaseModel):
    query: str
    hits: list[SearchHit]
    # True when nothing cleared the rerank score floor (DECIDE-10) — callers must treat
    # this as "no real grounding available," never silently generate from a weak/empty hit.
    insufficient_grounding: bool
