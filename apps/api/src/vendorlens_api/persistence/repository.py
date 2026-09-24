from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vendorlens_api.persistence.models import ExampleJobRecord
from vendorlens_core.jobs import ExampleJob, JobStatus


class ExampleJobRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(
        self,
        *,
        idempotency_key: str,
        payload_hash: str,
        label: str,
    ) -> ExampleJob:
        record = ExampleJobRecord(
            id=uuid4(),
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            label=label,
            status=JobStatus.QUEUED.value,
            attempt_count=0,
        )
        async with self._session_factory() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
        return self._to_domain(record)

    async def get(self, job_id: UUID) -> ExampleJob | None:
        async with self._session_factory() as session:
            record = await session.get(ExampleJobRecord, job_id)
        return None if record is None else self._to_domain(record)

    async def find_by_idempotency_key(self, idempotency_key: str) -> ExampleJob | None:
        async with self._session_factory() as session:
            record = await session.scalar(
                select(ExampleJobRecord).where(ExampleJobRecord.idempotency_key == idempotency_key)
            )
        return None if record is None else self._to_domain(record)

    async def mark_failed(self, job_id: UUID, *, error_category: str) -> ExampleJob:
        async with self._session_factory() as session:
            record = await session.get(ExampleJobRecord, job_id)
            if record is None:
                raise LookupError(f"example job {job_id} does not exist")
            record.status = JobStatus.FAILED.value
            record.error_category = error_category
            record.completed_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(record)
        return self._to_domain(record)

    @staticmethod
    def _to_domain(record: ExampleJobRecord) -> ExampleJob:
        return ExampleJob(
            id=record.id,
            idempotency_key=record.idempotency_key,
            payload_hash=record.payload_hash,
            status=JobStatus(record.status),
            attempt_count=record.attempt_count,
            result=record.result,
            error_category=record.error_category,
        )
