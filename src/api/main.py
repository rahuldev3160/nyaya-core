"""FastAPI app entrypoint for nyaya-core's Phase 2 API.

Binding history: originally bound 127.0.0.1 exclusively (never 0.0.0.0) because the bind
address was the *only* access control for "reachable by no one but Rahul" (FOUNDATION.md's
approval gate on any cloud deployment). Scaffolded 2026-09-18 for an optional move to
Google Cloud Run (see docs/DEPLOY.md) — Cloud Run requires the container to listen on
0.0.0.0:$PORT, so the bind address can no longer be the access control. Binding 0.0.0.0
here is harmless *only* in combination with Cloud Run's own ingress/IAM restriction (never
`--allow-unauthenticated`, invoker IAM limited to Devthorium's and Descriptive-exams' own
service accounts) -- see docs/DEPLOY.md for the exact deploy flags. Running this locally
with `python -m src.api.main` still binds 0.0.0.0 now (was 127.0.0.1) -- on a laptop with a
firewall this is low-risk, but it does mean the API is reachable from the local network
while running locally, not just localhost. This code change does not itself deploy
anything or make the API reachable from the internet -- that only happens if/when Rahul
runs the `gcloud run deploy` commands in docs/DEPLOY.md himself.

Run: .venv/bin/python -m src.api.main
"""
from __future__ import annotations

import os

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

    # PORT is Cloud Run's injected env var (defaults to 8080 there); 8420 is this
    # repo's existing local-dev default when PORT is unset (matches nyaya_core_client.py
    # and HANDOFF.md's documented local port).
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8420")))
