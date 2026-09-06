import pytesseract
from pdf2image import convert_from_path
from tqdm import tqdm


def extract_text(filepath: str, dpi: int = 200) -> list[tuple[int, str]]:
    """Returns (page_number, page_text) pairs, 1-indexed — see digital_pdf.py (BUG-02)."""
    images = convert_from_path(filepath, dpi=dpi)
    pages = []
    for i, img in enumerate(tqdm(images, desc=f"OCR: {filepath.split('/')[-1]}", leave=False), start=1):
        text = pytesseract.image_to_string(img, lang="eng")
        if text.strip():
            pages.append((i, text))
    return pages
