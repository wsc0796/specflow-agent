# T-073 Completion Report — Handoff Integrity Failure Observability

## Outcome

The multi-agent runner now classifies an output-hash mismatch as
`HANDOFF_INTEGRITY_FAILED`, stops before the affected receiver executes, and
persists bounded handoff identifiers in the failed manifest and root/coordinator
traces. Failure artifacts do not include the raw payload, expected hash, actual
hash, exception text, repository path, or secrets.

## Root cause

`HandoffValidator.validate_payload()` already recalculated the referenced
payload hash and rejected mismatches, but raised the generic
`HandoffValidationError`. `run_multi_agent()` therefore handled the mismatch as
an unexpected exception, persisted `MULTI_AGENT_RUN_FAILED`, and lost the
handoff identity needed to locate the failure in artifacts and traces.

## Changes

- Added `HandoffIntegrityError`, carrying only `handoff_id`, sender, receiver,
  and artifact-relative `payload_ref` as safe audit context.
- Raised the dedicated exception only for the output-hash mismatch branch;
  schema-ID and envelope validation retain their existing error behavior.
- Added `HANDOFF_INTEGRITY_FAILED` to the unified error taxonomy as a
  non-retryable internal integrity failure.
- Added a dedicated Runner catch path that records the classified error and
  bounded context in failed manifests and root/coordinator traces.
- Kept unrelated failure traces unchanged and preserved existing success,
  topology, schema, scheduling, revision, and provider behavior.

## TDD evidence

### RED 1 — validator behavior

```powershell
uv run pytest tests/test_handoff_validator.py::TestHandoffValidator::test_payload_mutated_after_hash_raises_integrity_error -q -p no:cacheprovider
```

Result: exit `1`. The existing validator detected the mismatch but raised
`HandoffValidationError` instead of the required dedicated integrity exception.

### RED 2 — Runner propagation

```powershell
uv run pytest tests/test_cli_multi_agent.py::TestMultiAgentRunner::test_handoff_integrity_failure_stops_receiver_and_persists_context -q -p no:cacheprovider
```

Result: exit `1`. The receiver call count was already zero and the workflow
failed, but the manifest recorded `MULTI_AGENT_RUN_FAILED` without handoff
context.

### GREEN

The two new tests passed after the minimal typed-exception and failure-context
implementation. The affected Handoff, Runner, and error-taxonomy paths passed
together: `58 passed`.

## Verification evidence

```text
Focused affected paths: 58 passed
Full pytest:            775 passed, 3 skipped, 3 known warnings
Ruff lint:              passed
Ruff format check:      208 files already formatted
git diff --check:       passed
```

## Boundaries retained

- No raw payload or hash values are persisted in the new failure context.
- Generic Handoff schema/envelope failures retain their previous classification.
- Unrelated failure traces do not gain new fields.
- Agent schemas, topology, scheduling, retry, fallback, Revision, Review,
  benchmark, provider, legacy runner, dependencies, and study-state files are
  unchanged.

## Files

- `src/specflow/handoff/exceptions.py`
- `src/specflow/handoff/validator.py`
- `src/specflow/policy/errors.py`
- `src/specflow/runner_multi.py`
- `tests/test_handoff_validator.py`
- `tests/test_cli_multi_agent.py`
- `docs/tasks/T-073-handoff-integrity-failure-observability.md`
- `docs/reports/T-073-completion-report.md`
