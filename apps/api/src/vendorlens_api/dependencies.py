from __future__ import annotations

from typing import Protocol


class ProbeSet(Protocol):
    async def database(self) -> None: ...

    async def queue(self) -> None: ...

    async def storage(self) -> None: ...


class HealthyProbeSet:
    async def database(self) -> None:
        return None

    async def queue(self) -> None:
        return None

    async def storage(self) -> None:
        return None
