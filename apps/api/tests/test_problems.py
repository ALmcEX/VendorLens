from typing import Annotated

import pytest
from fastapi import Body
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, Field

from vendorlens_api.main import create_app


class ValidationBody(BaseModel):
    label: Annotated[str, Field(min_length=1)]


@pytest.mark.asyncio
async def test_validation_errors_use_problem_details() -> None:
    app = create_app()

    @app.post("/test-validation")
    async def validation_endpoint(body: Annotated[ValidationBody, Body()]) -> ValidationBody:
        return body

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post("/test-validation", json={"label": ""})

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert set(response.json()) >= {
        "type",
        "title",
        "status",
        "detail",
        "instance",
        "request_id",
    }
    assert response.headers["x-request-id"] == response.json()["request_id"]


@pytest.mark.asyncio
async def test_unhandled_errors_hide_internal_details() -> None:
    app = create_app()

    @app.get("/test-error")
    async def error_endpoint() -> None:
        raise RuntimeError("postgresql://secret@internal.example/vendorlens")

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get("/test-error")

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/problem+json")
    assert "secret" not in response.text
    assert "internal.example" not in response.text
