from __future__ import annotations

import json
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.sql.elements import TextClause


class ScalarResult(Protocol):
    def scalar_one(self) -> Any: ...


class SqlExecutor(Protocol):
    async def execute(
        self,
        statement: TextClause,
        parameters: dict[str, Any],
    ) -> ScalarResult: ...


class QueuePublisher:
    def __init__(self, executor: SqlExecutor, *, queue_name: str) -> None:
        self._executor = executor
        self._queue_name = queue_name

    async def publish(self, *, job_id: UUID) -> None:
        message = json.dumps({"job_id": str(job_id)}, separators=(",", ":"))
        await self._executor.execute(
            text("select pgmq.send(:queue_name, cast(:message as jsonb))"),
            {"queue_name": self._queue_name, "message": message},
        )

    async def depth(self) -> int:
        result = await self._executor.execute(
            text("select queue_length from pgmq.metrics(:queue_name)"),
            {"queue_name": self._queue_name},
        )
        return int(result.scalar_one())
