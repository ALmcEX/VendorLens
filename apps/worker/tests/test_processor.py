from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest

from vendorlens_core.jobs import JobStatus
from vendorlens_worker.processor import JobProcessor, WorkerJob
from vendorlens_worker.queue import QueueMessage


class InMemoryRepository:
    def __init__(self, job: WorkerJob | None) -> None:
        self.job = job
        self.result_write_count = 0

    async def get(self, job_id: UUID) -> WorkerJob | None:
        if self.job is None or self.job.id != job_id:
            return None
        return self.job

    async def start_attempt(self, job_id: UUID) -> WorkerJob:
        assert self.job is not None and self.job.id == job_id
        self.job = self.job.model_copy(
            update={"status": JobStatus.RUNNING, "attempt_count": self.job.attempt_count + 1}
        )
        return self.job

    async def mark_queued(self, job_id: UUID) -> WorkerJob:
        assert self.job is not None and self.job.id == job_id
        self.job = self.job.model_copy(update={"status": JobStatus.QUEUED})
        return self.job

    async def mark_succeeded(self, job_id: UUID, *, result: str) -> WorkerJob:
        assert self.job is not None and self.job.id == job_id
        self.result_write_count += 1
        self.job = self.job.model_copy(update={"status": JobStatus.SUCCEEDED, "result": result})
        return self.job

    async def mark_failed(self, job_id: UUID, *, error_category: str) -> WorkerJob:
        assert self.job is not None and self.job.id == job_id
        self.job = self.job.model_copy(
            update={"status": JobStatus.FAILED, "error_category": error_category}
        )
        return self.job


class InMemoryQueue:
    def __init__(self) -> None:
        self.archived: list[int] = []
        self.retried: list[tuple[int, int]] = []

    async def archive(self, message_id: int) -> None:
        self.archived.append(message_id)

    async def retry(self, message_id: int, *, delay_seconds: int) -> None:
        self.retried.append((message_id, delay_seconds))


class FakeOperation:
    def __init__(self) -> None:
        self.raise_error: Exception | None = None
        self.calls = 0
        self.started = asyncio.Event()

    async def execute(self, label: str) -> str:
        self.calls += 1
        self.started.set()
        if self.raise_error is not None:
            raise self.raise_error
        return label.upper()


def build_job(*, status: JobStatus = JobStatus.QUEUED, attempt_count: int = 0) -> WorkerJob:
    return WorkerJob(
        id=uuid4(),
        label="VendorLens",
        status=status,
        attempt_count=attempt_count,
    )


def build_message(job: WorkerJob, *, read_count: int = 1) -> QueueMessage:
    return QueueMessage(message_id=41, read_count=read_count, job_id=job.id)


@pytest.mark.asyncio
async def test_duplicate_delivery_does_not_repeat_completed_work() -> None:
    job = build_job(status=JobStatus.SUCCEEDED)
    repository = InMemoryRepository(job)
    queue = InMemoryQueue()
    operation = FakeOperation()
    processor = JobProcessor(repository, queue, operation, max_attempts=3)

    await processor.process(build_message(job))

    assert repository.result_write_count == 0
    assert operation.calls == 0
    assert queue.archived == [41]


@pytest.mark.asyncio
async def test_transient_failure_leaves_message_for_redelivery() -> None:
    job = build_job()
    repository = InMemoryRepository(job)
    queue = InMemoryQueue()
    operation = FakeOperation()
    operation.raise_error = TimeoutError("temporary")
    processor = JobProcessor(repository, queue, operation, max_attempts=3)

    await processor.process(build_message(job))

    updated = await repository.get(job.id)
    assert updated is not None and updated.status is JobStatus.QUEUED
    assert updated.attempt_count == 1
    assert queue.archived == []
    assert queue.retried == [(41, 2)]


@pytest.mark.asyncio
async def test_max_attempt_failure_is_inspectable() -> None:
    job = build_job(attempt_count=2)
    repository = InMemoryRepository(job)
    queue = InMemoryQueue()
    operation = FakeOperation()
    operation.raise_error = ValueError("permanent details must remain private")
    processor = JobProcessor(repository, queue, operation, max_attempts=3)

    await processor.process(build_message(job, read_count=3))

    failed = await repository.get(job.id)
    assert failed is not None and failed.status is JobStatus.FAILED
    assert failed.error_category == "processing_failed"
    assert queue.archived == [41]


@pytest.mark.asyncio
async def test_success_is_persisted_before_message_is_archived() -> None:
    job = build_job()
    repository = InMemoryRepository(job)
    queue = InMemoryQueue()
    processor = JobProcessor(repository, queue, FakeOperation(), max_attempts=3)

    await processor.process(build_message(job))

    succeeded = await repository.get(job.id)
    assert succeeded is not None and succeeded.status is JobStatus.SUCCEEDED
    assert succeeded.result == "VENDORLENS"
    assert queue.archived == [41]


@pytest.mark.asyncio
async def test_missing_job_message_is_archived_as_poison_work() -> None:
    repository = InMemoryRepository(None)
    queue = InMemoryQueue()
    processor = JobProcessor(repository, queue, FakeOperation(), max_attempts=3)
    message = QueueMessage(message_id=41, read_count=1, job_id=uuid4())

    await processor.process(message)

    assert queue.archived == [41]
