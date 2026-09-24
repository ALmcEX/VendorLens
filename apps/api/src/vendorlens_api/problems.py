from __future__ import annotations

from fastapi import Request
from pydantic import BaseModel
from starlette.responses import JSONResponse


class ProblemDetails(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    instance: str | None = None
    request_id: str


def request_id_for(request: Request) -> str:
    return str(request.state.request_id)


def problem_response(
    request: Request,
    *,
    code: str,
    title: str,
    status: int,
    detail: str,
) -> JSONResponse:
    problem = ProblemDetails(
        type=f"https://vendorlens.dev/problems/{code}",
        title=title,
        status=status,
        detail=detail,
        instance=str(request.url.path),
        request_id=request_id_for(request),
    )
    return JSONResponse(
        status_code=status,
        content=problem.model_dump(mode="json"),
        media_type="application/problem+json",
    )


async def validation_exception_handler(
    request: Request,
    _exception: Exception,
) -> JSONResponse:
    return problem_response(
        request,
        code="validation-error",
        title="Request validation failed",
        status=422,
        detail="The request did not satisfy the published API contract.",
    )


async def unhandled_exception_handler(request: Request, _exception: Exception) -> JSONResponse:
    return problem_response(
        request,
        code="internal-error",
        title="Internal server error",
        status=500,
        detail="The server could not complete the request.",
    )
