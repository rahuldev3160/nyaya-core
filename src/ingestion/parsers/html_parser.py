from bs4 import BeautifulSoup


def extract_text(filepath: str) -> list[tuple[int, str]]:
    """No fixed page concept — single (1, text) page, see docx_parser.py (BUG-02)."""
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f.read(), "lxml")
    for tag in soup(["script", "style", "head"]):
        tag.decompose()
    return [(1, soup.get_text(separator="\n", strip=True))]
