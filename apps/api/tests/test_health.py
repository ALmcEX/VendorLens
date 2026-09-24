import pytest
from httpx import ASGITransport, AsyncClient

from vendorlens_api.main import create_app


class ProbeSet:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def database(self) -> None:
        self.calls.append("database")

    async def queue(self) -> None:
        self.calls.append("queue")

    async def storage(self) -> None:
        self.calls.append("storage")


@pytest.mark.asyncio
async def test_liveness_has_no_dependency_checks() -> None:
    probes = ProbeSet()

    async with AsyncClient(
        transport=ASGITransport(app=create_app(probes=probes)),
        base_url="http://test",
    ) as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert probes.calls == []


@pytest.mark.parametrize("failed_dependency", ["database", "queue", "storage"])
@pytest.mark.asyncio
async def test_readiness_reports_only_failed_dependency_category(
    failed_dependency: str,
) -> None:
    class FailedProbeSet(ProbeSet):
        async def _run(self, name: str) -> None:
            self.calls.append(name)
            if name == failed_dependency:
                raise RuntimeError("postgresql://secret@internal.example/vendorlens")

        async def database(self) -> None:
            await self._run("database")

        async def queue(self) -> None:
            await self._run("queue")

        async def storage(self) -> None:
            await self._run("storage")

    async with AsyncClient(
        transport=ASGITransport(app=create_app(probes=FailedProbeSet())),
        base_url="http://test",
    ) as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["type"].endswith(f"/{failed_dependency}-unavailable")
    assert "secret" not in response.text
    assert "internal.example" not in response.text
    assert response.headers["x-request-id"] == body["request_id"]


@pytest.mark.asyncio
async def test_readiness_reports_ready_after_all_probes_pass() -> None:
    probes = ProbeSet()

    async with AsyncClient(
        transport=ASGITransport(app=create_app(probes=probes)),
        base_url="http://test",
    ) as client:
        response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert sorted(probes.calls) == ["database", "queue", "storage"]
