from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import Field, SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from vendorlens_api.config import Settings
from vendorlens_api.infrastructure.queue import QueuePublisher
from vendorlens_api.infrastructure.storage import StorageProbe
from vendorlens_api.main import create_app
from vendorlens_api.persistence.repository import ExampleJobRepository
from vendorlens_api.rate_limit import FixedWindowRateLimiter
from vendorlens_api.services.jobs import JobService


class RuntimeSettings(Settings):
    database_url: str = Field(min_length=1)
    supabase_url: str = Field(min_length=1)
    supabase_service_role_key: SecretStr
    storage_bucket: str = "vendor-documents"
    queue_name: str = "example_jobs"


class EngineExecutor:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def execute(self, statement: Any, parameters: dict[str, Any]) -> Any:
        async with self._engine.begin() as connection:
            return await connection.execute(statement, parameters)


class RuntimeProbes:
    def __init__(
        self,
        engine: AsyncEngine,
        queue: QueuePublisher,
        storage: StorageProbe,
    ) -> None:
        self._engine = engine
        self._queue = queue
        self._storage = storage

    async def database(self) -> None:
        async with self._engine.connect() as connection:
            await connection.execute(text("select 1"))

    async def queue(self) -> None:
        await self._queue.depth()

    async def storage(self) -> None:
        await self._storage.check()


def create_runtime_app() -> FastAPI:
    settings = RuntimeSettings()  # type: ignore[call-arg]
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    executor = EngineExecutor(engine)
    queue = QueuePublisher(executor, queue_name=settings.queue_name)
    storage = StorageProbe(
        base_url=settings.supabase_url,
        service_role_key=settings.supabase_service_role_key.get_secret_value(),
        bucket=settings.storage_bucket,
        timeout_seconds=settings.dependency_timeout_seconds,
    )
    repository = ExampleJobRepository(async_sessionmaker(engine, expire_on_commit=False))
    service = JobService(
        repository=repository,
        queue=queue,
        rate_limiter=FixedWindowRateLimiter(
            limit=settings.request_limit,
            window_seconds=settings.request_window_seconds,
        ),
        queue_depth_limit=settings.queue_depth_limit,
    )
    app = create_app(
        settings=settings,
        probes=RuntimeProbes(engine, queue, storage),
        job_service=service,
    )
    app.state.database_engine = engine
    return app
