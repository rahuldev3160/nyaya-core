import pdfplumber


def extract_text(filepath: str) -> list[tuple[int, str]]:
    """Returns (page_number, page_text) pairs, 1-indexed. Page boundaries must survive
    past this function — the chunker needs them for ChunkMetadata.page_number and
    sections.page_start/page_end (BUG-02: the original version joined pages into one
    string and lost this, which Devthorium never needed since it has no citations).
    """
    pages = []
    with pdfplumber.open(filepath) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if text:
                pages.append((i, text))
    return pages


def get_page_text_quality(filepath: str, sample_pages: int = 3) -> float:
    """Returns avg chars per page. Low value (<100) means likely scanned."""
    try:
        with pdfplumber.open(filepath) as pdf:
            pages = pdf.pages[:sample_pages]
            total = sum(len(p.extract_text() or "") for p in pages)
            return total / max(len(pages), 1)
    except Exception:
        return 0.0
