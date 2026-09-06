"""Sanity tests for src/ingestion/chunker.py — run with: python -m pytest tests/test_chunker.py -v
(or `python tests/test_chunker.py` for a plain run without pytest)."""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.chunker import chunk_document, chunk_section, split_sections


def test_statute_article_stays_in_one_section():
    pages = [(1, "Article 21\nProtection of life and personal liberty.\nNo person shall be "
                  "deprived of his life or personal liberty except according to procedure "
                  "established by law.\nArticle 22\nProtection against arrest and detention "
                  "in certain cases.")]
    sections = split_sections(pages, doc_id="const_1")
    assert len(sections) == 2
    assert sections[0].heading == "Article 21"
    assert "deprived of his life" in sections[0].full_text
    assert "Article 22" not in sections[0].full_text  # didn't leak into the next section


def test_table_rows_stay_atomic_across_a_chunk_boundary():
    # Build a section whose body is mostly one big table — bigger than CHUNK_SIZE_WORDS
    # if it were naively word-sliced, to prove the whole table survives as one block.
    header = "Year | GDP Growth | Inflation"
    rows = "\n".join(f"{2000+i} | {i}.5% | {i}.2%" for i in range(200))
    pages = [(1, f"ECONOMIC INDICATORS\n{header}\n{rows}")]
    sections = split_sections(pages, doc_id="report_1")
    assert len(sections) == 1
    chunks = chunk_section(sections[0])
    table_chunks = [c for c in chunks if "GDP Growth" in c.content]
    assert len(table_chunks) == 1  # table wasn't split across chunks
    assert table_chunks[0].content.count("\n") >= 200  # the whole table is in there


def test_long_section_without_headings_splits_on_paragraphs():
    paragraphs = [f"Paragraph {i} " + ("word " * 80) for i in range(10)]
    pages = [(1, "\n\n".join(paragraphs))]
    sections = split_sections(pages, doc_id="doc_1")
    assert len(sections) == 1
    chunks = chunk_section(sections[0])
    assert len(chunks) > 1  # Stage 2 fired
    for c in chunks:
        assert len(c.content.split()) <= 375 + 80  # no chunk wildly over budget
        # never split mid-paragraph: every chunk's text starts at a paragraph boundary
        assert c.content.startswith("Paragraph")


def test_page_numbers_and_section_ids_survive_end_to_end():
    pages = [(1, "Article 5\nShort clause on page one."),
             (2, "Continuing on page two of the same article.\nArticle 6\nNext one.")]
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = OFF;")
    conn.execute("""CREATE TABLE sections (
        section_id TEXT PRIMARY KEY, doc_id TEXT, exam_id TEXT, topic_id TEXT,
        content_type TEXT, heading TEXT, full_text TEXT, page_start INTEGER, page_end INTEGER)""")

    chunks = chunk_document(pages, doc_id="const_2", exam_id="upsc_mains_gs", conn=conn)
    row_count = conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
    assert row_count == 2  # Article 5 section + Article 6 section persisted

    article5_chunk = next(c for c in chunks if "Short clause" in c.content)
    assert article5_chunk.page_number == 1
    assert "Continuing on page two" in article5_chunk.content  # spans pages, same section

    section_row = conn.execute(
        "SELECT page_start, page_end FROM sections WHERE section_id = ?",
        (article5_chunk.section_id,),
    ).fetchone()
    assert section_row == (1, 2)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"PASS: {name}")
