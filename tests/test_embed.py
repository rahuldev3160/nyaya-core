"""Sanity test for src/ingestion/embed.py against a real local Ollama instance and a
throwaway LanceDB table (not the project's real data/lancedb/) — no Anthropic API calls."""

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import lancedb

from src.ingestion.embed import ChunkRecord, embed_text, write_chunk
from src.schema.models import ChunkMetadata

TEST_DB_PATH = Path(__file__).parent / "_tmp_lancedb"


def _fake_metadata(chunk_id: str, content: str) -> ChunkMetadata:
    return ChunkMetadata(
        chunk_id=chunk_id, content=content, context_prefix="From the Constitution's rights chapter.",
        exam_id="upsc_prelims_gs", topic_id="right_to_freedom", content_type="study_material",
        section_id="const_s1", source_doc="constitution.pdf", page_number=5, source_type="official_pyq",
    )


def test_embed_text_returns_768_dim_vector():
    vec = embed_text("Article 21 protects life and personal liberty.")
    assert len(vec) == 768


def test_write_chunk_round_trips_and_upserts():
    if TEST_DB_PATH.exists():
        shutil.rmtree(TEST_DB_PATH)
    db = lancedb.connect(TEST_DB_PATH)
    table = db.create_table("chunks", schema=ChunkRecord)

    write_chunk(_fake_metadata("test_1", "Article 21 protects life and liberty."), table=table)
    rows = table.to_arrow().to_pylist()
    assert len(rows) == 1
    assert rows[0]["chunk_id"] == "test_1"
    assert rows[0]["topic_id"] == "right_to_freedom"

    # Re-writing the same chunk_id with different content must update, not duplicate.
    write_chunk(_fake_metadata("test_1", "UPDATED: Article 21 text."), table=table)
    rows = table.to_arrow().to_pylist()
    assert len(rows) == 1
    assert rows[0]["content"] == "UPDATED: Article 21 text."

    write_chunk(_fake_metadata("test_2", "A different chunk."), table=table)
    assert table.count_rows() == 2

    shutil.rmtree(TEST_DB_PATH)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"PASS: {name}")
