from dataclasses import FrozenInstanceError

import pytest

from specflow.llm.diagnostics import LLMFailureDiagnostics
from specflow.llm.exceptions import LLMResponseError


@pytest.mark.parametrize("phase", ["response_normalization", "json_parse", "schema_validation"])
def test_round_trip_preserves_safe_facts_and_recomputes_status(phase: str) -> None:
    diagnostics = LLMFailureDiagnostics(
        phase=phase,
        finish_reason="length",
        input_tokens=2528,
        output_tokens=3000,
        content_empty=False,
    )
    envelope = diagnostics.as_dict()
    envelope["usage_status"] = "provider supplied status"
    envelope["schema_validation"] = "passed"

    restored = LLMFailureDiagnostics.from_dict(envelope)

    assert restored == diagnostics
    assert restored.as_dict()["usage_status"] == "known"
    assert restored.as_dict()["schema_validation"] == (
        "failed" if phase == "schema_validation" else "not_run"
    )


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        "private body",
        {},
        {"failure_stage": []},
        {"failure_stage": "private stage"},
        {"phase": "json_parse"},
    ],
)
def test_untrusted_envelope_requires_an_allowlisted_phase(value: object) -> None:
    assert LLMFailureDiagnostics.from_dict(value) is None


def test_untrusted_envelope_cannot_smuggle_provider_data_or_fabricate_usage() -> None:
    diagnostics = LLMFailureDiagnostics.from_dict(
        {
            "failure_stage": "response_normalization",
            "finish_reason": "credential and private provider text",
            "usage": {"input_tokens": False, "output_tokens": 3000, "body": "private body"},
            "usage_status": "known",
            "content_empty": "false",
            "schema_validation": "passed",
            "content": "private body",
            "reasoning_content": "private reasoning",
            "headers": {"Authorization": "private credential"},
        }
    )

    assert diagnostics.as_dict() == {
        "failure_stage": "response_normalization",
        "finish_reason": "unknown",
        "usage": {"input_tokens": None, "output_tokens": 3000},
        "usage_status": "partial",
        "content_empty": None,
        "schema_validation": "not_run",
    }
    assert "private" not in repr(diagnostics)


@pytest.mark.parametrize("finish_reason", ["unexpected value", [], {}, 1, True, ""])
def test_arbitrary_finish_values_are_replaced(finish_reason: object) -> None:
    diagnostics = LLMFailureDiagnostics(phase="json_parse", finish_reason=finish_reason)

    assert diagnostics.finish_reason == "unknown"


def test_missing_facts_are_unknown_and_zero_usage_is_known() -> None:
    missing = LLMFailureDiagnostics(phase="json_parse").as_dict()
    zero = LLMFailureDiagnostics(phase="json_parse", input_tokens=0, output_tokens=0).as_dict()

    assert missing["finish_reason"] is None
    assert missing["content_empty"] is None
    assert missing["usage"] == {"input_tokens": None, "output_tokens": None}
    assert missing["usage_status"] == "unknown"
    assert zero["usage"] == {"input_tokens": 0, "output_tokens": 0}
    assert zero["usage_status"] == "known"


def test_diagnostic_value_is_immutable_and_legacy_errors_remain_valid() -> None:
    diagnostics = LLMFailureDiagnostics(phase="json_parse")
    with pytest.raises(FrozenInstanceError):
        diagnostics.phase = "schema_validation"

    assert LLMResponseError("existing call").diagnostics is None
