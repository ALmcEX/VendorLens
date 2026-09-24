from __future__ import annotations

import asyncio
import signal
from contextlib import suppress
from typing import Protocol

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from vendorlens_worker.config import WorkerSettings
from vendorlens_worker.processor import JobProcessor, NormalizeLabelOperation
from vendorlens_worker.queue import PgmqQueue, QueueMessage
from vendorlens_worker.repository import WorkerRepository


class ClaimQueue(Protocol):
    async def claim(self) -> QueueMessage | None: ...


class MessageProcessor(Protocol):
    async def process(self, message: QueueMessage) -> None: ...


class Worker:
    def __init__(
        self,
        queue: ClaimQueue,
        processor: MessageProcessor,
        *,
        poll_interval_seconds: float,
        shutdown_grace_seconds: float,
    ) -> None:
        self._queue = queue
        self._processor = processor
        self._poll_interval_seconds = poll_interval_seconds
        self._shutdown_grace_seconds = shutdown_grace_seconds

    async def run_once(self) -> bool:
        message = await self._queue.claim()
        if message is None:
            return False
        await self._processor.process(message)
        return True

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            message = await self._queue.claim()
            if message is None:
                try:
                    await asyncio.wait_for(
                        stop_event.wait(),
                        timeout=self._poll_interval_seconds,
                    )
                except TimeoutError:
                    continue
                return

            processing = asyncio.create_task(self._processor.process(message))
            stopping = asyncio.create_task(stop_event.wait())
            done, _pending = await asyncio.wait(
                {processing, stopping},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if processing in done:
                stopping.cancel()
                with suppress(asyncio.CancelledError):
                    await stopping
                await processing
                continue

            try:
                await asyncio.wait_for(processing, timeout=self._shutdown_grace_seconds)
            except TimeoutError:
                processing.cancel()
                with suppress(asyncio.CancelledError):
                    await processing
            return


def build_worker(settings: WorkerSettings) -> Worker:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    queue = PgmqQueue(
        engine,
        queue_name=settings.queue_name,
        visibility_timeout_seconds=settings.visibility_timeout_seconds,
    )
    processor = JobProcessor(
        WorkerRepository(session_factory),
        queue,
        NormalizeLabelOperation(),
        max_attempts=settings.max_attempts,
    )
    return Worker(
        queue,
        processor,
        poll_interval_seconds=settings.poll_interval_seconds,
        shutdown_grace_seconds=settings.shutdown_grace_seconds,
    )


async def async_main() -> None:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(signal_name, stop_event.set)
    await build_worker(WorkerSettings()).run(stop_event)  # type: ignore[call-arg]


def run() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    run()
