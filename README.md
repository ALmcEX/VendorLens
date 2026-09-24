# VendorLens

VendorLens is an evidence-bound review workflow for security and privacy teams evaluating AI SaaS vendors. This foundation release establishes the deployable engineering path—web, API, durable worker, PostgreSQL, object storage, queue, CI, and hosted smoke verification—before adding document ingestion or review logic.

> **Current boundary:** this is infrastructure scaffolding, not a vendor-risk decision system. It does not accept vendor evidence, score controls, approve purchases, or call paid AI models.

## Architecture

```text
Browser
  │
  ├── Next.js 16 / React 19 ───────────── Vercel Hobby
  │        │
  │        └── HTTPS JSON API
  │
  └── FastAPI ─────────────────────────── Render free web service
           │
           ├── PostgreSQL job metadata ── Supabase Free
           ├── private Storage probe ──── Supabase Storage
           └── UUID-only queue message ── Supabase Queues (pgmq)
                                                │
                                                └── Python worker on Render
```

The example workflow validates one label, enforces idempotency and abuse guards, persists a queued job, publishes only its UUID, uppercases the label in the worker, stores the terminal result, and archives the queue message. Failures expose stable categories rather than internal exception details.

## Repository map

| Path | Purpose |
| --- | --- |
| `apps/web` | Next.js public foundation page and safe example-job UI |
| `apps/api` | FastAPI routes, runtime assembly, persistence, queue, and Storage adapters |
| `apps/worker` | Durable queue consumer, retry policy, shutdown handling, and migration runner |
| `packages/vendorlens-core` | Pure domain models and deterministic operations |
| `supabase` | Local Supabase configuration and ordered SQL migrations |
| `infra/docker` | Reproducible non-root API and worker images |
| `infra/render.yaml` | Render Blueprint for the API and worker |
| `tests/integration` | Database migration verification |
| `tests/smoke` | Local and hosted end-to-end checks |
| `docs/superpowers` | Approved architecture specification and implementation plan |

## Prerequisites

