# T-084 — Handoff Integrity Failure Observability

> Integration identity (2026-09-13): T-084, formerly PR #9 T-073. Source: `c6c893c3a723a3f62c33265394ed1fcbf1c6029b` at `docs/tasks/T-073-handoff-integrity-failure-observability.md`. Original branch names, commits, dates and standalone validation below remain historical evidence, not integrated acceptance.

- Status: CLOSED
- Owner: Codex
- Branch: `codex/t072-no-evidence-fail-closed`
- Source finding: Day 6 Integrity Tamper

## Goal

Prove that a handoff payload changed after its hash is created is rejected before
the receiver executes, and persist a classified, payload-safe failure record
that identifies the affected handoff without reporting a successful run.

## Requirements

- **REQ-084-1:** `HandoffValidator.validate_payload()` must reject a payload
  that differs from the payload used to create `AgentHandoff.output_hash`.
- **REQ-084-2:** An integrity mismatch must stop the multi-agent run before the
  affected receiver executor is called and return exit code `3`.
- **REQ-084-3:** The failed run manifest and root/coordinator traces must record
  `HANDOFF_INTEGRITY_FAILED` plus bounded handoff identifiers sufficient to
  locate the sender, receiver, and payload reference.
- **REQ-084-4:** Failure artifacts must not persist the raw payload, expected
  hash, actual hash, exception text, repository path, or secrets.
- **REQ-084-5:** Existing successful handoffs and unrelated failure paths must
  preserve their current behavior.

## Allowed scope

- `src/specflow/handoff/exceptions.py`
- `src/specflow/handoff/validator.py`
- `src/specflow/policy/errors.py`
- `src/specflow/runner_multi.py`
- `tests/test_handoff_validator.py`
- `tests/test_cli_multi_agent.py`
- `docs/tasks/T-084-handoff-integrity-failure-observability.md`
- `docs/reports/T-084-completion-report.md`

## Forbidden scope

- Do not change Agent input/output schemas, topology, scheduling, retry,
  fallback, revision, Review, benchmark, provider, or legacy-runner behavior.
- Do not add payload persistence, raw hash persistence, dependencies, generic
  tracing middleware, or a new state machine.
- Do not update `docs/study/CURRENT.md`, learning evidence, Day 7 material,
  Retrieval, Vector, Hybrid, or Rerank behavior.

## Acceptance criteria

- **AC-084-1:** Given a valid handoff and matching output hash, when the
  referenced payload is modified before validation, validation raises the
  dedicated handoff integrity exception.
- **AC-084-2:** Given the same tamper at the Runner handoff boundary, the target
  receiver call count remains zero, the Runner returns `3`, and the workflow
  state is `failed`.
- **AC-084-3:** The failed manifest and root/coordinator traces contain
  `HANDOFF_INTEGRITY_FAILED`, `handoff_id`, `from_agent_id`, `to_agent_id`, and
  `payload_ref`.
- **AC-084-4:** The classified failure artifacts contain none of the raw
  payload, expected/actual hashes, exception text, repository path, or secrets.
- **AC-084-5:** Focused tests, full pytest, Ruff lint, Ruff format check, and
  `git diff --check` pass.

## Test-first plan

1. Add a validator unit test that creates a correct hash, mutates the payload,
   and expects a dedicated integrity exception.
2. Run the unit test and confirm RED because the dedicated exception does not
   exist yet.
3. Add a Runner integration test that tampers with a payload copy immediately
   before the real validator executes, then asserts receiver non-execution,
   classified failure, trace context, and payload-safe artifacts.
4. Run the integration test and confirm RED because the Runner currently emits
   `MULTI_AGENT_RUN_FAILED` without handoff context.
5. Implement only the typed exception, error taxonomy entry, and bounded
   failure-context propagation required by the tests.
6. Run focused and full validation, inspect the diff, and write the completion
   report.

## Risks

- A generic `HandoffValidationError` also covers schema-ID and envelope errors;
  only the output-hash mismatch may be classified as integrity failure.
- Failure context must remain identifiers-only. Raw payload and hash values
  would create unnecessary data exposure in diagnostic artifacts.
- The integration test may isolate the validator boundary, but must still call
  the real `validate_payload()` implementation after tampering.
