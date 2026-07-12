"""Regression tests for strict inter-agent output contracts."""

import pytest
from pydantic import ValidationError

from specflow.schema.agent_payloads import DesignPayload, ReviewPayload


def test_role_payloads_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DesignPayload.model_validate({"summary": "Valid", "raw_provider_field": "nope"})


def test_review_requires_explicit_decision() -> None:
    with pytest.raises(ValidationError):
        ReviewPayload.model_validate({"summary": "No decision"})


def test_reject_requires_explicit_revision_target() -> None:
    with pytest.raises(ValidationError, match="target_agent_id is required"):
        ReviewPayload.model_validate({"decision": "REJECT", "summary": "Blocked"})
