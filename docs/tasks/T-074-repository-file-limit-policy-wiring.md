# T-074 — Repository File Limit Policy Wiring

- Status: CLOSED
- Owner: learner decision and reproduction; Codex implementation
- Branch: `codex/t072-no-evidence-fail-closed`
- Source finding: Day 7 Control Coverage and correctness-failure exercise

## Problem

Both the legacy and multi-agent runners accept an `ExecutionPolicy`, but each
constructs `RepositoryToolSet(repo)` without translating
`policy.repository.max_file_bytes` into `RepositoryPolicyLimits`. A run
configured with a five-byte file limit can therefore read a larger file without
marking the Repository Tool result as truncated.

## Goal

Make the existing execution-policy file limit govern Repository Tools in both
runner modes through one explicit, shared policy translation while preserving
the default behavior and existing repository safety boundary.

## Requirements

- **REQ-074-1:** Legacy and multi-agent runners must translate
  `policy.repository.max_file_bytes` into the `RepositoryPolicyLimits` supplied
  to `RepositoryToolSet`.
- **REQ-074-2:** The translation must be implemented once and reused by both
  runners.
- **REQ-074-3:** Only `max_file_bytes` is translated in this task. Tool-limit
  fields without a proven one-to-one semantic mapping must retain their current
  defaults.
- **REQ-074-4:** With a five-byte configured limit and a matching file whose
  content begins with the search term, both runners must complete successfully
  and record the `read_file` ToolCall as truncated.
- **REQ-074-5:** Default-policy behavior, CLI/MCP construction, Repository Tool
  path checks, Evidence selection, and failure semantics must remain unchanged.

## Non-goals

- Split search-scan and read-output byte limits.
- Change provenance or source-hash semantics.
- Map `max_scanned_files`, `max_selected_files`, `max_evidence_items`, or fields
  with different names in `RepositoryPolicyLimits`.
- Remove or repurpose `EvidenceCollectionConfig.max_file_bytes`.
- Change Agent permissions, Retrieval, Vector, Hybrid, Rerank, topology, or
  Provider behavior.

## Allowed scope

- `src/specflow/policy/repository_limits.py`
- `src/specflow/runner.py`
- `src/specflow/runner_multi.py`
- `tests/test_repository_policy_wiring.py`
- `docs/tasks/T-074-repository-file-limit-policy-wiring.md`
- `docs/reports/T-074-completion-report.md`

## Forbidden scope

- Repository Tool behavior or public Tool arguments.
- `RepositoryAccessPolicy`, `ReadFileTool`, `SearchCodeTool`, and
  `EvidenceCollector` implementation.
- CLI/MCP configuration and defaults.
- Other ExecutionPolicy fields or unrelated refactors.
- Study-state files unless separately requested.

## Acceptance criteria

- **AC-074-1:** Given a legacy mock run with
  `policy.repository.max_file_bytes=5` and a file beginning with the matching
  term, the run returns `0` and its `read_file` ToolCall record has
  `truncated=true`.
- **AC-074-2:** Given the equivalent multi-agent mock run, the run returns `0`
  and its `read_file` ToolCall record has `truncated=true`.
- **AC-074-3:** Both runners obtain Repository Tool limits from the same
  translation function.
- **AC-074-4:** The translation preserves all unrelated
  `RepositoryPolicyLimits` defaults.
- **AC-074-5:** Focused tests, full pytest, Ruff lint, Ruff format check, and
  `git diff --check` pass.

## Test-first plan

1. Add one behavior test for each runner using the same five-byte fixture.
2. Run the focused tests and confirm RED because `read_file.truncated` is
   currently `false`.
3. Add the shared translation and connect both runners.
4. Run the focused tests and confirm GREEN.
5. Run the repository quality gate and record evidence in the completion
   report.

## Risks and boundaries

- The five-byte value is a deterministic test probe, not a recommended
  production threshold.
- `max_file_bytes` remains the shared hard per-file limit for search and read.
  A match beyond that boundary may produce no Evidence; changing that contract
  requires a separate provenance-aware task.
- Default execution remains at 262,144 bytes, so the ordinary default path is
  expected to retain its current behavior.
