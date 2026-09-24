from __future__ import annotations

import os
import time
from typing import Any

import httpx
import pytest


def required_url(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        pytest.skip(f"{name} is only set for an explicit hosted smoke run")
    return value.rstrip("/")


def wait_for_terminal(
    client: httpx.Client,
    location: str,
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = client.get(location)
        response.raise_for_status()
        job = response.json()
        if job["status"] in {"succeeded", "failed"}:
            return job
        time.sleep(1)
    raise AssertionError("hosted example job did not complete before the deadline")


def test_hosted_foundation_path() -> None:
    api_url = required_url("VENDORLENS_HOSTED_API_URL")
    web_url = os.getenv("VENDORLENS_HOSTED_WEB_URL")

    with httpx.Client(timeout=10, follow_redirects=True) as client:
        if web_url:
            web = client.get(web_url)
            assert web.status_code == 200
            assert "VendorLens" in web.text

        assert client.get(f"{api_url}/health/live").json() == {"status": "ok"}
        assert client.get(f"{api_url}/health/ready").json() == {"status": "ready"}
        created = client.post(
            f"{api_url}/api/v1/example-jobs",
            headers={"Idempotency-Key": f"hosted-smoke-{time.time_ns()}"},
            json={"label": "VendorLens"},
        )
        assert created.status_code == 202
        job = wait_for_terminal(
            client, f"{api_url}{created.headers['location']}", timeout_seconds=60
        )
        assert job["status"] == "succeeded"
        assert job["result"] == "VENDORLENS"
