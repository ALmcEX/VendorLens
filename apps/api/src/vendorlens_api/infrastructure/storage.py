from __future__ import annotations

import httpx


class StorageProbe:
    def __init__(
        self,
        *,
        base_url: str,
        service_role_key: str,
        bucket: str,
        timeout_seconds: float = 2.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._service_role_key = service_role_key
        self._bucket = bucket
        self._timeout_seconds = timeout_seconds
        self._client = client

    async def check(self) -> None:
        client = self._client or httpx.AsyncClient(timeout=self._timeout_seconds)
        owns_client = self._client is None
        try:
            response = await client.get(
                f"{self._base_url}/storage/v1/bucket/{self._bucket}",
                headers={
                    "apikey": self._service_role_key,
                    "Authorization": f"Bearer {self._service_role_key}",
                },
            )
            response.raise_for_status()
        finally:
            if owns_client:
                await client.aclose()
