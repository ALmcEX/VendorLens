from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from vendorlens_api.dependencies import ProbeSet
from vendorlens_api.problems import problem_response


def create_health_router(probes: ProbeSet, timeout_seconds: float) -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health/live")
    async def liveness() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/health/ready", response_model=None)
    async def readiness(request: Request) -> JSONResponse:
        checks: tuple[tuple[str, Callable[[], Awaitable[None]]], ...] = (
            ("database", probes.database),
            ("queue", probes.queue),
            ("storage", probes.storage),
        )

        async def run_check(
            name: str,
            operation: Callable[[], Awaitable[None]],
        ) -> str | None:
            try:
                await asyncio.wait_for(operation(), timeout=timeout_seconds)
            except Exception:
                return name
            return None

        failures = await asyncio.gather(*(run_check(name, check) for name, check in checks))
        failed_dependency = next((name for name in failures if name is not None), None)
        if failed_dependency is not None:
            return problem_response(
                request,
                code=f"{failed_dependency}-unavailable",
                title=f"{failed_dependency.title()} unavailable",
                status=503,
                detail="A required service is unavailable.",
            )
        return JSONResponse({"status": "ready"})

    return router
