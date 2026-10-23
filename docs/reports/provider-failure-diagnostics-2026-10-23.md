# Provider failure diagnostics — completion report

Date: 2026-10-23. Base: `07e37c11433e0b6388908e4b7d539a97e3abac1e`.
Task: [bounded repair contract](../tasks/provider-failure-diagnostics-2026-10-23.md).
Status: implemented and verified offline; no new live-model execution.

## Problem and resulting behavior

A recorded RepositoryAnalyst call returned HTTP 200, `finish_reason=length`,
2,528 input tokens and 3,000 completion tokens, but empty final content. The
original Provider → Adapter → Runner chain stopped safely while discarding the
known response facts and reporting only `MULTI_AGENT_RUN_FAILED`.

The same response now produces `PROVIDER_EMPTY_CONTENT`. A failed-run manifest
retains allowlisted diagnostics tied to the role and stage: normalization/JSON/
schema phase, safe finish reason, known or unknown input/output usage, empty-content
status, and whether schema validation ran. Trace context identifies the failed
role and error. Invalid business output remains excluded from handoffs and trusted
stage artifacts; dependent agents are not invoked.

## Changes

- Add a small immutable `LLMFailureDiagnostics` value object. Unknown usage stays
  `None`; a real reported zero stays known. Derived states are recomputed when
  reading diagnostic dictionaries. Arbitrary provider strings are not retained.
- Preserve safe response facts before Provider normalization can reject content.
  Empty content and other invalid Provider responses have non-retryable codes.
- Preserve available diagnostics for Adapter JSON and business-schema failures.
  Successful envelopes and request construction are unchanged.
- Keep failed-attempt diagnostics separate from completed stages and business
  outputs. Runner validates code/phase agreement before writing bounded metadata.
- Strengthen prior output-validity tests to expect specific schema-failure codes
  and usage instead of the previous generic error; fail-closed assertions remain.

## Verification actually run

All model responses in this task were offline fixtures or saved-response replays.
Repository tests block real HTTP. No real model calls, paid probes, or automatic
baseline reruns occurred.

| Check | Result |
|---|---|
| Provider behavior before repair | 11 failing / 27 passing focused tests |
| Adapter diagnostic regressions before repair | 3 failing focused regressions |
| Runner diagnostic regressions before Runner repair | 4 failing regressions |
| Provider and diagnostic-value focused checks | 60 passed |
| Adapter focused checks | 20 passed |
| New native failed-artifact checks | 4 passed |
| `.venv/Scripts/python.exe -B -m pytest -v` | **1055 passed, 3 skipped, 3 warnings**, 22.82s |
| `.venv/Scripts/python.exe -B -m ruff check .` | passed |
| `.venv/Scripts/python.exe -B -m ruff format --check .` | passed, 220 files formatted |
| `git diff --check` | passed |

The three skips concern Windows symlink privileges. Warnings are existing pytest
collection and Starlette/httpx notices; this task adds no skip or xfail.

### Saved-response replay

Replayed all seven saved HTTP responses through the actual Provider/AgentRunner
and fixed workflow with MockTransport and blocked sockets. Each serialized
request body matched its original baseline counterpart. The repaired run still
stopped at RepositoryAnalyst with exit code 3, zero completed stages, and no
downstream role calls, while its manifest now directly reported:

```json
{
  "error": "PROVIDER_EMPTY_CONTENT",
  "failure_stage": "response_normalization",
  "finish_reason": "length",
  "usage": {"input_tokens": 2528, "output_tokens": 3000},
  "usage_status": "known",
  "schema_validation": "not_run"
}
```

The excerpt flattens the manifest's diagnostic entry for readability. Request
parameters, default thinking behavior, retry policy, roles and target source were
not changed. Raw reasoning was not saved in the original record and is not read
by this parser; the relevant content/finish/usage fields were preserved.

## Review and boundaries

A focused independent source review found no additional issue in the diagnostic
whitelist, known/unknown semantics, code/phase agreement, fail-closed propagation,
or retry/circuit classification. The target repository stayed at its original
commit with a clean worktree.

This repair improves native failure diagnosis. It does not make the failed model
produce a valid plan and is not a quality-improvement claim. Failure usage is
retained as diagnostic evidence; planning accounting and a unified per-call
budget ledger remain separate unresolved work. Model configuration, semantic
brief consumption, context selection and memory are outside this task.

Implementation and validation here were AI-assisted. Do not convert these records
into an assertion that the learner independently implemented or mastered them.
