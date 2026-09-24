from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vendorlens_core.jobs import JobStatus
from vendorlens_worker.processor import WorkerJob


class WorkerRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get(self, job_id: UUID) -> WorkerJob | None:
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    "select id, label, status, attempt_count, result, error_category "
                    "from public.example_jobs where id = :job_id"
                ),
                {"job_id": job_id},
            )
            row = result.mappings().first()
        return None if row is None else self._to_domain(row)

    async def start_attempt(self, job_id: UUID) -> WorkerJob:
        return await self._transition(
            "update public.example_jobs "
            "set status = 'running', attempt_count = attempt_count + 1, "
            "started_at = :now, completed_at = null, error_category = null "
            "where id = :job_id and status in ('queued', 'running') "
            "returning id, label, status, attempt_count, result, error_category",
            job_id,
        )

    async def mark_queued(self, job_id: UUID) -> WorkerJob:
        return await self._transition(
            "update public.example_jobs set status = 'queued' "
            "where id = :job_id and status = 'running' "
            "returning id, label, status, attempt_count, result, error_category",
            job_id,
        )

    async def mark_succeeded(self, job_id: UUID, *, result: str) -> WorkerJob:
        return await self._transition(
            "update public.example_jobs "
            "set status = 'succeeded', result = :result, completed_at = :now, "
            "error_category = null "
            "where id = :job_id and status = 'running' "
            "returning id, label, status, attempt_count, result, error_category",
            job_id,
            result=result,
        )

    async def mark_failed(self, job_id: UUID, *, error_category: str) -> WorkerJob:
        return await self._transition(
            "update public.example_jobs "
            "set status = 'failed', error_category = :error_category, completed_at = :now "
            "where id = :job_id and status = 'running' "
            "returning id, label, status, attempt_count, result, error_category",
            job_id,
            error_category=error_category,
        )

    async def _transition(self, sql: str, job_id: UUID, **values: Any) -> WorkerJob:
        parameters = {"job_id": job_id, "now": datetime.now(UTC), **values}
        async with self._session_factory() as session:
            result = await session.execute(text(sql), parameters)
            row = result.mappings().first()
            if row is None:
                await session.rollback()
                raise LookupError(f"job {job_id} could not transition")
            await session.commit()
        return self._to_domain(row)

    @staticmethod
    def _to_domain(row: RowMapping) -> WorkerJob:
        return WorkerJob(
            id=UUID(str(row["id"])),
            label=str(row["label"]),
            status=JobStatus(str(row["status"])),
            attempt_count=int(row["attempt_count"]),
            result=None if row["result"] is None else str(row["result"]),
            error_category=(None if row["error_category"] is None else str(row["error_category"])),
        )
