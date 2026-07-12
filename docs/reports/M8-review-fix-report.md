# M8 Independent Review Fix Report

**Date:** 2026-07-12  
**Branch:** `feat/m8-production-hardening`  
**Review baseline:** `main` / `ab25b1f`  
**Merge decision:** Not merged; branch-only remediation.

## Resolved findings

- Required agent results now fail closed before downstream scheduling. Both
  receiver input and sender output schemas are validated on the runtime path;
  unknown output fields are rejected and no schema-missing raw pass-through
  remains.
- Review accepts only the explicit, validated `PASS` or `REJECT` decision.
  Revision execution records the Review-to-target audit edge and validates the
  subsequent Synthesis and Review handoffs.
- Execution policy is used by multi-agent execution for call, revision,
  wall-time, evidence, and tool limits. Legacy execution applies the policy to
  provider calls, evidence/tool limits, and worker token budgets.
- Retry retries only classified transient provider failures with bounded
  backoff. Authentication and security/path failures are not retried.
- Public result and failed-run artifacts store stable error codes rather than
  exception text. Multi-agent artifacts sanitize persisted payload values and
  do not place the target repository absolute path into prompts or artifacts.
- Evidence failure stops multi-agent execution. Repository evidence is labelled
  untrusted data and agents are told not to execute repository instructions.
- Metrics derive selected and referenced file counts from the evidence bundle;
  trace status reflects the real agent result.

## Regression coverage

Added production-path coverage for strict schemas, missing registry failure,
required-agent failure, receiver input validation, classified retry safety,
policy call limits, revision handoff hashes, artifact-safe errors, Chinese
evidence aliases, and real evidence-backed metrics.

## Validation

| Check | Result |
| --- | --- |
| `uv run pytest -v` | 637 passed, 2 skipped |
| `uv run ruff check .` | passed |
| `uv run ruff format --check .` | passed |
| `git diff --check` | passed |
| Legacy mock CLI | passed using the documented command syntax |
| Multi-agent mock CLI | passed against `sky-takeout-python`; target repo unchanged |

## Local acceptance evidence

Legacy mock used the documented CLI syntax:

```powershell
uv run specflow run --repo . --requirement "Add a search endpoint" --output ./artifacts/m8-legacy-final --mock
```

Multi-agent mock used the documented CLI syntax and the required read-only
target:

```powershell
uv run specflow run --mode multi-agent --repo "C:\Users\50469\github-projects\sky-takeout-python" --requirement "为订单增加超时自动取消功能，需要考虑订单状态竞争、重复任务、事务一致性、幂等、测试策略和失败恢复。" --output ./artifacts/m8-multi-agent-final --mock
```

The target repository was clean before and after the run. Its artifact contains
6 agent outputs, 7 handoffs with recomputed valid hashes, and 8 trace spans.
All 6 outputs are schema-validated, Review is explicit `PASS`,
`selected_file_count=10`, `referenced_file_count=6`, and fallback/degraded
counts are both 0. Artifact inspection found no secret pattern or absolute
filesystem path.

## Known boundaries

This remediation does not claim a new live-provider run, API service/auth
deployment, or completion of every M8 preview item. The local mock acceptance
is evidence for contract enforcement and artifact integrity only.
