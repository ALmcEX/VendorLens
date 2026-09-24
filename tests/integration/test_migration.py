import os

import asyncpg
import pytest


@pytest.mark.asyncio
async def test_foundation_migration_creates_required_resources() -> None:
    database_url = os.getenv("VENDORLENS_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("VENDORLENS_TEST_DATABASE_URL is only set in Supabase integration runs")

    connection = await asyncpg.connect(
        database_url.replace("postgresql+asyncpg://", "postgresql://")
    )
    try:
        table = await connection.fetchval("select to_regclass('public.example_jobs')")
        bucket = await connection.fetchval(
            "select exists(select 1 from storage.buckets where id = 'vendor-documents')"
        )
        queue = await connection.fetchval(
            "select exists(select 1 from pgmq.list_queues() where queue_name = 'example_jobs')"
        )
    finally:
        await connection.close()

    assert table == "example_jobs"
    assert bucket is True
    assert queue is True
