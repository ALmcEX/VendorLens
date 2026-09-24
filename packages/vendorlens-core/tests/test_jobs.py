import pytest
from pydantic import ValidationError
from vendorlens_core.jobs import (
    ExampleJobPayload,
    JobStatus,
    normalize_label,
    payload_fingerprint,
)


def test_payload_accepts_a_short_unicode_label() -> None:
    payload = ExampleJobPayload(label="  VendorLens 测试  ")
    assert payload.label == "VendorLens 测试"


def test_payload_rejects_more_than_100_characters() -> None:
    with pytest.raises(ValidationError):
        ExampleJobPayload(label="a" * 101)


def test_payload_rejects_whitespace_only_label() -> None:
    with pytest.raises(ValidationError):
        ExampleJobPayload(label="   ")


def test_fingerprint_is_stable_for_equivalent_payloads() -> None:
    first = payload_fingerprint(ExampleJobPayload(label=" VendorLens "))
    second = payload_fingerprint(ExampleJobPayload(label="VendorLens"))
    assert first == second


def test_job_status_values_are_stable() -> None:
    assert [status.value for status in JobStatus] == [
        "queued",
        "running",
        "succeeded",
        "failed",
    ]


def test_normalize_label_returns_uppercase_text() -> None:
    assert normalize_label("VendorLens 测试") == "VENDORLENS 测试"
