from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from sqlalchemy.sql.elements import TextClause

from vendorlens_api.infrastructure.queue import QueuePublisher


class FakeResult:
    def __init__(self, scalar: int) -> None:
        self._scalar = scalar

    def scalar_one(self) -> int:
        return self._scalar


class RecordingExecutor:
    def __init__(self, metric_count: int = 0) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.metric_count = metric_count

    async def execute(
        self,
        statement: TextClause,
        parameters: dict[str, Any],
    ) -> FakeResult:
        self.calls.append((statement.text, parameters))
        return FakeResult(self.metric_count)


@pytest.mark.asyncio
async def test_publish_serializes_only_job_identity() -> None:
    executor = RecordingExecutor()
    publisher = QueuePublisher(executor, queue_name="example_jobs")

    await publisher.publish(job_id=UUID("00000000-0000-0000-0000-000000000001"))

    assert executor.calls == [
        (
            "select pgmq.send(:queue_name, cast(:message as jsonb))",
            {
                "queue_name": "example_jobs",
                "message": '{"job_id":"00000000-0000-0000-0000-000000000001"}',
            },
        )
    ]


@pytest.mark.asyncio
async def test_depth_returns_visible_queue_length() -> None:
    executor = RecordingExecutor(metric_count=7)
    publisher = QueuePublisher(executor, queue_name="example_jobs")

    assert await publisher.depth() == 7
