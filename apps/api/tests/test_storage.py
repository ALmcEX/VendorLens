import httpx
import pytest

from vendorlens_api.infrastructure.storage import StorageProbe


@pytest.mark.asyncio
async def test_storage_probe_reads_bucket_metadata_without_uploading() -> None:
    observed: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(request)
        return httpx.Response(200, json={"id": "vendor-documents", "public": False})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        probe = StorageProbe(
            base_url="https://project.supabase.co",
            service_role_key="service-role-test-key",
            bucket="vendor-documents",
            client=client,
        )
        await probe.check()

    assert len(observed) == 1
    assert observed[0].method == "GET"
    assert observed[0].url.path == "/storage/v1/bucket/vendor-documents"
    assert observed[0].headers["authorization"] == "Bearer service-role-test-key"