- Git
- Python 3.13 and [uv](https://docs.astral.sh/uv/)
- Node.js 24 and pnpm 11.19.0
- Docker Desktop or a compatible Linux Docker engine
- Supabase CLI 2.117.0 (the scripts use `pnpm dlx`, so no global install is required)

Windows local Supabase requires Docker Desktop with its Linux engine available. If WSL is intentionally disabled, run unit/build checks locally and rely on the public GitHub Actions `Supabase` and `Containers` jobs for Linux integration verification.

## Local setup

```powershell
git clone https://github.com/ALmcEX/VendorLens.git
Set-Location VendorLens
Copy-Item .env.example .env
uv sync --frozen --all-packages
pnpm install --frozen-lockfile
./scripts/dev.ps1
```

`scripts/dev.ps1` starts local Supabase, resets and migrates its database, derives only the local connection values, builds and starts the API and worker with Compose, then runs the web development server in the foreground.

The services are available at:

- Web: `http://localhost:3000`
- API: `http://localhost:8000`
- API liveness: `http://localhost:8000/health/live`
- API readiness: `http://localhost:8000/health/ready`
- Supabase Studio: `http://localhost:54323`

Stop the foreground web server with `Ctrl+C`, then run:

```powershell
docker compose down
pnpm dlx supabase@2.117.0 stop
```

## Environment variables

The committed `.env.example` contains names and safe local placeholders only. Never commit a populated `.env` file.

| Variable | Consumer | Meaning |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | Web | Public API origin, frozen into the browser bundle at build time |
| `VENDORLENS_DATABASE_URL` | API, worker, migrator | SQLAlchemy-style async PostgreSQL URL (`postgresql+asyncpg://...`) |
| `VENDORLENS_SUPABASE_URL` | API | Server-side Supabase project URL used for Storage readiness |
| `VENDORLENS_SUPABASE_SERVICE_ROLE_KEY` | API | Server-only Storage credential; never expose with `NEXT_PUBLIC_` |
| `VENDORLENS_CORS_ORIGINS` | API | JSON array of allowed browser origins |
| `VENDORLENS_STORAGE_BUCKET` | API | Private bucket name; default `vendor-documents` |
| `VENDORLENS_QUEUE_NAME` | API, worker | PGMQ queue name; default `example_jobs` |
| `VENDORLENS_TRUST_PROXY_HEADERS` | API | Trust the first forwarded client address only on the hosted proxy path |
| `VENDORLENS_REQUEST_LIMIT` | API | Per-process submissions allowed in one fixed window |
| `VENDORLENS_QUEUE_DEPTH_LIMIT` | API | Queue depth at which new work receives HTTP 429 |
| `VENDORLENS_MAX_ATTEMPTS` | Worker | Maximum processing attempts before an inspectable terminal failure |
| `VENDORLENS_SHUTDOWN_GRACE_SECONDS` | Worker | Bounded in-flight shutdown grace period |

## Tests and checks

Run the normal local suite:

```powershell
./scripts/check.ps1
```

Include container builds when a Linux Docker engine is available:

```powershell
./scripts/check.ps1 -Containers
```

Focused commands:

```powershell
uv run pytest -q
uv run ruff check packages apps tests
uv run ruff format --check packages apps tests
uv run mypy packages/vendorlens-core/src apps/api/src apps/worker/src
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

## GitHub CI

The least-privilege CI workflow exposes four required job names:

- `Python`: lint, format, strict typing, and unit tests
- `Web`: frozen install, lint, typecheck, component tests, and production build
- `Supabase`: local migration, repository resources, composed API/worker, and end-to-end smoke
- `Containers`: independent API and worker image builds

The public repository uses standard GitHub-hosted runners, which GitHub documents as free for public repositories. Dependabot checks uv/pip, pnpm/npm, GitHub Actions, and both Dockerfiles weekly.

## Supabase provisioning

1. Create a Free project in the Supabase dashboard and record the project URL, service-role key, and database connection string.
2. Use a connection endpoint reachable from Render. Convert its scheme to `postgresql+asyncpg://` for `VENDORLENS_DATABASE_URL`.
3. Keep the service-role key only in Render's server-side environment. It must never be added to Vercel or a browser variable.
4. The paid Render worker runs `python -m vendorlens_worker.migrate` once before each deploy. The runner takes a PostgreSQL advisory lock, verifies checksums, and applies each ordered file in `supabase/migrations` exactly once.
5. Confirm the private `vendor-documents` bucket, `public.example_jobs` table, and `example_jobs` queue exist after the first worker pre-deploy step.

Supabase Free projects can pause after a week of low activity. Restore a paused project in the Supabase dashboard before diagnosing API readiness failures.

## Render deployment

1. In Render, create a Blueprint from this repository and select `infra/render.yaml`.
2. Keep `vendorlens-api` on the Free web-service plan.
3. Confirm the `vendorlens-worker` plan is `0.5c-512mb` before applying; this is the paid **$7/month** component.
4. Enter the prompted server-side values:
   - `VENDORLENS_DATABASE_URL` for both services
   - `VENDORLENS_SUPABASE_URL` and `VENDORLENS_SUPABASE_SERVICE_ROLE_KEY` for the API
   - `VENDORLENS_CORS_ORIGINS`, initially the exact Vercel production origin as a JSON array
5. Deploy the worker first so its pre-deploy migration completes, then verify API `/health/ready`.

The API uses Render's free web service and may cold-start after inactivity. The worker is intentionally always-on so queued work does not depend on a web request waking a second service.

## Vercel deployment

1. Import the GitHub repository into Vercel.
2. Set the project root directory to `apps/web` and keep the detected Next.js framework.
3. Add `NEXT_PUBLIC_API_BASE_URL` with the public Render API origin for Production and Preview as appropriate.
4. Deploy, then update `VENDORLENS_CORS_ORIGINS` on Render with the exact Vercel production origin and redeploy the API.

The Hobby plan is intended for personal, non-commercial projects. Use Vercel Pro instead if the deployment becomes commercial or needs team features.

## Smoke verification

After all three providers report healthy deployments:

```powershell
$env:VENDORLENS_HOSTED_API_URL = "https://vendorlens-api.example.onrender.com"
$env:VENDORLENS_HOSTED_WEB_URL = "https://vendorlens.example.vercel.app"
uv run pytest tests/smoke/hosted_smoke.py -q
```

The test checks the page, API liveness/readiness, job submission, durable worker completion, and final `VENDORLENS` result within 60 seconds.

## Monthly cost

Expected foundation cost in USD, excluding tax, custom domains, and optional overages:

| Service | Plan | Expected monthly cost |
| --- | --- | ---: |
| Vercel frontend | Hobby (personal/non-commercial) | $0 |
| Render API | Free web service | $0 |
| Render worker | `0.5c-512mb` | $7 |
| Supabase database, Storage, Queues | Free | $0 |
| GitHub Actions | Public repository, standard runners | $0 |
| **Expected total** | | **about $7/month** |

Pricing and limits can change. Verify the current official [Render pricing](https://render.com/pricing), [Vercel pricing](https://vercel.com/pricing), [Supabase pricing](https://supabase.com/pricing), and [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions) before enabling the paid worker. Set provider budgets or alerts where available; do not add a custom domain or paid model API in this phase.

## Troubleshooting

- **`/health/live` works but `/health/ready` returns 503:** inspect the returned stable dependency category, then verify database reachability, the PGMQ extension/queue, and private bucket metadata. Details and credentials are deliberately not returned.
- **API returns 429:** wait for the fixed window or drain the queue. Do not raise limits until the cause is understood.
- **Render worker restarts:** unarchived work becomes visible again after the queue visibility window. Terminal jobs are skipped idempotently.
- **Supabase project paused:** restore it in Supabase, wait for database and Storage availability, then retry readiness.
- **Docker hangs on Windows:** verify Docker Desktop's Linux engine and WSL 2 are enabled. Enabling WSL is an OS-level choice; CI remains the supported integration fallback.
- **Vercel page cannot reach the API:** rebuild after changing `NEXT_PUBLIC_API_BASE_URL`, then ensure CSP and Render CORS both contain that exact origin.

## Data-safety boundary

- The foundation accepts one non-sensitive label of at most 100 Unicode characters.
- It accepts no files, vendor evidence, personal data, secrets, or purchasing instructions.
- Browser code receives only the public API base URL.
- Database, service-role, and queue credentials remain server-side.
- The worker cannot send email, approve purchases, modify repositories, or take external actions.
- Future vendor documents must be treated as untrusted data, never as instructions.

See the [approved design](docs/superpowers/specs/2026-09-23-foundation-deployment-design.md) for the complete scope and threat boundary.
