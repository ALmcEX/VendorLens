# VendorLens Foundation and Deployment Design

**Date:** 2026-09-23  
**Status:** Approved  
**Source brief:** `VendorLens_Full_Project_Outline.md`, supplied separately by the project owner

## 1. Purpose

VendorLens is a production-style prototype for Security and Privacy reviewers performing pre-purchase evidence reviews of AI SaaS products. The first delivery establishes a public, deployable engineering foundation without prematurely implementing document ingestion, claim extraction, control assessment, or reviewer workflows.

The foundation succeeds when a public web application, API, background worker, durable queue, PostgreSQL database, and object-storage connection operate as one observable system from a public GitHub monorepo.

## 2. Goals

- Create a public GitHub repository named `VendorLens`.
- Establish a monorepo for a Next.js frontend, FastAPI API, Python worker, shared domain package, controls, evaluations, documentation, and infrastructure.
- Provide equivalent local and hosted development paths.
- Deploy the frontend to Vercel, the API and worker to Render, and data services to Supabase.
- Verify the full asynchronous path with a non-sensitive example job.
- Enforce formatting, linting, typing, tests, builds, and secret safety in CI.
- Keep the initial recurring infrastructure cost near USD 7 per month, excluding taxes, a custom domain, and model API usage.

## 3. Non-goals

This foundation does not implement:

- Vendor-document upload or parsing.
- LLM calls, prompts, claim extraction, or citation validation.
- Control applicability or assessment logic.
- Potential-conflict detection.
- Authentication, multi-tenancy, or role-based access control.
- Vendor approval, rejection, legal conclusions, or automated communications.
- A Redis service, microservices, Kubernetes, or a graph database.
- Production handling of sensitive or confidential documents.

No document-upload endpoint will be exposed until authentication, authorization, file validation, and untrusted-content processing have their own approved design.

## 4. Selected Architecture

The project uses one public monorepo and three deployable processes:

```text
GitHub: public VendorLens monorepo
│
├── Next.js web application ───────────────> Vercel Hobby
├── FastAPI HTTP API ──────────────────────> Render free web service
├── Python queue worker ───────────────────> Render 0.5c-512mb worker
└── migrations and service configuration ─> Supabase Free
                                                ├── PostgreSQL
                                                ├── Storage
                                                └── Postgres-native Queue
```

Vercel is selected because it directly supports Next.js monorepo deployments. Render is selected because its Blueprint configuration expresses separate API and worker processes in source control. Supabase provides PostgreSQL, S3-compatible object storage, and a durable Postgres-native queue without introducing a separate Redis service.

The initial hosted tier costs approximately USD 7 per month:

| Service | Initial tier | Monthly cost |
|---|---|---:|
| GitHub public repository and standard Actions runners | Free | $0 |
| Vercel frontend | Hobby | $0 |
| Render API | Free | $0 |
| Render worker | 0.5c-512mb | $7 |
| Supabase database, storage, and queue | Free | $0 |
| **Total** | | **$7** |

The Render API can sleep after 15 minutes of inactivity, and the Supabase project can pause after one week of inactivity. A later always-on portfolio tier upgrades the Render API to USD 7 per month and Supabase to Pro at USD 25 per month, producing an estimated USD 39 monthly total while Vercel remains on Hobby.

## 5. Technology Constraints

- Python 3.13 for backend and shared Python packages.
- FastAPI with Pydantic for API validation and response contracts.
- SQLAlchemy and Alembic for database access and migrations.
- `uv` for Python dependency and workspace management.
- Node.js 24 LTS for frontend tooling.
- Next.js 16 with the App Router and TypeScript.
- `pnpm` for JavaScript dependency and workspace management.
- PostgreSQL as the system of record.
- Supabase Storage for opaque object storage behind a server-side interface.
- Supabase Queues, backed by `pgmq`, for durable asynchronous work.
- Docker and the Supabase CLI for local dependencies.
- GitHub Actions for continuous integration.
- Dependabot for supported dependency update automation.

Patch releases are locked in dependency lockfiles. Automated dependency updates must preserve tests and production builds before merging.

## 6. Repository Structure

