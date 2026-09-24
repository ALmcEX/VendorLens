from __future__ import annotations

from typing import Protocol
from uuid import UUID

from vendorlens_core.jobs import ExampleJob, ExampleJobPayload, payload_fingerprint


class JobRepository(Protocol):
    async def create(
        self,
        *,
        idempotency_key: str,
        payload_hash: str,
        label: str,
    ) -> ExampleJob: ...

    async def get(self, job_id: UUID) -> ExampleJob | None: ...

    async def find_by_idempotency_key(self, idempotency_key: str) -> ExampleJob | None: ...

    async def mark_failed(self, job_id: UUID, *, error_category: str) -> ExampleJob: ...


class JobQueue(Protocol):
    async def depth(self) -> int: ...

    async def publish(self, *, job_id: UUID) -> None: ...


class RateLimiter(Protocol):
    async def allow(self, key: str) -> bool: ...


class JobServiceError(Exception):
    pass


class IdempotencyConflict(JobServiceError):
    pass


class RateLimitExceeded(JobServiceError):
    pass


class QueueSaturated(JobServiceError):
    pass


class EnqueueUnavailable(JobServiceError):
    pass


class JobNotFound(JobServiceError):
    pass


class JobServiceUnavailable(JobServiceError):
    pass


class JobOperations(Protocol):
    async def submit(
        self,
        *,
        payload: ExampleJobPayload,
        idempotency_key: str,
        client_id: str,
    ) -> ExampleJob: ...

    async def get(self, job_id: UUID) -> ExampleJob: ...


class JobService:
    def __init__(
        self,
        *,
        repository: JobRepository,
        queue: JobQueue,
        rate_limiter: RateLimiter,
        queue_depth_limit: int,
    ) -> None:
        self._repository = repository
        self._queue = queue
        self._rate_limiter = rate_limiter
        self._queue_depth_limit = queue_depth_limit

    async def submit(
        self,
        *,
        payload: ExampleJobPayload,
        idempotency_key: str,
        client_id: str,
    ) -> ExampleJob:
        if not await self._rate_limiter.allow(client_id):
            raise RateLimitExceeded
        if await self._queue.depth() >= self._queue_depth_limit:
            raise QueueSaturated

        payload_hash = payload_fingerprint(payload)
        existing = await self._repository.find_by_idempotency_key(idempotency_key)
        if existing is not None:
            if existing.payload_hash != payload_hash:
                raise IdempotencyConflict
            return existing

        job = await self._repository.create(
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            label=payload.label,
        )
        try:
            await self._queue.publish(job_id=job.id)
        except Exception as exception:
            await self._repository.mark_failed(job.id, error_category="enqueue_failed")
            raise EnqueueUnavailable from exception
        return job

    async def get(self, job_id: UUID) -> ExampleJob:
        job = await self._repository.get(job_id)
        if job is None:
            raise JobNotFound
        return job


class UnavailableJobService:
    async def submit(
        self,
        *,
        payload: ExampleJobPayload,
        idempotency_key: str,
        client_id: str,
    ) -> ExampleJob:
        del payload, idempotency_key, client_id
        raise JobServiceUnavailable

    async def get(self, job_id: UUID) -> ExampleJob:
        del job_id
        raise JobServiceUnavailable
