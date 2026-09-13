# T-074 Completion Report — Repository File Limit Policy Wiring

## Outcome

The legacy and multi-agent runners now translate
`ExecutionPolicy.repository.max_file_bytes` through one shared function and
supply the resulting `RepositoryPolicyLimits` to `RepositoryToolSet`.
Custom file limits therefore affect the Repository Tools in both runner modes,
while unrelated Tool limits retain their existing defaults.

## Root cause

Both runners accepted and hashed an `ExecutionPolicy`, but each constructed
`RepositoryToolSet(repo)` without passing limits. `RepositoryAccessPolicy`
therefore replaced `None` with default `RepositoryPolicyLimits`, leaving a
custom execution-policy file limit unenforced.

## Changes

- Added `repository_tool_limits_from_policy()` as the single translation point.
- Translated only `max_file_bytes`, the field with reproduced and matching
  semantics in both policy models.
- Connected the legacy and multi-agent runners to the shared translation.
- Added behavior tests that exercise both complete mock-run paths and inspect
  the persisted `read_file` ToolCall record.

## TDD evidence

### RED

```powershell
uv run pytest tests/test_repository_policy_wiring.py -q -p no:cacheprovider
```

Result before production changes: exit `1`; both tests failed because
`read_file.truncated` was `false` under a configured five-byte limit.

```text
2 failed in 1.24s
```

### GREEN

The same command passed after the shared translation and runner wiring:

```text
2 passed in 0.67s
```

Affected Repository Tool, policy, DLP, CLI, and multi-agent paths also passed:

```text
107 passed, 1 skipped in 3.45s
```

## Full verification

```text
Full pytest:        777 passed, 3 skipped, 3 known warnings
Ruff lint:          passed
Ruff format check:  210 files already formatted
git diff --check:   passed
```

## Boundaries retained

- Default file-limit behavior remains 262,144 bytes.
- Search and read continue to share the same hard per-file limit.
- CLI/MCP construction, Repository Tool arguments, path safety, Evidence
  selection, source-hash semantics, and failure handling are unchanged.
- `max_scanned_files` and fields without a proven one-to-one mapping remain at
  existing Repository Tool defaults.
- A match beyond a deliberately small hard file boundary may remain unseen;
  separating search-scan and read-output limits requires a separate
  provenance-aware task.

## Files

- `src/specflow/policy/repository_limits.py`
- `src/specflow/runner.py`
- `src/specflow/runner_multi.py`
- `tests/test_repository_policy_wiring.py`
- `docs/tasks/T-074-repository-file-limit-policy-wiring.md`
- `docs/reports/T-074-completion-report.md`
