from __future__ import annotations

from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from vendorlens_core.jobs import JobStatus, normalize_label
from vendorlens_worker.queue import QueueMessage


class WorkerJob(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    label: str
    status: JobStatus
    attempt_count: int = Field(ge=0)
    result: str | None = None
    error_category: str | None = None


class JobRepository(Protocol):
    async def get(self, job_id: UUID) -> WorkerJob | None: ...

    async def start_attempt(self, job_id: UUID) -> WorkerJob: ...

    async def mark_queued(self, job_id: UUID) -> WorkerJob: ...

    async def mark_succeeded(self, job_id: UUID, *, result: str) -> WorkerJob: ...

    async def mark_failed(self, job_id: UUID, *, error_category: str) -> WorkerJob: ...


class JobQueue(Protocol):
    async def archive(self, message_id: int) -> None: ...

    async def retry(self, message_id: int, *, delay_seconds: int) -> None: ...


class JobOperation(Protocol):
    async def execute(self, label: str) -> str: ...


class NormalizeLabelOperation:
    async def execute(self, label: str) -> str:
        return normalize_label(label)


class JobProcessor:
    def __init__(
        self,
        repository: JobRepository,
        queue: JobQueue,
        operation: JobOperation,
        *,
        max_attempts: int,
    ) -> None:
        self._repository = repository
        self._queue = queue
        self._operation = operation
        self._max_attempts = max_attempts

    async def process(self, message: QueueMessage) -> None:
        job = await self._repository.get(message.job_id)
        if job is None or job.status in {JobStatus.SUCCEEDED, JobStatus.FAILED}:
            await self._queue.archive(message.message_id)
            return

        active_job = await self._repository.start_attempt(job.id)
        try:
            result = await self._operation.execute(active_job.label)
        except Exception:
            if active_job.attempt_count >= self._max_attempts:
                await self._repository.mark_failed(
                    active_job.id,
                    error_category="processing_failed",
                )
                await self._queue.archive(message.message_id)
            else:
                await self._repository.mark_queued(active_job.id)
                await self._queue.retry(
                    message.message_id,
                    delay_seconds=min(2**active_job.attempt_count, 8),
                )
            return

        await self._repository.mark_succeeded(active_job.id, result=result)
        await self._queue.archive(message.message_id)
