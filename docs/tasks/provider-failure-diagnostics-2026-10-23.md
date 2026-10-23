# Provider failure diagnostics — bounded repair

Status: implementation authorized and scope frozen on 2026-10-23.
Baseline: `07e37c11433e0b6388908e4b7d539a97e3abac1e`.
Branch: `fix/provider-failure-diagnostics`, based on the T-072 branch without changing its semantics.

## Problem and evidence

The authorized baseline returned HTTP 200 with empty final content, finish_reason=length,
and known prompt/completion usage. Response normalization discarded those facts;
Adapter and Runner collapsed the failure into INTERNAL_UNEXPECTED and
MULTI_AGENT_RUN_FAILED. The run correctly stopped, but its native failure artifact
could not explain the observed cause or retain the known usage.

The owner explicitly approved only the Provider → Adapter → Runner diagnostic
repair and offline regression. No real model calls are authorized by this task.

## Scope

- Add bounded, structured failure diagnostics: failure stage, safe finish reason,
  known/unknown input and output usage, content-empty status, and whether business
  schema validation ran or failed.
- Classify empty final content and invalid provider responses explicitly. Retain
  known response facts for JSON/schema failures after a valid provider response.
- Carry safe diagnostics into the native failed-run manifest, bound to the role
  and stage. Never release failed business output to downstream roles.
- Keep successful behavior, model/thinking/output settings, retry behavior,
  fixed topology, execution lanes, circuit behavior and target repository unchanged.

This is not a unified accounting rewrite: planning usage, budget admission,
effective configuration and semantic-brief consumption remain separate unresolved
items. Do not claim complete billing or improved plan quality from this repair.

## Allowed files

- `src/specflow/llm/diagnostics.py` (small stdlib-only diagnostic value object)
- `src/specflow/llm/exceptions.py`
- `src/specflow/llm/providers/openai_compatible.py`
- `src/specflow/policy/errors.py`
- `src/specflow/agents/adapter.py`
- `src/specflow/runner_multi.py`
- Focused tests for the provider, adapter, and failed-run artifacts; existing
  assertions may be strengthened to expect precise failure codes.
- This task and its completion report. Do not update learner progress or ownership.

## Acceptance

1. HTTP 200 + empty content + length + known usage remains a failure, but the
   manifest reports response-normalization failure and preserves finish reason
   and known usage. Schema status is not-run, not a fabricated schema failure.
2. Missing or invalid usage remains unknown, never fabricated as zero.
3. Invalid JSON and schema-invalid content retain available response diagnostics
   and are distinguishable from response-normalization failure.
4. No raw response body, reasoning text, exception text, credentials, or arbitrary
   provider strings enter the new diagnostics. Enum-like values are allowlisted.
5. Required-role failure still prevents dependent roles from executing; invalid
   payloads are not added to successful stages or persisted as trusted output.
6. Success, existing policy failures, lane/circuit behavior and retry counts retain
   their current semantics. The fix does not trigger retry or live execution.
7. A focused regression fails on the baseline and passes after the fix. Then run
   the repository's offline pytest suite and Ruff checks.

## Stop conditions

Stop before changing model settings, enabling retries, moving the goal to another
project, adding a general telemetry system, or running a model. Scope expansion
requires a new owner decision.
