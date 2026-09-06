"""Embeds enriched chunks and writes them to LanceDB's `chunks` table (PLAN.md Phase 1,
docs/DATA_DICTIONARY.md). Embeds `context_prefix + content` together, not raw content alone
— that's the actual point of Contextual Retrieval (DECIDE-13): the blurb's context gets
folded into the vector, so a query can match a chunk even when the chunk text itself never
names the thing being asked about.
"""

import json
from pathlib import Path
from typing import Optional

import lancedb
import ollama
from lancedb.pydantic import LanceModel, Vector

from src.schema.models import ChunkMetadata

EMBED_MODEL = "nomic-embed-text"
EMBED_DIM = 768
LANCEDB_PATH = Path(__file__).parent.parent.parent / "data" / "lancedb"


class ChunkRecord(LanceModel):
    """LanceDB's `chunks` table schema — ChunkMetadata's fields plus the embedding vector.
    `tags` (DECIDE-09) is stored as a JSON string, not a native map, to sidestep pyarrow's
    map-type quirks for a field that's read back whole, never queried inside LanceDB itself
    (the `chunk_tags` EAV table in core.db is what SQL-filters on individual tag values).
    """

    chunk_id: str
    content: str
    context_prefix: str
    vector: Vector(EMBED_DIM)
    exam_id: str
    paper_id: Optional[str] = None
    topic_id: str
    content_type: str
    section_id: str
    source_doc: str
    page_number: int
    published_date: Optional[str] = None  # ISO date string
    source_type: str
    verified_by: Optional[str] = None
    reviewed_at: Optional[str] = None  # ISO datetime string
    is_current: bool = True
    superseded_by: Optional[str] = None
    tags: str = "{}"  # JSON-encoded dict[str, str]


def embed_text(text: str) -> list[float]:
    return ollama.embeddings(model=EMBED_MODEL, prompt=text)["embedding"]


def get_chunks_table(db: lancedb.DBConnection | None = None):
    db = db or lancedb.connect(LANCEDB_PATH)
    if "chunks" in db.table_names():
        return db.open_table("chunks")
    return db.create_table("chunks", schema=ChunkRecord)


def to_record(metadata: ChunkMetadata) -> dict:
    vector = embed_text(f"{metadata.context_prefix} {metadata.content}")
    return {
        "chunk_id": metadata.chunk_id,
        "content": metadata.content,
        "context_prefix": metadata.context_prefix,
        "vector": vector,
        "exam_id": metadata.exam_id,
        "paper_id": metadata.paper_id,
        "topic_id": metadata.topic_id,
        "content_type": metadata.content_type,
        "section_id": metadata.section_id,
        "source_doc": metadata.source_doc,
        "page_number": metadata.page_number,
        "published_date": metadata.published_date.isoformat() if metadata.published_date else None,
        "source_type": metadata.source_type,
        "verified_by": metadata.verified_by,
        "reviewed_at": metadata.reviewed_at.isoformat() if metadata.reviewed_at else None,
        "is_current": metadata.is_current,
        "superseded_by": metadata.superseded_by,
        "tags": json.dumps(metadata.tags),
    }


def write_chunk(metadata: ChunkMetadata, table=None) -> None:
    """Upsert by chunk_id (merge_insert) so re-running ingestion over the same document
    updates rather than duplicates — required for the incremental/resumable ingestion this
    feeds into (PLAN.md Phase 1's hash-based skip-list, same idea as ingestion_log.json)."""
    table = table if table is not None else get_chunks_table()
    (
        table.merge_insert("chunk_id")
        .when_matched_update_all()
        .when_not_matched_insert_all()
        .execute([to_record(metadata)])
    )
