"""Unit tests for the pure logic in scripts/ingest.py (hashing, skip-list, parser
detection, published_date inference) — no API calls, no real file parsing."""

import shutil
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from ingest import detect_parser, file_hash, infer_published_date, load_log, save_log

TMP_DIR = Path(__file__).parent / "_tmp_ingest"


def test_file_hash_changes_when_content_changes():
    TMP_DIR.mkdir(exist_ok=True)
    f = TMP_DIR / "a.docx"
    f.write_text("version 1")
    h1 = file_hash(f)
    time.sleep(0.01)
    f.write_text("version 2, longer content")
    h2 = file_hash(f)
    assert h1 != h2
    shutil.rmtree(TMP_DIR)


def test_file_hash_stable_for_unchanged_file():
    TMP_DIR.mkdir(exist_ok=True)
    f = TMP_DIR / "a.docx"
    f.write_text("stable content")
    h1 = file_hash(f)
    h2 = file_hash(f)
    assert h1 == h2
    shutil.rmtree(TMP_DIR)


def test_log_round_trip(monkeypatch):
    import ingest as ingest_module
    log_path = TMP_DIR / "ingestion_log.json"
    TMP_DIR.mkdir(exist_ok=True)
    monkeypatch.setattr(ingest_module, "LOG_PATH", log_path)
    save_log({"foo.docx": "abc123"})
    assert load_log() == {"foo.docx": "abc123"}
    shutil.rmtree(TMP_DIR)


def test_detect_parser_by_extension():
    assert detect_parser(Path("notes.docx")) == "docx"
    assert detect_parser(Path("notes.pages")) == "pages"
    assert detect_parser(Path("notes.html")) == "html"
    assert detect_parser(Path("notes.textClipping")) == "textclipping"
    assert detect_parser(Path("notes.xyz")) == "unknown"


def test_detect_parser_handwritten_keyword_overrides_pdf_default():
    assert detect_parser(Path("Handwritten Notes.pdf")) == "handwritten_pdf"


def test_infer_published_date_prefers_cli_override():
    result = infer_published_date(Path("report_2023.pdf"), cli_override=date(2020, 1, 1))
    assert result == date(2020, 1, 1)


def test_infer_published_date_from_filename_year():
    result = infer_published_date(Path("Economic_Survey_2023.pdf"), cli_override=None)
    assert result == date(2023, 1, 1)


def test_infer_published_date_none_when_no_year_found():
    result = infer_published_date(Path("syllabus.pdf"), cli_override=None)
    assert result is None


if __name__ == "__main__":
    class _FakeMonkeypatch:
        def setattr(self, obj, name, value):
            setattr(obj, name, value)

    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            import inspect
            if "monkeypatch" in inspect.signature(fn).parameters:
                fn(_FakeMonkeypatch())
            else:
                fn()
            print(f"PASS: {name}")
