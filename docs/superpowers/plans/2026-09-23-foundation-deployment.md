# VendorLens Foundation and Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and publicly deploy the VendorLens monorepo foundation with a Next.js frontend, FastAPI API, durable Supabase queue, Render worker, CI, and a verified asynchronous example job.

**Architecture:** A public monorepo contains three deployable processes: Next.js on Vercel, FastAPI on Render, and a Python worker on Render. PostgreSQL, object storage, and `pgmq` run in Supabase; API and worker share only the `vendorlens-core` package and communicate through durable state and queue messages.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, SQLAlchemy, Alembic, uv, Node.js 24 LTS, Next.js 16, TypeScript, pnpm, Supabase PostgreSQL/Storage/Queues, Docker, Vercel, Render, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-23-foundation-deployment-design.md`

## Global Constraints

- Initial recurring infrastructure cost is approximately USD 7/month, excluding taxes, a custom domain, and model API usage.
- Use Python 3.13 and Node.js 24 LTS.
- Use one public GitHub repository named `VendorLens` under the `ALmcEX` account.
- Browser bundles must never contain database credentials, Supabase service-role credentials, or queue access.
- The initial deployment accepts no files and stores no sensitive content.
- The example label is limited to 100 Unicode characters.
- Job statuses are exactly `queued`, `running`, `succeeded`, and `failed`.
- HTTP errors use `application/problem+json` and include a request ID.
- API and worker may depend on `vendorlens-core`; they must not depend directly on each other.
- Patch versions are locked in generated lockfiles and updated only through green CI.
- No LLM API, authentication system, Redis service, document upload, or vendor-risk decision logic is part of this plan.

## Review Focus

- A repeated idempotency key with a different payload must return HTTP 409 and must not enqueue another message; Task 4 pins this behavior.
- An oversized or malformed Unicode label must return a stable Problem Details response; Task 4 pins this behavior.
- Rate-limit exhaustion or queue saturation must return HTTP 429 without writing or enqueueing a job; Task 4 pins this behavior.
- Duplicate delivery or worker interruption must not duplicate the result and must leave the message eligible for safe redelivery; Task 5 pins this behavior.
- Database, storage, or queue unavailability must make readiness fail without leaking credentials or internal endpoints; Task 2 pins this behavior.

---

## File Map

| Path | Responsibility |
|---|---|
| `pyproject.toml` / `uv.lock` | Python workspace, shared developer tools, and locked dependencies |
| `package.json` / `pnpm-workspace.yaml` / `pnpm-lock.yaml` | JavaScript workspace and locked dependencies |
| `packages/vendorlens-core/src/vendorlens_core/jobs.py` | Framework-independent job types, transitions, and normalization |
| `apps/api/src/vendorlens_api/` | HTTP configuration, middleware, routes, persistence, queue, and storage probes |
| `apps/worker/src/vendorlens_worker/` | Message claiming, deterministic processing, retries, and shutdown |
| `apps/web/` | Public foundation page and example-job UI |
| `supabase/migrations/` | Database table, queue, storage bucket, indexes, and grants |
| `infra/docker/` | API and worker container definitions |
| `infra/render.yaml` | Render API and paid worker Blueprint |
| `.github/workflows/ci.yml` | Required repository checks |
| `.github/dependabot.yml` | Python, npm, Actions, and Docker dependency updates |
| `tests/smoke/` | Hosted end-to-end liveness and job-completion verification |
| `README.md` | Local setup, deployment, cost, architecture, and limitation guide |

## Task 0: Install and Verify the Local Toolchain

**Files:** None

**Interfaces:**
- Consumes: Windows host with Node.js 24.19.0 and pnpm 11.19.0 already available.
- Produces: `uv`, managed Python 3.13, Docker Desktop, and Supabase CLI commands available to later tasks.

- [ ] **Step 1: Install uv and its managed Python runtime**

Request command approval, install uv from the Windows package catalog, then run:

```powershell
winget install --id astral-sh.uv -e --accept-package-agreements --accept-source-agreements
uv python install 3.13
uv python pin 3.13
uv --version
uv run python --version
```

Expected: `uv` reports a version and Python reports `3.13.x`.

- [ ] **Step 2: Install Docker Desktop if it remains unavailable**

Request installation approval immediately before the install. Install Docker Desktop, allow the user to complete any required interactive startup, then run:

```powershell
winget install --id Docker.DockerDesktop -e --accept-package-agreements --accept-source-agreements
docker version
docker compose version
```

Expected: both client and server versions are returned.

- [ ] **Step 3: Use the project-local Supabase CLI**

Do not install a global CLI. Verify the CLI through pnpm:

```powershell
pnpm dlx supabase@2.117.0 --version
```

Expected: the Supabase CLI version is returned.

## Task 1: Create the Monorepo and Shared Job Contract

**Files:**
- Create: `.editorconfig`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `pyproject.toml`
- Create: `package.json`
- Create: `pnpm-workspace.yaml`
- Create: `packages/vendorlens-core/pyproject.toml`
- Create: `packages/vendorlens-core/src/vendorlens_core/__init__.py`
- Create: `packages/vendorlens-core/src/vendorlens_core/jobs.py`
- Create: `packages/vendorlens-core/tests/test_jobs.py`
- Create: empty tracked placeholders only where needed under `controls/`, `evals/`, `docs/adr/`, `docs/failure-analysis/`, `docs/research/`, and `docs/retrospectives/`

**Interfaces:**
- Consumes: Python 3.13 and uv from Task 0.
- Produces: `JobStatus`, `ExampleJobPayload`, `ExampleJob`, `payload_fingerprint()`, and `normalize_label()` for API and worker tasks.

- [ ] **Step 1: Write the failing shared-domain tests**

```python
# packages/vendorlens-core/tests/test_jobs.py
from uuid import UUID

