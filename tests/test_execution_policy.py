"""Tests for ExecutionPolicy, error taxonomy, and policy validation."""

import pytest

from specflow.policy.defaults import DEFAULT_POLICY
from specflow.policy.errors import (
    ErrorCategory,
    ErrorCode,
    error_category,
    is_retryable,
)
from specflow.policy.models import ExecutionPolicy, RunStatus
from specflow.policy.validator import PolicyValidator


class TestExecutionPolicy:
    def test_default_policy_is_valid(self):
        policy = DEFAULT_POLICY
        assert policy.max_wall_seconds == 180
        assert policy.max_total_tokens == 60000

    def test_custom_policy(self):
        policy = ExecutionPolicy(
            max_wall_seconds=120,
            max_total_tokens=30000,
            max_agent_input_tokens=4000,
            max_agent_output_tokens=1000,
        )
        assert policy.max_wall_seconds == 120

    def test_negative_wall_seconds_raises(self):
        with pytest.raises(ValueError):
            ExecutionPolicy(max_wall_seconds=0)

    def test_agent_tokens_exceed_total_raises(self):
        with pytest.raises(ValueError, match="cannot exceed total"):
            ExecutionPolicy(
                max_total_tokens=5000,
                max_agent_input_tokens=4000,
                max_agent_output_tokens=2000,
            )

    def test_invalid_retry_ratio_raises(self):
        with pytest.raises(ValueError):
            ExecutionPolicy(retry_budget_ratio=1.5)

    def test_policy_hash_stable(self):
        p1 = ExecutionPolicy()
        p2 = ExecutionPolicy()
        assert p1.policy_hash() == p2.policy_hash()

    def test_policy_hash_changes(self):
        p1 = ExecutionPolicy()
        p2 = ExecutionPolicy(max_total_tokens=12345)
        assert p1.policy_hash() != p2.policy_hash()

    def test_serialization_roundtrip(self):
        policy = ExecutionPolicy()
        h1 = policy.policy_hash()
        # Rebuild from dict
        data = {k: getattr(policy, k) for k in policy.__dataclass_fields__}  # type: ignore
        rebuilt = ExecutionPolicy(**data)
        assert rebuilt.policy_hash() == h1


class TestRunStatus:
    def test_all_statuses_defined(self):
        assert RunStatus.COMPLETED == "completed"
        assert RunStatus.FAILED_SECURITY == "failed_security"
        assert RunStatus.BUDGET_EXCEEDED == "budget_exceeded"
        assert RunStatus.CANCELLED == "cancelled"

    def test_business_reject_not_failed(self):
        assert RunStatus.REJECTED != RunStatus.FAILED_RUNTIME


class TestErrorTaxonomy:
    def test_transient_errors_are_retryable(self):
        assert is_retryable(ErrorCode.PROVIDER_TIMEOUT) is True
        assert is_retryable(ErrorCode.PROVIDER_RATE_LIMITED) is True
        assert is_retryable(ErrorCode.PROVIDER_SERVER_ERROR) is True

    def test_security_errors_not_retryable(self):
        assert is_retryable(ErrorCode.SECURITY_PATH_TRAVERSAL) is False
        assert is_retryable(ErrorCode.SECURITY_SENSITIVE_FILE) is False
        assert is_retryable(ErrorCode.PROVIDER_AUTH_FAILURE) is False

    def test_budget_errors_not_retryable(self):
        assert is_retryable(ErrorCode.BUDGET_TOTAL_TOKENS) is False
        assert is_retryable(ErrorCode.BUDGET_RETRY_EXHAUSTED) is False

    def test_schema_errors_not_retryable(self):
        assert is_retryable(ErrorCode.SCHEMA_MISSING_FIELD) is False

    def test_category_mapping(self):
        assert error_category(ErrorCode.PROVIDER_TIMEOUT) == ErrorCategory.TRANSIENT_PROVIDER
        assert error_category(ErrorCode.PROVIDER_AUTH_FAILURE) == ErrorCategory.PERMANENT_PROVIDER
        assert error_category(ErrorCode.SCHEMA_MISSING_FIELD) == ErrorCategory.SCHEMA_MISMATCH
        assert error_category(ErrorCode.SECURITY_PATH_TRAVERSAL) == ErrorCategory.SECURITY_VIOLATION
        assert error_category(ErrorCode.BUDGET_TOTAL_TOKENS) == ErrorCategory.BUDGET_EXCEEDED
        assert error_category(ErrorCode.RUN_CANCELLED) == ErrorCategory.CANCELLED

    def test_all_codes_have_category(self):
        for code in ErrorCode:
            cat = error_category(code)
            assert isinstance(cat, ErrorCategory), f"Missing category for {code}"


class TestPolicyValidator:
    def test_valid_policy_passes(self):
        PolicyValidator().validate(DEFAULT_POLICY)

    def test_exceeds_hard_limit_raises(self):
        hard = ExecutionPolicy(max_total_tokens=10000)
        validator = PolicyValidator(system_hard_limit=hard)
        client = ExecutionPolicy(max_total_tokens=20000)
        with pytest.raises(ValueError, match="exceeds system limit"):
            validator.validate(client)
