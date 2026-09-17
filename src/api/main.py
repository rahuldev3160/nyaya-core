"""FastAPI app entrypoint for nyaya-core's Phase 2 API.

Local-only, single-user: binds 127.0.0.1 exclusively, never 0.0.0.0. Devthorium's own
backend binds 0.0.0.0 for phone LAN access, but nyaya-core must stay reachable by no one
but Rahul's own machine (FOUNDATION.md's "reachable by anyone but Rahul" approval gate).

Run: .venv/bin/python -m src.api.main
"""
from __future__ import annotations

from fastapi import FastAPI

from src.api.routes import router as core_router
from src.api.routes_attempts import router as attempts_router

app = FastAPI(title="Nyaya Core API", version="0.1.0")
app.include_router(core_router)
app.include_router(attempts_router)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8420)
