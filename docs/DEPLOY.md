# Deploying nyaya-core to Google Cloud Run

**Scaffolding only.** This document is a reference for Rahul to run himself. Nothing in
this repo's `infra/cloud-run-scaffold` branch provisions any GCP resource, spends any
money, or makes this API reachable by anyone — that only happens when these commands are
actually run, with Rahul's own GCP project and billing account.

**Read this before running anything:** deploying this crosses `docs/FOUNDATION.md`'s own
approval gate — "anything that makes this platform reachable by anyone other than Rahul (a
public API, a cloud deployment) — explicitly deferred, flagged in PROJECT.md as
post-personal-use." Every step below keeps the service IAM-restricted (never
`--allow-unauthenticated`) specifically to hold that line as closely as Cloud Run allows,
but it is still a real change from "bound to 127.0.0.1, physically unreachable off this
Mac" — confirm you actually want that before step 4.

## What changed to make this possible

`src/api/main.py` used to bind `127.0.0.1` exclusively — that bind address *was* the
access control. Cloud Run requires the container to listen on `0.0.0.0:$PORT`, so the bind
address can no longer do that job. Access control now moves to Cloud Run's own ingress +
IAM invoker restriction (step 4 below) — **the bind-address change is safe only in
combination with that**, not on its own.

## Prerequisites (one-time, Rahul's own accounts)

- A GCP project with billing enabled (free tier still requires a billing account on file —
  it will not be charged as long as usage stays under the free tier; **verify current free
  tier limits and region eligibility at cloud.google.com/run/pricing before deploying** —
  this doc was written 2026-09-18 and GCP's terms can change).
- `gcloud` CLI installed and authenticated: `gcloud auth login`, `gcloud config set project <PROJECT_ID>`.
- APIs enabled once per project:
  ```bash
  gcloud services enable run.googleapis.com artifactregistry.googleapis.com storage.googleapis.com
  ```

## 1. Create the GCS bucket (one-time)

Pick a region close to Rahul (e.g. `asia-south1` — Mumbai) and use the **same region** for
the bucket and the Cloud Run service (avoids cross-region latency/egress).

```bash
gcloud storage buckets create gs://nyaya-core-data --location=asia-south1 --uniform-bucket-level-access
```

## 2. Upload the existing local data into the bucket (one-time)

Run from the repo root, with the local `data/` directory as it exists today
(`data/core.db`, `data/lancedb/`):

```bash
gsutil -m rsync -r data/core.db  gs://nyaya-core-data/core.db   # if this errors as a directory-vs-file mismatch, use: gsutil cp data/core.db gs://nyaya-core-data/core.db
gsutil -m rsync -r data/lancedb  gs://nyaya-core-data/lancedb
```

Re-run this `rsync` any time local ingestion adds new data and Rahul wants to push it to
the hosted copy — ingestion itself stays local-only (Ollama is local-only, per
CLAUDE.md), this is just a one-way sync of the *result*.

## 3. Build and deploy

From the repo root (where `Dockerfile` now lives):

```bash
gcloud run deploy nyaya-core \
  --source . \
  --region asia-south1 \
  --no-allow-unauthenticated \
  --add-volume=name=data,type=cloud-storage,bucket=nyaya-core-data \
  --add-volume-mount=volume=data,mount-path=/app/data \
  --set-env-vars=ANTHROPIC_API_KEY=<your-key> \
  --memory=1Gi \
  --execution-environment=gen2
```

Notes:
- `--no-allow-unauthenticated` is the default, spelled out here so it's never accidentally
  dropped — this keeps the service private (IAM-gated), not internet-public.
- `--execution-environment=gen2` is required for GCS FUSE volume mounts on Cloud Run.
- `--memory=1Gi` is a starting point — FlashRank's cross-encoder loads in-process; bump if
  you see OOM kills in Cloud Run logs after first deploy.
- Cloud Run sets `$PORT` itself (defaults to 8080) — do not set `PORT` in `--set-env-vars`,
  it's ignored/overridden by the platform anyway.
- The deploy prints a URL like `https://nyaya-core-xxxxx-uc.a.run.app` — call this
  `NYAYA_CORE_API_URL` below.

## 4. Restrict invoker IAM (the actual access control)

Grant `roles/run.invoker` only to the service accounts of the Cloud Run services that are
allowed to call this one (Devthorium's and, if/when it moves off batch-sync, Descriptive-
exams'). Find each caller's service account after *it* is deployed (Cloud Run assigns a
default one per service, or use a custom one — see each sibling repo's own `docs/DEPLOY.md`
after this):

```bash
gcloud run services add-iam-policy-binding nyaya-core \
  --region asia-south1 \
  --member="serviceAccount:<devthorium-service-account>" \
  --role="roles/run.invoker"
```

**This is the piece that isn't finished by this scaffolding pass:** Devthorium's
`backend/nyaya_core_client.py` currently calls this API with a plain `urllib.request` GET/
POST and no auth header at all. Once this service requires IAM auth, every call from
Devthorium will get a 403 until that client is updated to attach a Google-signed identity
token (`google.auth.transport.requests` + `google.oauth2.id_token.fetch_id_token(request,
audience=NYAYA_CORE_API_URL)`, added as an `Authorization: Bearer <token>` header) — this
needs the `google-auth` package added to Devthorium's backend requirements and is a real
code change, not a config flip, so it was flagged rather than done as part of this task.
Until that's built, either:
- keep this endpoint IAM-restricted and accept that Devthorium's live PFRDA/EPFO drill
  (`routes/nyaya_pyq_drill.py`) will fail with 502s against the hosted URL until the
  identity-token client is built, or
- temporarily deploy with `--allow-unauthenticated` to keep that feature working, which
  reopens the "reachable by anyone" gate this whole doc is trying to avoid — Rahul's call,
  not made here.

## 5. Point Devthorium at the hosted URL

In Devthorium's own Cloud Run deploy (see `../Devthorium/docs/migration/03_gcp_cloud_run_vercel_deploy.md`),
set:
```
NYAYA_CORE_API_URL=https://nyaya-core-xxxxx-uc.a.run.app
```
replacing the `http://127.0.0.1:8420` local default in `backend/nyaya_core_client.py`.

## Newly unblocked (not built here, flagged for a separate decision)

`CLAUDE.md`'s sibling-projects note says Descriptive-exams ("Nyaya Scribe") "consumes via
batch sync (Railway can't reach a local-only service) — never add a live API dependency
from Scribe to here without revisiting DECIDE-03." Once this service has a real URL
(instead of `127.0.0.1`), that constraint's premise changes — Scribe *could* call it live
instead of batch-syncing. This still needs the same IAM identity-token work described in
step 4 (or a shared-secret scheme) on Scribe's side, a decision on whether live latency is
acceptable for Scribe's use case, and revisiting DECIDE-03 in `docs/decisions.md` as that
doc itself requires. Not built or decided here — flagging per the task that requested this
scaffolding.
