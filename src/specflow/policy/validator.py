"""PolicyValidator — pre-flight policy checks."""

from specflow.policy.models import ExecutionPolicy


class PolicyValidator:
    """Validates that a policy is internally consistent and within system limits."""

    def __init__(self, system_hard_limit: ExecutionPolicy | None = None) -> None:
        self._hard_limit = system_hard_limit

    def validate(self, policy: ExecutionPolicy) -> None:
        """Raise ValueError if *policy* is invalid or exceeds system limits."""
        # Policy's own __post_init__ already validates internal consistency.
        # This method checks against optional hard limits.

        if self._hard_limit is None:
            return

        limits = [
            ("max_wall_seconds", self._hard_limit.max_wall_seconds),
            ("max_llm_calls", self._hard_limit.max_llm_calls),
            ("max_parallel_agents", self._hard_limit.max_parallel_agents),
            ("max_revisions", self._hard_limit.max_revisions),
            ("max_total_tokens", self._hard_limit.max_total_tokens),
            ("max_agent_input_tokens", self._hard_limit.max_agent_input_tokens),
            ("max_agent_output_tokens", self._hard_limit.max_agent_output_tokens),
            ("max_repository_files", self._hard_limit.max_repository_files),
            ("max_selected_files", self._hard_limit.max_selected_files),
            ("max_evidence_chars", self._hard_limit.max_evidence_chars),
            ("max_tool_calls", self._hard_limit.max_tool_calls),
        ]
        for field_name, max_allowed in limits:
            value = getattr(policy, field_name)
            if value > max_allowed:
                raise ValueError(
                    f"Policy {field_name}={value} exceeds system limit {max_allowed}"
                )