import pytest
from pydantic import ValidationError

from vendorlens_core.jobs import ExampleJobPayload, JobStatus, normalize_label, payload_fingerprint


def test_payload_accepts_a_short_unicode_label() -> None:
    payload = ExampleJobPayload(label="  VendorLens 测试  ")
    assert payload.label == "VendorLens 测试"


def test_payload_rejects_more_than_100_characters() -> None:
    with pytest.raises(ValidationError):
        ExampleJobPayload(label="a" * 101)


def test_fingerprint_is_stable_for_equivalent_payloads() -> None:
    first = payload_fingerprint(ExampleJobPayload(label=" VendorLens "))
    second = payload_fingerprint(ExampleJobPayload(label="VendorLens"))
    assert first == second


def test_job_status_values_are_stable() -> None:
    assert [status.value for status in JobStatus] == [
        "queued", "running", "succeeded", "failed"
    ]


def test_normalize_label_returns_uppercase_text() -> None:
    assert normalize_label("VendorLens 测试") == "VENDORLENS 测试"
```

- [ ] **Step 2: Create workspace manifests and run the test to verify failure**

Root `pyproject.toml` must declare uv workspace member `packages/vendorlens-core`, Python `>=3.13,<3.14`, and development dependencies `pytest`, `pytest-asyncio`, `ruff`, and `mypy`. The package manifest must depend on Pydantic and expose `src/vendorlens_core`.

Run:

```powershell
uv lock
uv run pytest packages/vendorlens-core/tests/test_jobs.py -q
```

Expected: FAIL because `vendorlens_core.jobs` does not exist.

- [ ] **Step 3: Implement the minimal shared job contract**

```python
# packages/vendorlens-core/src/vendorlens_core/jobs.py
from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ExampleJobPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    label: str = Field(min_length=1, max_length=100)

    @field_validator("label")
    @classmethod
    def strip_label(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("label must contain non-whitespace characters")
        return stripped


class ExampleJob(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: UUID
    idempotency_key: str
    payload_hash: str
    status: JobStatus
    attempt_count: int = Field(ge=0)
    result: str | None = None
    error_category: str | None = None


def payload_fingerprint(payload: ExampleJobPayload) -> str:
    canonical = json.dumps(payload.model_dump(), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_label(label: str) -> str:
    return label.upper()
```

- [ ] **Step 4: Run domain and quality checks**

```powershell
uv run pytest packages/vendorlens-core/tests/test_jobs.py -q
uv run ruff check packages/vendorlens-core
uv run ruff format --check packages/vendorlens-core
uv run mypy packages/vendorlens-core/src
```

Expected: all commands pass.

- [ ] **Step 5: Lock JavaScript workspace metadata**

Root `package.json` must set `private: true`, `packageManager` to the installed pnpm 11 release, and scripts that delegate `lint`, `typecheck`, `test`, and `build` to workspace packages. `pnpm-workspace.yaml` must include `apps/*`.

Run:

```powershell
pnpm install --lockfile-only
git branch -M main
```

Expected: `pnpm-lock.yaml` exists and the current branch is `main`.

- [ ] **Step 6: Commit the workspace and domain contract**

```powershell
git add .editorconfig .gitignore .env.example pyproject.toml uv.lock package.json pnpm-workspace.yaml pnpm-lock.yaml packages controls evals docs
git commit -m "feat: establish monorepo and job domain"
```

## Task 2: Add the FastAPI Runtime, Health Checks, and Error Contract

**Files:**
- Create: `apps/api/pyproject.toml`
- Create: `apps/api/src/vendorlens_api/__init__.py`
- Create: `apps/api/src/vendorlens_api/config.py`
- Create: `apps/api/src/vendorlens_api/problems.py`
- Create: `apps/api/src/vendorlens_api/middleware.py`
- Create: `apps/api/src/vendorlens_api/dependencies.py`
- Create: `apps/api/src/vendorlens_api/routes/health.py`
- Create: `apps/api/src/vendorlens_api/main.py`
- Create: `apps/api/tests/test_health.py`
- Create: `apps/api/tests/test_problems.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: `vendorlens_core` workspace package.
- Produces: `create_app(settings, probes) -> FastAPI`, `GET /health/live`, `GET /health/ready`, request-ID middleware, and Problem Details responses.

- [ ] **Step 1: Write failing health and redaction tests**

```python
# apps/api/tests/test_health.py
from fastapi.testclient import TestClient

from vendorlens_api.main import create_app


class ProbeSet:
    async def database(self) -> None: return None
    async def queue(self) -> None: return None
    async def storage(self) -> None: return None


def test_liveness_has_no_dependency_checks() -> None:
    response = TestClient(create_app(probes=ProbeSet())).get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_reports_only_failed_dependency_category() -> None:
    class FailedDatabase(ProbeSet):
        async def database(self) -> None:
            raise RuntimeError("postgresql://secret@internal.example/vendorlens")

    response = TestClient(create_app(probes=FailedDatabase())).get("/health/ready")
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["type"].endswith("/database-unavailable")
    assert "secret" not in response.text
    assert "internal.example" not in response.text
    assert response.headers["x-request-id"] == body["request_id"]
```

```python
# apps/api/tests/test_problems.py
from fastapi.testclient import TestClient

from vendorlens_api.main import create_app


def test_validation_errors_use_problem_details() -> None:
    response = TestClient(create_app()).post("/api/v1/example-jobs", json={"label": ""})
    assert response.status_code in {404, 422}
    if response.status_code == 422:
        assert response.headers["content-type"].startswith("application/problem+json")
        assert set(response.json()) >= {"type", "title", "status", "detail", "request_id"}
```

- [ ] **Step 2: Add API dependencies and verify failure**

The API manifest must add FastAPI, Uvicorn, Pydantic Settings, HTTPX, SQLAlchemy with asyncio support, asyncpg, and the workspace `vendorlens-core` package.

```powershell
uv lock
uv run pytest apps/api/tests/test_health.py apps/api/tests/test_problems.py -q
```

Expected: FAIL because the API package has not been implemented.

- [ ] **Step 3: Implement settings, probes, request IDs, and Problem Details**

`Settings` must use the `VENDORLENS_` prefix, forbid unknown configuration, expose explicit CORS origins, and validate dependency timeouts between 0.1 and 10 seconds. `create_app()` must accept probe objects for tests and install middleware before routes. Readiness checks run concurrently under bounded timeouts and expose category names only.

Core response shape:

```python
class ProblemDetails(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    instance: str | None = None
    request_id: str
```

- [ ] **Step 4: Run API checks**

```powershell
uv run pytest apps/api/tests/test_health.py apps/api/tests/test_problems.py -q
uv run ruff check apps/api
uv run ruff format --check apps/api
uv run mypy apps/api/src
```

Expected: all commands pass.

- [ ] **Step 5: Commit the API foundation**

```powershell
git add pyproject.toml uv.lock apps/api
git commit -m "feat: add API health and error contracts"
```

## Task 3: Create Supabase Persistence, Storage, and Queue Adapters

**Files:**
- Create: `supabase/config.toml`
- Create: `supabase/migrations/202609230001_foundation.sql`
- Create: `apps/api/src/vendorlens_api/persistence/models.py`
- Create: `apps/api/src/vendorlens_api/persistence/repository.py`
- Create: `apps/api/src/vendorlens_api/infrastructure/queue.py`
- Create: `apps/api/src/vendorlens_api/infrastructure/storage.py`
- Create: `apps/api/tests/test_repository.py`
- Create: `apps/api/tests/test_queue.py`
- Create: `tests/integration/test_migration.py`

**Interfaces:**
- Consumes: `ExampleJob`, `ExampleJobPayload`, `JobStatus`, and a PostgreSQL connection.
- Produces: `ExampleJobRepository.create/get/mark_failed`, `QueuePublisher.publish/depth`, and `StorageProbe.check`.

- [ ] **Step 1: Write failing repository and queue tests**

```python
async def test_repository_round_trips_a_queued_job(repository) -> None:
    created = await repository.create(
        idempotency_key="same-request",
        payload_hash="abc123",
        label="VendorLens",
    )
    loaded = await repository.get(created.id)
    assert loaded == created
    assert loaded.status is JobStatus.QUEUED


async def test_publish_serializes_only_job_identity(fake_connection) -> None:
    publisher = QueuePublisher(fake_connection, queue_name="example_jobs")
    await publisher.publish(job_id=UUID("00000000-0000-0000-0000-000000000001"))
    assert fake_connection.last_message == {
        "job_id": "00000000-0000-0000-0000-000000000001"
    }
```

- [ ] **Step 2: Create and validate the Supabase migration**

The migration must:

```sql
create extension if not exists pgmq;
select pgmq.create('example_jobs');

create table public.example_jobs (
  id uuid primary key,
  idempotency_key text not null unique,
  payload_hash char(64) not null,
  label text not null check (char_length(label) between 1 and 100),
  status text not null check (status in ('queued', 'running', 'succeeded', 'failed')),
  attempt_count integer not null default 0 check (attempt_count >= 0),
  result text,
  error_category text,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz
);

insert into storage.buckets (id, name, public, file_size_limit)
values ('vendor-documents', 'vendor-documents', false, 10485760)
on conflict (id) do nothing;
```

Start local Supabase and apply the migration:

```powershell
pnpm dlx supabase@2.117.0 start
pnpm dlx supabase@2.117.0 db reset
uv run pytest tests/integration/test_migration.py -q
```

Expected: the table, private bucket, and `example_jobs` queue exist.

- [ ] **Step 3: Implement async repository and adapters**

Use SQLAlchemy async sessions for job metadata. Use parameterized SQL for `pgmq.send`, `pgmq.metrics`, and readiness probes. Storage readiness must perform a bounded metadata/list operation against the private bucket and must not upload a file.

- [ ] **Step 4: Run persistence tests**

```powershell
uv run pytest apps/api/tests/test_repository.py apps/api/tests/test_queue.py tests/integration/test_migration.py -q
uv run ruff check apps/api/src/vendorlens_api/persistence apps/api/src/vendorlens_api/infrastructure
uv run mypy apps/api/src
```

Expected: all commands pass.

- [ ] **Step 5: Commit persistence and Supabase resources**

```powershell
git add supabase apps/api tests/integration
git commit -m "feat: add Supabase persistence and queue adapters"
```

## Task 4: Implement Job Submission, Idempotency, and Abuse Guards

**Files:**
- Create: `apps/api/src/vendorlens_api/rate_limit.py`
- Create: `apps/api/src/vendorlens_api/services/jobs.py`
- Create: `apps/api/src/vendorlens_api/routes/jobs.py`
- Create: `apps/api/tests/test_jobs_api.py`
- Modify: `apps/api/src/vendorlens_api/main.py`
- Modify: `apps/api/src/vendorlens_api/config.py`

**Interfaces:**
- Consumes: `ExampleJobRepository`, `QueuePublisher`, `ExampleJobPayload`.
- Produces: `POST /api/v1/example-jobs` and `GET /api/v1/example-jobs/{job_id}`.

- [ ] **Step 1: Write failing endpoint tests for the review-focus cases**

```python
def test_duplicate_key_with_different_payload_returns_409(client) -> None:
    headers = {"Idempotency-Key": "stable-key"}
    assert client.post("/api/v1/example-jobs", json={"label": "first"}, headers=headers).status_code == 202
    response = client.post("/api/v1/example-jobs", json={"label": "second"}, headers=headers)
    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    assert client.queue.publish_count == 1


def test_oversized_label_returns_problem_details(client) -> None:
    response = client.post("/api/v1/example-jobs", json={"label": "界" * 101})
    assert response.status_code == 422
    assert response.json()["status"] == 422
    assert client.queue.publish_count == 0


def test_rate_limit_rejects_before_persistence(rate_limited_client) -> None:
    response = rate_limited_client.post("/api/v1/example-jobs", json={"label": "safe"})
    assert response.status_code == 429
    assert rate_limited_client.repository.create_count == 0


def test_queue_depth_guard_rejects_before_persistence(saturated_client) -> None:
    response = saturated_client.post("/api/v1/example-jobs", json={"label": "safe"})
    assert response.status_code == 429
    assert saturated_client.repository.create_count == 0
```

- [ ] **Step 2: Run the endpoint tests to verify failure**

```powershell
uv run pytest apps/api/tests/test_jobs_api.py -q
```

Expected: FAIL because the route and job service do not exist.

- [ ] **Step 3: Implement the job service and routes**

The service order is fixed:

```text
validate payload
→ enforce per-client fixed-window limit
→ read queue depth and enforce guard
→ resolve idempotency key and payload hash
→ return existing matching job OR reject mismatched reuse
→ persist queued job
→ publish queue identity
→ mark failed with enqueue_failed if publication fails
→ return 202 with Location header
```

The client address resolver trusts `X-Forwarded-For` only when `VENDORLENS_TRUST_PROXY_HEADERS=true`; local tests default it to false. The default limit is 5 submissions per client per 60 seconds, and the default queue-depth guard is 100.

- [ ] **Step 4: Run all API tests and static checks**

```powershell
uv run pytest apps/api/tests -q
uv run ruff check apps/api
uv run ruff format --check apps/api
uv run mypy apps/api/src
```

Expected: all commands pass.

- [ ] **Step 5: Commit the public API workflow**

```powershell
git add apps/api
git commit -m "feat: add idempotent example job API"
```

## Task 5: Implement the Durable Worker

**Files:**
- Create: `apps/worker/pyproject.toml`
- Create: `apps/worker/src/vendorlens_worker/__init__.py`
- Create: `apps/worker/src/vendorlens_worker/config.py`
- Create: `apps/worker/src/vendorlens_worker/queue.py`
- Create: `apps/worker/src/vendorlens_worker/repository.py`
- Create: `apps/worker/src/vendorlens_worker/processor.py`
- Create: `apps/worker/src/vendorlens_worker/main.py`
- Create: `apps/worker/tests/test_processor.py`
- Create: `apps/worker/tests/test_shutdown.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: queue messages shaped like `{ "job_id": "00000000-0000-0000-0000-000000000001" }` and queued job rows.
- Produces: `Worker.run_once() -> bool`, durable status transitions, archived successful messages, and safely redeliverable interrupted messages.

- [ ] **Step 1: Write failing worker tests**

```python
async def test_duplicate_delivery_does_not_repeat_completed_work(worker, succeeded_job, message) -> None:
    await worker.process(message)
    assert worker.repository.result_write_count == 0
    assert worker.queue.archive_count == 1


async def test_transient_failure_leaves_message_for_redelivery(worker, queued_job, message) -> None:
    worker.operation.raise_error = TimeoutError("temporary")
    await worker.process(message)
    assert worker.repository.get(queued_job.id).status is JobStatus.QUEUED
    assert worker.queue.archive_count == 0


async def test_max_attempt_failure_is_inspectable(worker, queued_job, final_attempt_message) -> None:
    worker.operation.raise_error = ValueError("permanent")
    await worker.process(final_attempt_message)
    failed = worker.repository.get(queued_job.id)
    assert failed.status is JobStatus.FAILED
    assert failed.error_category == "processing_failed"
    assert worker.queue.archive_count == 1
```

- [ ] **Step 2: Add worker dependencies and verify failure**

```powershell
uv lock
uv run pytest apps/worker/tests -q
```

Expected: FAIL because the worker package does not exist.

- [ ] **Step 3: Implement queue claim, processing, retry, and shutdown**

The worker uses `pgmq.read` with a bounded visibility timeout and batch size one. It loads the job by UUID, skips and archives already-terminal jobs, increments attempts before executing `normalize_label`, stores the result exactly once, and archives only terminal messages. Transient failures leave the message unarchived for redelivery. The configured maximum is three attempts with delays derived from 2, 4, and 8 seconds.

`SIGTERM` and `SIGINT` set a stop event. The main loop stops claiming messages and grants the current handler up to 20 seconds before exit; an unfinished message remains unarchived and becomes visible again.

- [ ] **Step 4: Run worker and workspace checks**

```powershell
uv run pytest packages/vendorlens-core/tests apps/api/tests apps/worker/tests -q
uv run ruff check packages apps
uv run ruff format --check packages apps
uv run mypy packages/vendorlens-core/src apps/api/src apps/worker/src
```

Expected: all commands pass.

- [ ] **Step 5: Commit the worker**

```powershell
git add pyproject.toml uv.lock apps/worker
git commit -m "feat: add durable example job worker"
```

## Task 6: Build the Next.js Foundation Page

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/next.config.ts`
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/vitest.config.ts`
- Create: `apps/web/src/app/layout.tsx`
- Create: `apps/web/src/app/page.tsx`
- Create: `apps/web/src/app/globals.css`
- Create: `apps/web/src/components/job-demo.tsx`
- Create: `apps/web/src/lib/api.ts`
- Create: `apps/web/src/lib/types.ts`
- Create: `apps/web/src/components/job-demo.test.tsx`
- Modify: `package.json`
- Modify: `pnpm-lock.yaml`

**Interfaces:**
- Consumes: `NEXT_PUBLIC_API_BASE_URL`, `POST /api/v1/example-jobs`, and the job status endpoint.
- Produces: accessible public page that explains the infrastructure-only scope and demonstrates one safe job end to end.

- [ ] **Step 1: Scaffold Next.js without overwriting repository files**

Create the app under `apps/web` with TypeScript, App Router, ESLint, `src/`, and no Tailwind dependency:

```powershell
pnpm create next-app@16.3.6 apps/web --ts --eslint --app --src-dir --no-tailwind --use-pnpm --import-alias "@/*"
pnpm --filter @vendorlens/web add -D vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event msw
```

Expected: the generated application uses Next.js 16.3.6 and the root lockfile records exact resolved versions.

- [ ] **Step 2: Write failing component tests**

```tsx
it("explains that the release is infrastructure scaffolding", () => {
  render(<Home />);
  expect(screen.getByText(/not a vendor-risk decision system/i)).toBeVisible();
});

it("submits and displays a completed example job", async () => {
  server.use(successfulJobHandlers());
  render(<JobDemo />);
  await userEvent.type(screen.getByLabelText(/example label/i), "VendorLens");
  await userEvent.click(screen.getByRole("button", { name: /run example job/i }));
  expect(await screen.findByText("VENDORLENS")).toBeVisible();
});

it("keeps a recoverable error visible", async () => {
  server.use(rateLimitedHandler());
  render(<JobDemo />);
  await submitExampleJob("VendorLens");
  expect(await screen.findByRole("alert")).toHaveTextContent(/try again later/i);
});
```

- [ ] **Step 3: Run tests to verify failure**

```powershell
pnpm --filter @vendorlens/web test
```

Expected: FAIL because the page and job component are not implemented.

- [ ] **Step 4: Implement the page and security headers**

The page contains a concise project purpose, architecture summary, current limitations, dependency status, and example-job panel. The job panel creates an idempotency key per deliberate submission, polls with a bounded 30-second deadline, stops on terminal status, and presents a retry action without automatically duplicating the job.

`next.config.ts` sets `Content-Security-Policy`, `Referrer-Policy`, `X-Content-Type-Options`, and `Permissions-Policy`; CSP `connect-src` includes only self and the configured API origin.

- [ ] **Step 5: Run frontend checks**

```powershell
pnpm --filter @vendorlens/web lint
pnpm --filter @vendorlens/web typecheck
pnpm --filter @vendorlens/web test
pnpm --filter @vendorlens/web build
```

Expected: all commands pass.

- [ ] **Step 6: Commit the frontend**

```powershell
git add apps/web package.json pnpm-lock.yaml
git commit -m "feat: add foundation web experience"
```

## Task 7: Add Containers and the Reproducible Local Stack

**Files:**
- Create: `infra/docker/api.Dockerfile`
- Create: `infra/docker/worker.Dockerfile`
- Create: `docker-compose.yml`
- Create: `scripts/dev.ps1`
- Create: `scripts/check.ps1`
- Create: `tests/smoke/local_smoke.py`
- Modify: `.env.example`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: locked Python/Node dependencies and local Supabase endpoints.
- Produces: reproducible API and worker images plus one local start/check workflow.

- [ ] **Step 1: Write the failing local smoke test**

```python
def test_local_stack_completes_example_job(http_client) -> None:
    assert http_client.get("/health/live").json() == {"status": "ok"}
    created = http_client.post(
        "/api/v1/example-jobs",
        headers={"Idempotency-Key": "local-smoke"},
        json={"label": "VendorLens"},
    )
    assert created.status_code == 202
    job_url = created.headers["location"]
    assert wait_for_terminal(http_client, job_url, timeout_seconds=30) == {
        "status": "succeeded",
        "result": "VENDORLENS",
    }
```

- [ ] **Step 2: Build minimal non-root containers**

Both Dockerfiles must use a Python 3.13 slim base, copy only required workspace manifests before dependency installation, use the lockfile with frozen installs, run as an unprivileged user, and use exec-form commands. The API listens on `$PORT`; the worker runs its module entrypoint.

- [ ] **Step 3: Compose the local application around Supabase**

`scripts/dev.ps1` starts local Supabase first, exports its local URLs/keys into the application environment, applies migrations, and starts web/API/worker. `docker-compose.yml` defines the application processes and uses health-based dependencies; it does not create a second PostgreSQL instance.

- [ ] **Step 4: Build and verify locally**

```powershell
docker build -f infra/docker/api.Dockerfile -t vendorlens-api:local .
docker build -f infra/docker/worker.Dockerfile -t vendorlens-worker:local .
pnpm dlx supabase@2.117.0 start
pnpm dlx supabase@2.117.0 db reset
docker compose up -d api worker
uv run pytest tests/smoke/local_smoke.py -q
docker compose down
```

Expected: both images build and the example job reaches `succeeded`.

- [ ] **Step 5: Commit local infrastructure**

```powershell
git add infra docker-compose.yml scripts tests/smoke .env.example .gitignore
git commit -m "build: add reproducible local infrastructure"
```

## Task 8: Add CI, Dependency Automation, and Deployment Manifests

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/dependabot.yml`
- Create: `infra/render.yaml`
- Create: `apps/web/vercel.json`
- Create: `tests/smoke/hosted_smoke.py`
- Create: `README.md`

**Interfaces:**
- Consumes: all workspace test/build commands and platform environment variables.
- Produces: required CI checks, Render Blueprint, Vercel root configuration, hosted smoke command, and operator documentation.

- [ ] **Step 1: Add CI with explicit jobs**

`ci.yml` starts with least-privilege repository permissions and the following executable job structure:

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: astral-sh/setup-uv@v6
        with:
          python-version: "3.13"
          enable-cache: true
      - run: uv sync --frozen --all-packages
      - run: uv run ruff check packages apps tests
      - run: uv run ruff format --check packages apps tests
      - run: uv run mypy packages/vendorlens-core/src apps/api/src apps/worker/src
      - run: uv run pytest packages/vendorlens-core/tests apps/api/tests apps/worker/tests -q
  web:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: pnpm/action-setup@v4
        with:
          version: 11.19.0
      - uses: actions/setup-node@v5
        with:
          node-version: "24"
          cache: pnpm
      - run: pnpm install --frozen-lockfile
      - run: pnpm lint
      - run: pnpm typecheck
      - run: pnpm test
      - run: pnpm build
  supabase:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: astral-sh/setup-uv@v6
        with:
          python-version: "3.13"
      - uses: supabase/setup-cli@v1
        with:
          version: 2.117.0
      - run: uv sync --frozen --all-packages
      - run: supabase start
      - run: supabase db reset
      - run: uv run pytest tests/integration/test_migration.py -q
  containers:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - run: docker build -f infra/docker/api.Dockerfile -t vendorlens-api:ci .
      - run: docker build -f infra/docker/worker.Dockerfile -t vendorlens-worker:ci .
```

Each job must use least-privilege `contents: read` permissions, pin official action major versions, and avoid production secrets.

- [ ] **Step 2: Add dependency automation**

Configure weekly Dependabot updates for `pip`, `npm`, `github-actions`, and both Dockerfiles. Limit open pull requests per ecosystem to five and group patch/minor development dependencies.

- [ ] **Step 3: Add Render Blueprint and Vercel configuration**

`infra/render.yaml` defines:

```yaml
services:
  - type: web
    name: vendorlens-api
    runtime: docker
    plan: free
    dockerfilePath: ./infra/docker/api.Dockerfile
    healthCheckPath: /health/live
  - type: worker
    name: vendorlens-worker
    runtime: docker
    plan: 0.5c-512mb
    dockerfilePath: ./infra/docker/worker.Dockerfile
```

Both services reference server-side environment variables without literal secret values. The API alone receives CORS settings; both receive database/queue settings. A single controlled API pre-deploy command applies database migrations.

`apps/web/vercel.json` pins the Next.js framework and security-compatible build behavior without duplicating secrets.

- [ ] **Step 4: Write complete operator documentation**

README sections are: purpose, honest limitations, architecture, repository map, prerequisites, local setup, environment variables, tests, GitHub CI, Supabase provisioning, Render deployment, Vercel deployment, smoke verification, monthly cost, troubleshooting, and data-safety boundary.

- [ ] **Step 5: Run the complete local verification suite**

```powershell
uv run ruff check packages apps tests
uv run ruff format --check packages apps tests
uv run mypy packages/vendorlens-core/src apps/api/src apps/worker/src
uv run pytest -q
pnpm lint
pnpm typecheck
pnpm test
pnpm build
docker build -f infra/docker/api.Dockerfile -t vendorlens-api:verify .
docker build -f infra/docker/worker.Dockerfile -t vendorlens-worker:verify .
```

Expected: all checks pass.

- [ ] **Step 6: Commit CI and deployment configuration**

```powershell
git add .github infra/render.yaml apps/web/vercel.json tests/smoke/hosted_smoke.py README.md
git commit -m "ci: add deployment and verification pipeline"
```

## Task 9: Create and Push the Public GitHub Repository

**Files:**
- Modify: local Git remote and GitHub repository settings, not tracked workspace files.

**Interfaces:**
- Consumes: verified local `main` branch and GitHub account `ALmcEX`.
- Produces: public repository `https://github.com/ALmcEX/VendorLens`, pushed history, Actions results, and branch protection.

- [ ] **Step 1: Prepare the GitHub new-repository form**

Open GitHub's repository creation page in the authenticated Chrome session. Set owner `ALmcEX`, name `VendorLens`, description `Evidence-bound review workflow for AI SaaS procurement`, visibility `Public`, and do not initialize README, `.gitignore`, or license because the local repository already contains history.

- [ ] **Step 2: Confirm before creating public content**

Immediately before clicking **Create repository**, request confirmation because this publishes a new public artifact under the user's account.

- [ ] **Step 3: Create the repository and push `main`**

```powershell
git remote add origin https://github.com/ALmcEX/VendorLens.git
git push -u origin main
```

Expected: GitHub displays the repository and the full local commit history.

- [ ] **Step 4: Verify Actions and configure branch protection**

Wait for the CI workflow to finish. After it is green, protect `main` by requiring pull requests and the Python, web, Supabase, and container checks. Request confirmation immediately before saving repository permission/protection changes.

- [ ] **Step 5: Record repository state**

```powershell
git remote -v
git status --short --branch
git log --oneline --decorate -5
```

Expected: `origin` points to the public repository, `main` tracks `origin/main`, and the working tree is clean.

## Task 10: Provision Supabase and Deploy Render and Vercel

**Files:**
- No secret-bearing files are created.
- Modify: provider project settings and environment variables through authenticated web interfaces.

**Interfaces:**
- Consumes: public GitHub repository, platform accounts, Render USD 7/month worker authorization, and environment-variable inventory from README.
- Produces: Supabase project, Render API/worker, Vercel frontend, and public deployment URLs.

- [ ] **Step 1: Create the Supabase Free project**

Create `vendorlens` in a US region on the Free plan. At the action that creates the project or exposes/copies persistent credentials, follow the computer-use confirmation policy. Apply migrations using a controlled local command or the provider SQL path, then verify the table, private bucket, and queue exist.

- [ ] **Step 2: Prepare Render Blueprint configuration**

Connect the public GitHub repository, select `infra/render.yaml`, configure the API as Free and the worker as `0.5c-512mb`, and enter server-side Supabase settings. Do not place any credential into GitHub, logs, chat, or tracked files.

- [ ] **Step 3: Confirm the paid worker immediately before purchase/deploy**

Request action-time confirmation that enabling the Render worker incurs approximately USD 7/month plus applicable tax. Only after confirmation, submit the Blueprint deployment.

- [ ] **Step 4: Verify Render services**

Wait for both deployments. Store the exact visible Render API URL in the process-scoped `VENDORLENS_API_URL` environment variable, then verify:

```powershell
Invoke-RestMethod "$env:VENDORLENS_API_URL/health/live"
Invoke-RestMethod "$env:VENDORLENS_API_URL/health/ready"
```

Expected: liveness returns `{"status":"ok"}`, readiness returns HTTP 200, and worker logs show startup without payloads or credentials.

- [ ] **Step 5: Deploy the Next.js app to Vercel Hobby**

Import `ALmcEX/VendorLens`, set root directory `apps/web`, keep the Hobby plan, and set `NEXT_PUBLIC_API_BASE_URL` to the verified Render API URL. Deploy and confirm the public page renders.

- [ ] **Step 6: Update Render CORS and run hosted smoke verification**

Store the exact visible Vercel production URL in the process-scoped `VENDORLENS_WEB_URL` environment variable, add that origin to Render's CORS environment variable, and redeploy the API. Run:

```powershell
uv run pytest tests/smoke/hosted_smoke.py -q
```

Expected: the page loads, health checks pass, and one example job reaches `succeeded` within 30 seconds.

- [ ] **Step 7: Document non-secret deployment outputs**

Update README with the verified Vercel and Render public URLs, the deployment date, the USD 7/month operating estimate, and the known free-tier sleep/pause behavior. Run the full verification suite, commit, and push:

```powershell
git add README.md
git commit -m "docs: add live deployment endpoints"
git push
```

## Final Verification

- [ ] Run every local unit, integration, build, and container check from Task 8.
- [ ] Confirm GitHub Actions is green on `main`.
- [ ] Confirm no tracked file contains provider credentials or rendered `.env` values.
- [ ] Confirm Vercel loads the foundation page over HTTPS.
- [ ] Confirm Render liveness/readiness respond without internal detail leakage.
- [ ] Confirm the hosted example job completes through the paid worker.
- [ ] Confirm duplicate idempotency submission does not create a second job.
- [ ] Confirm README states the product is infrastructure scaffolding, not a vendor-risk decision system.
- [ ] Confirm the provider billing views match the expected initial USD 7/month recurring compute charge before declaring completion.
