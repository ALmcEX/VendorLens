from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ExampleJobPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str = Field(min_length=1, max_length=100)

    @field_validator("label")
    @classmethod
    def strip_label(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("label must contain non-whitespace characters")
        return stripped


class ExampleJob(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    idempotency_key: str
    payload_hash: str
    status: JobStatus
    attempt_count: int = Field(ge=0)
    result: str | None = None
    error_category: str | None = None


def payload_fingerprint(payload: ExampleJobPayload) -> str:
    canonical = json.dumps(payload.model_dump(), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_label(label: str) -> str:
    return label.upper()
