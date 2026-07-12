# T-040 Completion Report — ExecutionPolicy and Error Taxonomy

## Result
**PASS.** All T-040 acceptance criteria met.

## Baseline
- Starting commit: `a6e7074` (initial implementation, 11 failures)
- Fix commit: `e880d46` (dot-path migration, 0 failures)
- Final commit: **pending** (RuntimeGuard integration)

## Implemented

### ExecutionPolicy with Sub-Policies
- `ExecutionPolicy` top-level: max_wall_time_seconds, max_llm_calls, max_parallel_agents, max_revisions, fail_on_schema_error, allow_degraded_completion
- `RepositoryPolicy`: scanned_files, selected_files, file_bytes, evidence_chars, evidence_items
- `TokenPolicy`: run_input/output/total tokens, agent input/output, reserved_retry
- `RetryPolicy`: provider_retries, schema_retries, json_repair_attempts
- `ArtifactPolicy`: max_artifact_bytes, max_error_message_chars, raw_provider_output/prompt flags
- Stable `policy_hash()` via canonical JSON + SHA-256

### Error Taxonomy
- `SpecFlowError`: code, safe_message, retryable, stage, agent_id, internal_error_id, details (sanitized)
- `ErrorCode` (33 codes) with `ErrorCategory` (11 categories) and `is_retryable()`
- `RunOutcome`: status, error_code, safe_message, requires_review, degraded, retryable
- `RunStatus`: CREATED, RUNNING, COMPLETED, COMPLETED_DEGRADED, REJECTED, FAILED_RUNTIME, FAILED_SECURITY, BUDGET_EXCEEDED, CANCELLED

### RuntimeGuard (replaces ExecutionBudget)
- `consume_llm_call()` — raises CALL_BUDGET_EXCEEDED
- `consume_tokens(in, out)` — raises TOKEN_BUDGET_EXCEEDED
- `consume_revision()` — raises REVISION_BUDGET_EXCEEDED
- `consume_agent()` — raises PARALLEL_AGENT_LIMIT_EXCEEDED (per-stage concurrency check)
- `check_wall_time()` — time source injectable for testing
- `check_artifact_size(bytes)` — raises ARTIFACT_LIMIT_EXCEEDED

### Integration
- RuntimeGuard wired into `runner_multi.py` production path
- `_budgeted_executor` wraps agent execution with LLM call + token tracking
- `_safe_write` checks artifact size before disk write
- Manifest includes `execution_policy`, `execution_policy_hash`, `budget_usage`
- `policy_hash` included in idempotency_key
- Legacy runner unaffected (separate `ExecutionBudget` compatibility adapter)

## Compatibility Decision
- `ExecutionBudget` retained in runner.py (Legacy) as lightweight compatibility adapter
- `RuntimeGuard` is canonical for Multi-Agent (used in runner_multi.py)
- Old top-level fields (`max_selected_files`, etc.) migrated to dot-path (`repository.max_selected_files`)
- All 11 field-reference failures fixed in `e880d46`

## Tests
- `tests/test_execution_policy.py`: 32 tests (policy validation, hash, error taxonomy, RuntimeGuard, safe error)
- All existing tests pass (652 total)

## Validation
```
uv run pytest -v:              652 passed, 2 skipped, 0 failures
uv run ruff check .:           All checks passed
uv run ruff format --check .:  All files formatted
git diff --check:              clean
```

## Known Limits (T-040 out of scope)
- Strict schema enforcement (T-041)
- Typed fallback with backoff retry (T-042)
- Real tokenizer / cost estimates (T-043)
- Full-pipeline redaction (T-044)
- Checkpoint recovery (T-045)
- API service (T-046)
