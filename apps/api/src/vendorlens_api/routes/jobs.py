from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Header, Request
from starlette.responses import JSONResponse

from vendorlens_api.problems import problem_response
from vendorlens_api.services.jobs import (
    EnqueueUnavailable,
    IdempotencyConflict,
    JobNotFound,
    JobOperations,
    JobServiceUnavailable,
    QueueSaturated,
    RateLimitExceeded,
)
from vendorlens_core.jobs import ExampleJobPayload


def _client_id(request: Request, *, trust_proxy_headers: bool) -> str:
    if trust_proxy_headers:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",", maxsplit=1)[0].strip()
    if request.client is None:
        return "unknown"
    return request.client.host


def create_jobs_router(
    service: JobOperations,
    *,
    trust_proxy_headers: bool,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/example-jobs", tags=["example-jobs"])

    @router.post("", status_code=202)
    async def submit_job(
        request: Request,
        payload: ExampleJobPayload,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> JSONResponse:
        active_key = idempotency_key or str(uuid4())
        try:
            job = await service.submit(
                payload=payload,
                idempotency_key=active_key,
                client_id=_client_id(request, trust_proxy_headers=trust_proxy_headers),
            )
        except IdempotencyConflict:
            return problem_response(
                request,
                code="idempotency-conflict",
                title="Idempotency key conflict",
                status=409,
                detail="The idempotency key was already used with different input.",
            )
        except RateLimitExceeded:
            return problem_response(
                request,
                code="rate-limit-exceeded",
                title="Request rate exceeded",
                status=429,
                detail="Too many job submissions were received for this client.",
            )
        except QueueSaturated:
            return problem_response(
                request,
                code="queue-saturated",
                title="Job queue is at capacity",
                status=429,
                detail="The job queue is temporarily unable to accept more work.",
            )
        except (EnqueueUnavailable, JobServiceUnavailable):
            return problem_response(
                request,
                code="job-service-unavailable",
                title="Job service unavailable",
                status=503,
                detail="The job could not be accepted at this time.",
            )

        return JSONResponse(
            status_code=202,
            content=job.model_dump(mode="json"),
            headers={
                "Location": f"/api/v1/example-jobs/{job.id}",
                "Idempotency-Key": active_key,
            },
        )

    @router.get("/{job_id}")
    async def get_job(request: Request, job_id: UUID) -> JSONResponse:
        try:
            job = await service.get(job_id)
        except JobNotFound:
            return problem_response(
                request,
                code="job-not-found",
                title="Job not found",
                status=404,
                detail="No job exists for the requested identifier.",
            )
        except JobServiceUnavailable:
            return problem_response(
                request,
                code="job-service-unavailable",
                title="Job service unavailable",
                status=503,
                detail="Job status is temporarily unavailable.",
            )
        return JSONResponse(status_code=200, content=job.model_dump(mode="json"))

    return router
