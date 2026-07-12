"""Tests for ExecutionPolicy, error taxonomy, RuntimeGuard, and RunOutcome."""

import pytest

from specflow.policy.defaults import DEFAULT_POLICY
from specflow.policy.errors import ErrorCategory, ErrorCode, error_category, is_retryable
from specflow.policy.models import (
    ArtifactPolicy,
    ExecutionPolicy,
    RepositoryPolicy,
    RetryPolicy,
    RunOutcome,
    RunStatus,
    SpecFlowError,
    TokenPolicy,
)
from specflow.policy.runtime_guard import RuntimeGuard
from specflow.policy.validator import PolicyValidator


class TestExecutionPolicy:
    def test_default_is_valid(self):
        assert DEFAULT_POLICY.max_wall_time_seconds == 300
        assert DEFAULT_POLICY.tokens.max_run_total_tokens == 62000
        assert DEFAULT_POLICY.repository.max_selected_files == 80

    def test_custom_policy(self):
        p = ExecutionPolicy(
            max_wall_time_seconds=120,
            tokens=TokenPolicy(max_run_total_tokens=30000),
        )
        assert p.max_wall_time_seconds == 120
        assert p.tokens.max_run_total_tokens == 30000

    def test_negative_wall_seconds_raises(self):
        with pytest.raises(ValueError):
            ExecutionPolicy(max_wall_time_seconds=0)

    def test_repository_selected_exceeds_scanned_raises(self):
        with pytest.raises(ValueError, match="max_selected_files"):
            RepositoryPolicy(max_scanned_files=10, max_selected_files=20)

    def test_token_reserved_exceeds_total_raises(self):
        with pytest.raises(ValueError, match="reserved_retry"):
            TokenPolicy(max_run_total_tokens=1000, reserved_retry_tokens=2000)

    def test_retry_negative_raises(self):
        with pytest.raises(ValueError, match="max_provider_retries"):
            RetryPolicy(max_provider_retries=-1)

    def test_policy_hash_stable(self):
        p1 = DEFAULT_POLICY
        p2 = ExecutionPolicy(
            max_wall_time_seconds=300,
            tokens=TokenPolicy(max_run_total_tokens=62000),
            repository=RepositoryPolicy(max_selected_files=80),
            retry=RetryPolicy(),
            artifacts=ArtifactPolicy(),
        )
        assert p1.policy_hash() == p2.policy_hash()

    def test_policy_hash_changes(self):
        p1 = DEFAULT_POLICY
        p2 = ExecutionPolicy(max_wall_time_seconds=999)
        assert p1.policy_hash() != p2.policy_hash()


class TestRunStatus:
    def test_business_reject_not_failed(self):
        assert RunStatus.REJECTED != RunStatus.FAILED_RUNTIME


class TestRunOutcome:
    def test_completed(self):
        o = RunOutcome(status=RunStatus.COMPLETED)
        assert o.degraded is False

    def test_degraded(self):
        o = RunOutcome(status=RunStatus.COMPLETED_DEGRADED, degraded=True)
        assert o.degraded is True

    def test_security_requires_code(self):
        with pytest.raises(ValueError):
            RunOutcome(status=RunStatus.FAILED_SECURITY)


class TestSpecFlowError:
    def test_safe_message(self):
        e = SpecFlowError(code="TEST", safe_message="safe text")
        assert "safe text" in str(e)

    def test_internal_error_id(self):
        e = SpecFlowError(code="TEST", safe_message="x")
        assert len(e.internal_error_id) == 12

    def test_api_key_filtered(self):
        e = SpecFlowError(code="TEST", safe_message="x", details={"api_key": "sk-secret"})
        assert e.details["api_key"] == "[REDACTED]"

    def test_no_traceback_in_message(self):
        try:
            raise ValueError("raw error")
        except ValueError as exc:
            e = SpecFlowError(code="TEST", safe_message="safe", retryable=False)
            e.__cause__ = exc
        assert "raw error" not in e.safe_message
        assert "Traceback" not in e.safe_message


