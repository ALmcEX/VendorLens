from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from vendorlens_api.config import Settings
from vendorlens_api.dependencies import HealthyProbeSet, ProbeSet
from vendorlens_api.middleware import request_id_middleware
from vendorlens_api.problems import (
    unhandled_exception_handler,
    validation_exception_handler,
)
from vendorlens_api.routes.health import create_health_router
from vendorlens_api.routes.jobs import create_jobs_router
from vendorlens_api.services.jobs import JobOperations, UnavailableJobService


def create_app(
    settings: Settings | None = None,
    probes: ProbeSet | None = None,
    job_service: JobOperations | None = None,
) -> FastAPI:
    active_settings = settings or Settings()
    active_probes = probes or HealthyProbeSet()
    active_job_service = job_service or UnavailableJobService()

    app = FastAPI(title="VendorLens API", version="0.1.0")
    app.middleware("http")(request_id_middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Idempotency-Key", "X-Request-ID"],
    )
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(
        create_health_router(
            active_probes,
            timeout_seconds=active_settings.dependency_timeout_seconds,
        )
    )
    app.include_router(
        create_jobs_router(
            active_job_service,
            trust_proxy_headers=active_settings.trust_proxy_headers,
        )
    )
    return app


app = create_app()