```text
VendorLens/
├── apps/
│   ├── web/                         # Next.js application deployed to Vercel
│   ├── api/                         # FastAPI process deployed to Render
│   └── worker/                      # Queue consumer deployed to Render
├── packages/
│   └── vendorlens-core/             # Shared domain types and deterministic rules
├── supabase/
│   └── migrations/                  # Database, storage, and queue migrations
├── controls/                        # Versioned control-set data
├── evals/                           # Dataset, runner, and report scaffolding
├── tests/                           # Cross-process integration and smoke tests
├── docs/
│   ├── adr/
│   ├── failure-analysis/
│   ├── research/
│   ├── retrospectives/
│   └── superpowers/                 # Approved specs and implementation plans
├── infra/
│   ├── docker/                      # Runtime container definitions
│   └── render.yaml                  # Render Blueprint
├── .github/
│   └── workflows/                   # CI workflows
├── docker-compose.yml               # Local application orchestration
├── .env.example                     # Names only; never real credentials
└── README.md                        # Setup, architecture, deployment, and limits
```

The API and worker depend on `vendorlens-core`; they do not depend directly on each other. The shared package contains domain and configuration-independent logic only. Platform adapters for HTTP, queues, databases, and storage remain inside their owning application or a narrowly scoped adapter package introduced by a later approved design.

## 7. Initial Interfaces

### 7.1 HTTP endpoints

- `GET /health/live` reports whether the API process is running. It performs no network calls.
- `GET /health/ready` verifies database, queue, and object-storage configuration and connectivity using bounded timeouts.
- `POST /api/v1/example-jobs` validates a non-sensitive example payload, persists job metadata, and enqueues one durable message.
- `GET /api/v1/example-jobs/{job_id}` returns the current state of an example job.

HTTP errors use `application/problem+json` with stable fields for `type`, `title`, `status`, `detail`, `instance`, and `request_id`. Internal exception messages and credentials are never returned.

The example label is limited to 100 Unicode characters. The API applies a conservative per-client fixed-window rate limit and rejects new jobs with HTTP 429 when the limit or a configured queue-depth guard is exceeded. Proxy-derived client addresses are trusted only from the configured hosting proxy path.

### 7.2 Example job contract

The example job exists only to validate the foundation. It accepts a short label and produces a normalized uppercase result. It contains no vendor document, personal data, or model call.

Each job records:

- UUID job identifier.
- Caller-provided or server-generated idempotency key.
- Status: `queued`, `running`, `succeeded`, or `failed`.
- Attempt count.
- Created, started, and completed timestamps.
- Safe error category when failed.
- Result when succeeded.

Submitting the same idempotency key with the same payload returns the existing job. Reusing it with a different payload returns HTTP 409.

### 7.3 Queue behavior

The API writes job metadata and enqueues a message after the metadata transaction succeeds. The worker claims messages with a visibility window, transitions the matching job to `running`, and completes idempotently. Successful messages are archived. Transient failures use bounded exponential backoff. After the configured maximum attempt count, the worker marks the job `failed` and archives the message with a safe error category.

If the metadata write succeeds but enqueueing fails, the API reports service unavailability, marks the job `failed`, and records `enqueue_failed` as its safe error category so it cannot appear silently queued. A later reliability iteration may add a transactional outbox after measurement demonstrates that it is necessary.

## 8. Runtime Data Flow

```text
Browser
  → Next.js page
  → FastAPI /api/v1/example-jobs
  → schema and idempotency validation
  → PostgreSQL job metadata
  → Supabase Queue message
  → Render worker claim
  → deterministic example operation
  → PostgreSQL result/status
  → message archive
  → browser status refresh
```

The frontend receives the public API base URL at build/runtime configuration. The API and worker receive database, storage, and queue credentials through server-side environment variables. Browser bundles never receive Supabase service-role credentials or direct queue access.

## 9. Configuration and Secrets

- Local development uses `.env` files ignored by Git; `.env.example` contains variable names and safe descriptions only.
- Vercel stores frontend-safe environment variables.
- Render stores API and worker server-side variables, preferably in a shared environment group.
- Supabase owns database, storage, and queue credentials.
- Production and preview origins are explicit CORS allowlist entries.
- Startup validation fails fast for missing or malformed mandatory configuration.
- Logs redact values whose names indicate tokens, secrets, passwords, keys, cookies, authorization headers, database URLs, or service-role credentials.

## 10. Security Boundary

- All future vendor content is treated as untrusted data, never as instructions.
- The worker has no approval, purchasing, email-sending, or repository-write capability.
- The initial deployment accepts no files and stores no sensitive content.
- HTTPS is provided by the hosting platforms.
- The frontend sets a restrictive Content Security Policy and standard security headers compatible with Vercel and the configured API origin.
- The API restricts CORS to configured local, preview, and production origins.
- Database and storage access use server-side credentials with the narrowest practical privileges.
- Structured logs contain identifiers and classifications, not raw request bodies or document content.
- CI runs dependency and secret checks appropriate for a public repository.

