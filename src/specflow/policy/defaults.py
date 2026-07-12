"""Conservative default execution policy."""

from specflow.policy.models import (
    ArtifactPolicy,
    ExecutionPolicy,
    RepositoryPolicy,
    RetryPolicy,
    TokenPolicy,
)

DEFAULT_POLICY = ExecutionPolicy(
    policy_version="1.0.0",
    max_wall_time_seconds=300,
    max_llm_calls=10,
    max_parallel_agents=3,
    max_revisions=1,
    fail_on_schema_error=True,
    allow_degraded_completion=True,
    repository=RepositoryPolicy(
        max_scanned_files=10000,
        max_selected_files=80,
        max_file_bytes=262144,
        max_total_evidence_chars=80000,
        max_evidence_items=200,
    ),
    tokens=TokenPolicy(
        max_run_input_tokens=50000,
        max_run_output_tokens=12000,
        max_run_total_tokens=62000,
        max_agent_input_tokens=10000,
        max_agent_output_tokens=3000,
        reserved_retry_tokens=6000,
    ),
    retry=RetryPolicy(
        max_provider_retries=2,
        max_schema_retries=1,
        max_json_repair_attempts=1,
    ),
    artifacts=ArtifactPolicy(
        max_artifact_bytes=5 * 1024 * 1024,
        max_error_message_chars=500,
        include_raw_provider_output=False,
        include_raw_prompt=False,
    ),
)
