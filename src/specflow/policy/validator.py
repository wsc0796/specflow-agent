"""PolicyValidator — pre-flight policy checks."""

from specflow.policy.models import ExecutionPolicy


class PolicyValidator:
    """Validates that a policy is internally consistent and within system limits."""

    def __init__(self, system_hard_limit: ExecutionPolicy | None = None) -> None:
        self._hard_limit = system_hard_limit

    def validate(self, policy: ExecutionPolicy) -> None:
        """Raise ValueError if *policy* is invalid or exceeds system limits."""
        if self._hard_limit is None:
            return

        limits: list[tuple[str, int]] = [
            ("max_wall_time_seconds", self._hard_limit.max_wall_time_seconds),
            ("max_llm_calls", self._hard_limit.max_llm_calls),
            ("max_parallel_agents", self._hard_limit.max_parallel_agents),
            ("max_revisions", self._hard_limit.max_revisions),
            ("tokens.max_run_total_tokens", self._hard_limit.tokens.max_run_total_tokens),
            ("tokens.max_agent_input_tokens", self._hard_limit.tokens.max_agent_input_tokens),
            ("tokens.max_agent_output_tokens", self._hard_limit.tokens.max_agent_output_tokens),
            ("repository.max_scanned_files", self._hard_limit.repository.max_scanned_files),
            ("repository.max_selected_files", self._hard_limit.repository.max_selected_files),
            (
                "repository.max_total_evidence_chars",
                self._hard_limit.repository.max_total_evidence_chars,
            ),
            ("artifacts.max_artifact_bytes", self._hard_limit.artifacts.max_artifact_bytes),
        ]
        for field_path, max_allowed in limits:
            value = _resolve_attr(policy, field_path)
            if value > max_allowed:
                raise ValueError(f"Policy {field_path}={value} exceeds system limit {max_allowed}")


def _resolve_attr(obj: object, path: str) -> int:
    """Resolve dotted attribute path like 'tokens.max_run_total_tokens'."""
    parts = path.split(".")
    for part in parts:
        obj = getattr(obj, part)
    return obj  # type: ignore[return-value]