## 11. Observability and Failure Handling

- Every HTTP request receives or generates a request ID, returned in the response and included in structured logs.
- Every example job has a job ID and idempotency key; worker logs include the job ID but not the payload.
- Readiness checks use bounded timeouts and report dependency categories without leaking endpoints or credentials.
- Expected external failures map to stable categories such as `database_unavailable`, `queue_unavailable`, and `storage_unavailable`.
- Unexpected errors produce a generic client response and a structured server log with stack information.
- Worker shutdown stops claiming new work and allows an in-flight job a bounded grace period before the visibility window permits redelivery.

## 12. Local Development

The supported local path provides:

- Next.js development server.
- FastAPI development server.
- Worker process.
- Local Supabase services for PostgreSQL, Storage, and Queue.
- A Docker Compose entrypoint or documented wrapper commands that start the application processes consistently.

The README contains exact prerequisites, setup commands, environment-variable descriptions, migration commands, test commands, and teardown commands. Local setup must not require a paid cloud account.

## 13. CI and Deployment

Pull requests and pushes to `main` run:

- Python formatting and lint checks.
- Python static type checks.
- Python unit and integration tests.
- Frontend lint and TypeScript checks.
- Frontend unit tests.
- Next.js production build.
- Database migration validation.
- Container build validation for the API and worker.
- Secret scanning and dependency review where supported for a public repository.

Branch protection requires the pull-request CI checks before changes enter `main`. After a merge to `main`, the connected platforms run their own builds and deployments:

- Vercel builds `apps/web` from the monorepo and deploys it.
- Render applies the repository Blueprint and deploys the API and worker.
- Database migrations run through one controlled pre-deploy path, not concurrently in both API and worker.
- A smoke test verifies the web page, API liveness/readiness, and the end-to-end example job.

Failed CI prevents a merge under the intended branch-protection configuration. Failed platform deployment leaves the last successful deployment serving traffic.

## 14. Test Strategy

- `vendorlens-core`: pure unit tests with no network dependencies.
- API: configuration, health, Problem Details, validation, rate limiting, queue-depth protection, idempotency, enqueue failure, and status endpoint tests.
- Worker: claim, success, retry, maximum-attempt failure, message redelivery, and idempotent reprocessing tests.
- Database: migration-up validation and repository integration tests against ephemeral PostgreSQL/Supabase services.
- Frontend: Vitest and Testing Library tests for the landing page, dependency-state display, example-job submission, pending state, success, and recoverable error state.
- Hosted smoke: Playwright or a small HTTP smoke suite checks the deployed web and API and waits for an example job to complete within a bounded timeout.

Tests must explicitly cover malformed and oversized example payloads, rate-limit exhaustion, queue saturation, duplicate idempotency keys with different payloads, unavailable dependencies, duplicate message delivery, and a worker interruption during processing.

## 15. Acceptance Criteria

The foundation is complete only when:

1. The public `VendorLens` GitHub repository exists and contains no credentials.
2. CI is green on the default branch.
3. The Vercel URL serves the VendorLens foundation page.
4. The Render API liveness and readiness endpoints respond as designed.
5. Supabase migrations create the required example-job and queue resources.
6. A job submitted through the public application is processed by the Render worker and reaches `succeeded`.
7. Repeating a request with the same idempotency key does not duplicate work.
8. A simulated processing failure follows the bounded retry policy and becomes inspectably failed.
9. The README enables a new developer to run the system locally and explains hosted cost and limitations.
10. The project explicitly states that the current release is infrastructure scaffolding, not a vendor-risk decision system.

## 16. Rollout and Cost Controls

- Start with Vercel Hobby, a Render free API service, one USD 7 Render worker, and Supabase Free.
- Set provider spend limits or alerts where available.
- Do not add a custom domain during the foundation phase.
- Do not enable paid model APIs during the foundation phase.
- Upgrade the Render API and Supabase only when public-demo reliability justifies the estimated USD 39 monthly tier.
- Record any pricing or hosting change in an ADR because it changes operating assumptions.

## 17. Deferred Decisions

The following decisions are deliberately deferred to later, separately approved designs because the foundation does not need them:

- Authentication provider and reviewer authorization model.
- Production document upload limits and malware/content controls.
- LLM provider, model, prompt contract, and cost budget.
- Claim and evidence persistence schema beyond the supplied project outline.
- Evaluation dataset licensing and storage policy.
- Custom domain and permanent paid hosting tier.

These are scoped deferrals, not missing requirements for the foundation described here.
