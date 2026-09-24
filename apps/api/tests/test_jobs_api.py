from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from vendorlens_api.main import create_app
from vendorlens_api.rate_limit import FixedWindowRateLimiter
from vendorlens_api.services.jobs import JobService
from vendorlens_core.jobs import ExampleJob, JobStatus


class InMemoryRepository:
    def __init__(self) -> None:
        self.jobs: dict[UUID, ExampleJob] = {}
        self.keys: dict[str, UUID] = {}
        self.create_count = 0

    async def create(
        self,
        *,
        idempotency_key: str,
        payload_hash: str,
        label: str,
    ) -> ExampleJob:
        del label
        self.create_count += 1
        job = ExampleJob(
            id=uuid4(),
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            status=JobStatus.QUEUED,
            attempt_count=0,
        )
        self.jobs[job.id] = job
        self.keys[idempotency_key] = job.id
        return job

    async def get(self, job_id: UUID) -> ExampleJob | None:
        return self.jobs.get(job_id)

    async def find_by_idempotency_key(self, idempotency_key: str) -> ExampleJob | None:
        job_id = self.keys.get(idempotency_key)
        return None if job_id is None else self.jobs[job_id]

    async def mark_failed(self, job_id: UUID, *, error_category: str) -> ExampleJob:
        failed = self.jobs[job_id].model_copy(
            update={"status": JobStatus.FAILED, "error_category": error_category}
        )
        self.jobs[job_id] = failed
        return failed


class InMemoryQueue:
    def __init__(self, *, depth: int = 0, fail_publish: bool = False) -> None:
        self.current_depth = depth
        self.fail_publish = fail_publish
        self.published: list[UUID] = []

    async def depth(self) -> int:
        return self.current_depth

    async def publish(self, *, job_id: UUID) -> None:
        if self.fail_publish:
            raise RuntimeError("queue credentials must not be exposed")
        self.published.append(job_id)


def build_service(
    repository: InMemoryRepository,
    queue: InMemoryQueue,
    *,
    request_limit: int = 5,
    queue_depth_limit: int = 100,
) -> JobService:
    return JobService(
        repository=repository,
        queue=queue,
        rate_limiter=FixedWindowRateLimiter(limit=request_limit, window_seconds=60),
        queue_depth_limit=queue_depth_limit,
    )


@pytest.mark.asyncio
async def test_duplicate_key_with_different_payload_returns_409() -> None:
    repository = InMemoryRepository()
    queue = InMemoryQueue()
    app = create_app(job_service=build_service(repository, queue))
    headers = {"Idempotency-Key": "stable-key"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/api/v1/example-jobs", json={"label": "first"}, headers=headers)
        response = await client.post(
            "/api/v1/example-jobs", json={"label": "second"}, headers=headers
        )

    assert first.status_code == 202
    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    assert len(queue.published) == 1


@pytest.mark.asyncio
async def test_duplicate_key_with_same_payload_returns_existing_job() -> None:
    repository = InMemoryRepository()
    queue = InMemoryQueue()
    app = create_app(job_service=build_service(repository, queue))
    headers = {"Idempotency-Key": "stable-key"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post(
            "/api/v1/example-jobs", json={"label": "VendorLens"}, headers=headers
        )
        second = await client.post(
            "/api/v1/example-jobs", json={"label": " VendorLens "}, headers=headers
        )

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    assert len(queue.published) == 1


@pytest.mark.asyncio
async def test_oversized_label_returns_problem_details_without_enqueueing() -> None:
    repository = InMemoryRepository()
    queue = InMemoryQueue()
    app = create_app(job_service=build_service(repository, queue))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/example-jobs", json={"label": "界" * 101})

    assert response.status_code == 422
    assert response.json()["status"] == 422
    assert queue.published == []


@pytest.mark.asyncio
async def test_rate_limit_rejects_before_second_persistence() -> None:
    repository = InMemoryRepository()
    queue = InMemoryQueue()
    app = create_app(job_service=build_service(repository, queue, request_limit=1))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/api/v1/example-jobs", json={"label": "first"})
        response = await client.post("/api/v1/example-jobs", json={"label": "second"})

    assert first.status_code == 202
    assert response.status_code == 429
    assert repository.create_count == 1


@pytest.mark.asyncio
async def test_queue_depth_guard_rejects_before_persistence() -> None:
    repository = InMemoryRepository()
    queue = InMemoryQueue(depth=100)
    app = create_app(job_service=build_service(repository, queue))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/example-jobs", json={"label": "safe"})

    assert response.status_code == 429
    assert repository.create_count == 0


@pytest.mark.asyncio
async def test_publish_failure_marks_job_failed_and_hides_internal_detail() -> None:
    repository = InMemoryRepository()
    queue = InMemoryQueue(fail_publish=True)
    app = create_app(job_service=build_service(repository, queue))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/example-jobs", json={"label": "safe"})

    assert response.status_code == 503
    assert "credentials" not in response.text
    assert next(iter(repository.jobs.values())).status is JobStatus.FAILED


@pytest.mark.asyncio
async def test_status_endpoint_returns_created_job() -> None:
    repository = InMemoryRepository()
    queue = InMemoryQueue()
    app = create_app(job_service=build_service(repository, queue))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/v1/example-jobs", json={"label": "VendorLens"})
        response = await client.get(created.headers["location"])

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
