from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from vendorlens_api.persistence.models import Base
from vendorlens_api.persistence.repository import ExampleJobRepository
from vendorlens_core.jobs import JobStatus


@pytest_asyncio.fixture
async def repository() -> AsyncIterator[ExampleJobRepository]:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield ExampleJobRepository(async_sessionmaker(engine, expire_on_commit=False))
    await engine.dispose()


@pytest.mark.asyncio
async def test_repository_round_trips_a_queued_job(
    repository: ExampleJobRepository,
) -> None:
    created = await repository.create(
        idempotency_key="same-request",
        payload_hash="a" * 64,
        label="VendorLens",
    )

    loaded = await repository.get(created.id)

    assert loaded == created
    assert loaded.status is JobStatus.QUEUED


@pytest.mark.asyncio
async def test_repository_marks_enqueue_failure_without_leaking_detail(
    repository: ExampleJobRepository,
) -> None:
    created = await repository.create(
        idempotency_key="failed-request",
        payload_hash="b" * 64,
        label="VendorLens",
    )

    failed = await repository.mark_failed(created.id, error_category="enqueue_failed")

    assert failed.status is JobStatus.FAILED
    assert failed.error_category == "enqueue_failed"
