# Container image for nyaya-core's FastAPI service (src/api/main.py), for deploying to
# Google Cloud Run. Scaffolding only -- this file does not build or deploy anything by
# itself. See docs/DEPLOY.md for the exact commands Rahul runs himself.
#
# What's deliberately NOT installed here: Ollama and the ingestion-only packages
# (pdfplumber, pdf2image, pytesseract, python-docx, beautifulsoup4, lxml, tqdm) that
# requirements.txt lists for local ingestion runs. CLAUDE.md is explicit that "Ollama
# (nomic-embed-text) is used ONLY at local ingestion time -- never at query time," and
# the API layer (src/api/, src/retrieval/) never imports the ingestion parsers or an
# Ollama client at request time -- only src/ingestion/embed.py's get_chunks_table() (a
# LanceDB table handle, not an embedding call). So this image installs the full
# requirements.txt as-is (simplest, matches the repo's one real dependency file, avoids
# guessing at a narrower list) but never runs `scripts/*ingest*` -- those stay a local
# workflow on Rahul's own machine, per PROJECT.md/FOUNDATION.md (ingestion is local-only
# by design, this image only ever serves the read-mostly API).
#
# Build (from repo root):
#   docker build -t nyaya-core .

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY scripts/ scripts/

# data/ (core.db, lancedb/) is intentionally NOT copied in -- see .dockerignore. On Cloud
# Run this path is a GCS FUSE volume mount (docs/DEPLOY.md); locally it's the repo's own
# data/ directory via a bind mount, never baked into the image.

# Cloud Run injects $PORT (defaults to 8080 there); src/api/main.py's __main__ block
# falls back to 8420 for local-dev parity when $PORT is unset.
ENV PORT=8420
EXPOSE 8420

CMD ["python", "-m", "src.api.main"]