class TestRuntimeGuard:
    def test_llm_call_within_budget(self):
        g = RuntimeGuard(ExecutionPolicy(max_llm_calls=5))
        g.consume_llm_call()
        assert g.llm_calls == 1

    def test_llm_call_exceeded(self):
        g = RuntimeGuard(ExecutionPolicy(max_llm_calls=1))
        g.consume_llm_call()
        with pytest.raises(SpecFlowError, match="budget exceeded"):
            g.consume_llm_call()

    def test_tokens_within_budget(self):
        g = RuntimeGuard(
            ExecutionPolicy(tokens=TokenPolicy(max_run_total_tokens=1000, reserved_retry_tokens=0))
        )
        g.consume_tokens(400, 400)
        assert g.total_input_tokens == 400
        assert g.total_output_tokens == 400

    def test_tokens_exceeded(self):
        g = RuntimeGuard(
            ExecutionPolicy(tokens=TokenPolicy(max_run_total_tokens=500, reserved_retry_tokens=0))
        )
        with pytest.raises(SpecFlowError, match="budget exceeded"):
            g.consume_tokens(300, 300)

    def test_revision_within_budget(self):
        g = RuntimeGuard(ExecutionPolicy(max_revisions=2))
        g.consume_revision()
        g.consume_revision()
        assert g.revision_count == 2

    def test_revision_exceeded(self):
        g = RuntimeGuard(ExecutionPolicy(max_revisions=1))
        g.consume_revision()
        with pytest.raises(SpecFlowError, match="budget exceeded"):
            g.consume_revision()

    def test_wall_time_exceeded(self):
        t = [0.0]

        def fake_time() -> float:
            return t[0]

        g = RuntimeGuard(ExecutionPolicy(max_wall_time_seconds=10), time_source=fake_time)
        t[0] = 100.0
        with pytest.raises(SpecFlowError, match="budget exceeded"):
            g.check_wall_time()

    def test_artifact_size_ok(self):
        g = RuntimeGuard(ExecutionPolicy())
        g.check_artifact_size(100)

    def test_artifact_size_exceeded(self):
        g = RuntimeGuard(ExecutionPolicy(artifacts=ArtifactPolicy(max_artifact_bytes=100)))
        with pytest.raises(SpecFlowError, match="exceeds limit"):
            g.check_artifact_size(200)

    def test_agent_limit_exceeded(self):
        g = RuntimeGuard(ExecutionPolicy(max_parallel_agents=2))
        g.consume_agent()
        g.consume_agent()
        with pytest.raises(SpecFlowError):
            g.consume_agent()


class TestErrorTaxonomy:
    def test_transient_retryable(self):
        assert is_retryable(ErrorCode.PROVIDER_TIMEOUT) is True
        assert is_retryable(ErrorCode.PROVIDER_RATE_LIMITED) is True

    def test_security_not_retryable(self):
        assert is_retryable(ErrorCode.PROVIDER_AUTH_FAILURE) is False
        assert is_retryable(ErrorCode.SECURITY_PATH_TRAVERSAL) is False

    def test_budget_not_retryable(self):
        assert is_retryable(ErrorCode.BUDGET_TOTAL_TOKENS) is False

    def test_all_codes_have_category(self):
        for code in ErrorCode:
            assert isinstance(error_category(code), ErrorCategory)


class TestPolicyValidator:
    def test_valid_passes(self):
        PolicyValidator().validate(DEFAULT_POLICY)

    def test_exceeds_hard_limit_raises(self):
        hard = ExecutionPolicy(max_llm_calls=5)
        client = ExecutionPolicy(max_llm_calls=20)
        v = PolicyValidator(system_hard_limit=hard)
        with pytest.raises(ValueError, match="exceeds system limit"):
            v.validate(client)

    def test_hard_limit_within_bounds_passes(self):
        hard = ExecutionPolicy(max_llm_calls=10)
        client = ExecutionPolicy(max_llm_calls=5)
        v = PolicyValidator(system_hard_limit=hard)
        v.validate(client)  # no exception
