from __future__ import annotations

import os
import time
from typing import Any

import httpx


def wait_for_terminal(
    client: httpx.Client,
    job_url: str,
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = client.get(job_url)
        response.raise_for_status()
        job = response.json()
        if job["status"] in {"succeeded", "failed"}:
            return {"status": job["status"], "result": job["result"]}
        time.sleep(0.25)
    raise AssertionError("example job did not reach a terminal state before the deadline")


def test_local_stack_completes_example_job() -> None:
    base_url = os.getenv("VENDORLENS_SMOKE_API_URL", "http://localhost:8000")
    with httpx.Client(base_url=base_url, timeout=5.0) as client:
        assert client.get("/health/live").json() == {"status": "ok"}
        created = client.post(
            "/api/v1/example-jobs",
            headers={"Idempotency-Key": f"local-smoke-{time.time_ns()}"},
            json={"label": "VendorLens"},
        )
        assert created.status_code == 202
        assert wait_for_terminal(
            client,
            created.headers["location"],
            timeout_seconds=30,
        ) == {"status": "succeeded", "result": "VENDORLENS"}
