import subprocess


def extract_text(filepath: str) -> list[tuple[int, str]]:
    """Extract text from macOS .textClipping files. No fixed page concept — single
    (1, text) page, see docx_parser.py (BUG-02)."""
    try:
        result = subprocess.run(["strings", filepath], capture_output=True, text=True, timeout=10)
        lines = [l.strip() for l in result.stdout.splitlines() if len(l.strip()) > 10]
        return [(1, "\n".join(lines))]
    except Exception:
        try:
            with open(filepath, "rb") as f:
                return [(1, f.read().decode("utf-8", errors="ignore"))]
        except Exception:
            return [(1, "")]
