from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


class QueueMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    message_id: int
    read_count: int = Field(ge=1)
    job_id: UUID


class PgmqQueue:
    def __init__(
        self,
        engine: AsyncEngine,
        *,
        queue_name: str,
        visibility_timeout_seconds: int,
    ) -> None:
        self._engine = engine
        self._queue_name = queue_name
        self._visibility_timeout_seconds = visibility_timeout_seconds

    async def claim(self) -> QueueMessage | None:
        statement = text(
            "select msg_id, read_ct, message from pgmq.read(:queue_name, :visibility_timeout, 1)"
        )
        async with self._engine.begin() as connection:
            result = await connection.execute(
                statement,
                {
                    "queue_name": self._queue_name,
                    "visibility_timeout": self._visibility_timeout_seconds,
                },
            )
            row = result.mappings().first()
        if row is None:
            return None
        payload: Any = row["message"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return QueueMessage(
            message_id=int(row["msg_id"]),
            read_count=int(row["read_ct"]),
            job_id=UUID(str(payload["job_id"])),
        )

    async def archive(self, message_id: int) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(
                text("select pgmq.archive(:queue_name, :message_id)"),
                {"queue_name": self._queue_name, "message_id": message_id},
            )

    async def retry(self, message_id: int, *, delay_seconds: int) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(
                text("select pgmq.set_vt(:queue_name, :message_id, :delay_seconds)"),
                {
                    "queue_name": self._queue_name,
                    "message_id": message_id,
                    "delay_seconds": delay_seconds,
                },
            )
