# T-049 — Bounded Live Validation

```yaml
task_id: T-049
title: Bounded live-provider validation
stage_state: skipped
goal: Produce a small, safe live-provider evidence set only when authorized provider configuration and a read-only target repository are available.
allowed_scope:
  files:
    - docs/tasks/T-049-bounded-live-validation.md
    - docs/reports/T-049-completion-report.md
forbidden_scope:
  - Do not create, request, print, persist, or commit credentials.
  - Do not substitute mock evidence for a live-provider claim.
  - Do not modify the target repository.
inputs:
  - SPECFLOW_LLM_BASE_URL, SPECFLOW_LLM_API_KEY, and SPECFLOW_LLM_MODEL supplied by the user environment.
  - An authorized read-only target repository.
acceptance:
  - If all inputs exist, run one to three bounded cases and validate resulting artifacts.
  - If any input is absent, record a skipped result with the missing input category and proceed without a live claim.
verification:
  - command: environment-presence check without printing secret values
    proves: Whether live execution may begin safely.
outputs:
  - A live validation report or an explicit skipped record.
risks:
  - A mock run cannot replace this task.
  - Credentials must remain process-local and absent from all artifacts and Git history.
next_state: planning (T-050 Portfolio Demo Release)
```
