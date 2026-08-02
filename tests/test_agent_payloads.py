"""Regression tests for strict inter-agent output contracts."""

import pytest
from pydantic import ValidationError

from specflow.revision.models import FindingSeverity, ReviewFinding
from specflow.schema.agent_payloads import DesignPayload, ReviewPayload


def _finding(target: str = "design-agent-v1", finding_id: str = "F-00000001") -> dict:
    return {
        "schema_version": "review_finding/v1",
        "finding_id": finding_id,
        "severity": FindingSeverity.WARNING.value,
        "category": "completeness",
        "description": "Missing module_b handling",
        "target_agent_id": target,
        "affected_artifact": None,
        "evidence_refs": [],
        "recommendation": "Add module_b coverage",
    }


def test_role_payloads_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DesignPayload.model_validate({"summary": "Valid", "raw_provider_field": "nope"})


def test_review_requires_explicit_decision() -> None:
    with pytest.raises(ValidationError):
        ReviewPayload.model_validate({"summary": "No decision"})


def test_reject_requires_structured_findings() -> None:
    """REJECT without findings must fail closed."""
    with pytest.raises(ValidationError, match="REJECT requires non-empty"):
        ReviewPayload.model_validate({"decision": "REJECT", "summary": "Blocked"})


def test_reject_requires_revision_flag() -> None:
    """REJECT with findings but requires_revision=False must fail closed."""
    with pytest.raises(ValidationError, match="requires_revision=True"):
        ReviewPayload.model_validate(
            {
                "decision": "REJECT",
                "summary": "Blocked",
                "findings": [ReviewFinding.model_validate(_finding())],
            }
        )


def test_pass_cannot_require_revision() -> None:
    with pytest.raises(ValidationError, match="PASS cannot require revision"):
        ReviewPayload.model_validate(
            {"decision": "PASS", "summary": "ok", "requires_revision": True}
        )


def test_duplicate_finding_ids_rejected() -> None:
    with pytest.raises(ValidationError, match="must be unique"):
        ReviewPayload.model_validate(
            {
                "decision": "REJECT",
                "summary": "Blocked",
                "requires_revision": True,
                "findings": [
                    ReviewFinding.model_validate(_finding(finding_id="F-00000001")),
                    ReviewFinding.model_validate(_finding(finding_id="F-00000001")),
                ],
            }
        )


def test_legacy_string_findings_are_rejected() -> None:
    """A legacy list[str] finding must never become an executable finding."""
    with pytest.raises(ValidationError):
        ReviewPayload.model_validate(
            {"decision": "REJECT", "summary": "Blocked", "findings": ["Missing module"]}
        )
