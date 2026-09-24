from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest

from vendorlens_core.jobs import JobStatus
from vendorlens_worker.main import Worker
from vendorlens_worker.processor import JobProcessor, WorkerJob
from vendorlens_worker.queue import QueueMessage


class BlockingOperation:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def execute(self, label: str) -> str:
        self.started.set()
        await self.release.wait()
        return label.upper()


class Repository:
    def __init__(self, job: WorkerJob) -> None:
        self.job = job

    async def get(self, job_id: UUID) -> WorkerJob | None:
        return self.job if self.job.id == job_id else None

    async def start_attempt(self, job_id: UUID) -> WorkerJob:
        self.job = self.job.model_copy(
            update={"status": JobStatus.RUNNING, "attempt_count": self.job.attempt_count + 1}
        )
        return self.job

    async def mark_queued(self, job_id: UUID) -> WorkerJob:
        self.job = self.job.model_copy(update={"status": JobStatus.QUEUED})
        return self.job

    async def mark_succeeded(self, job_id: UUID, *, result: str) -> WorkerJob:
        self.job = self.job.model_copy(update={"status": JobStatus.SUCCEEDED, "result": result})
        return self.job

    async def mark_failed(self, job_id: UUID, *, error_category: str) -> WorkerJob:
        self.job = self.job.model_copy(
            update={"status": JobStatus.FAILED, "error_category": error_category}
        )
        return self.job


class Queue:
    def __init__(self, message: QueueMessage | None) -> None:
        self.message = message
        self.archived: list[int] = []

    async def claim(self) -> QueueMessage | None:
        message, self.message = self.message, None
        return message

    async def archive(self, message_id: int) -> None:
        self.archived.append(message_id)

    async def retry(self, message_id: int, *, delay_seconds: int) -> None:
        del message_id, delay_seconds


@pytest.mark.asyncio
async def test_interrupted_work_remains_unarchived_for_redelivery() -> None:
    job = WorkerJob(
        id=uuid4(),
        label="VendorLens",
        status=JobStatus.QUEUED,
        attempt_count=0,
    )
    queue = Queue(QueueMessage(message_id=8, read_count=1, job_id=job.id))
    operation = BlockingOperation()
    processor = JobProcessor(Repository(job), queue, operation, max_attempts=3)
    worker = Worker(queue, processor, poll_interval_seconds=0.01, shutdown_grace_seconds=0.01)
    stop_event = asyncio.Event()
    task = asyncio.create_task(worker.run(stop_event))

    await operation.started.wait()
    stop_event.set()
    await asyncio.wait_for(task, timeout=1)

    assert queue.archived == []


@pytest.mark.asyncio
async def test_run_once_reports_when_no_message_is_available() -> None:
    job = WorkerJob(id=uuid4(), label="VendorLens", status=JobStatus.QUEUED, attempt_count=0)
    queue = Queue(None)
    processor = JobProcessor(Repository(job), queue, BlockingOperation(), max_attempts=3)
    worker = Worker(queue, processor, poll_interval_seconds=0.01, shutdown_grace_seconds=0.01)

    assert await worker.run_once() is False
