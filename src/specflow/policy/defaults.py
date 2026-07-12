"""Default execution policy — conservative production defaults."""

from specflow.policy.models import ExecutionPolicy

DEFAULT_POLICY = ExecutionPolicy(
    max_wall_seconds=180,
    max_llm_calls=10,
    max_parallel_agents=3,
    max_revisions=1,
    max_total_tokens=60000,
    max_agent_input_tokens=8000,
    max_agent_output_tokens=2000,
    retry_budget_ratio=0.15,
    max_repository_files=10000,
    max_selected_files=80,
    max_evidence_chars=80000,
    max_tool_calls=20,
    fail_on_schema_error=True,
    allow_degraded_completion=True,
)
