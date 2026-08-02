# Phase 1 Task Brief Wiring Completion Report

## Scope

Phase 1 establishes strict, role-scoped Task Brief generation and execution inputs, injects each
brief into the corresponding real `AgentRunner` request, and persists metadata-only lifecycle
evidence. It does not change the legacy worker path, Review/Revision semantics, RuntimeGuard, or
the committed mock benchmark baseline.

## Delivered Contract

- Strict, frozen Pydantic models separate fixed identity fields from model-generated advice.
- Enrichment receives the original requirement, fixed role definition, controlled evidence, and
  role output schema. Invalid provider, JSON, schema, or evidence-reference output becomes an
  explicit deterministic degraded brief.
- `AgentExecutionInput` fails closed on missing or mismatched identity, role, output schema, or
  evidence reference.
- Worker requests use five explicit sections: requirement, verified evidence, role brief,
  validated prior outputs, and role output contract.
- `task-briefs.json`, manifest metadata, and `TASK_BRIEF_GENERATED` / `TASK_BRIEF_CONSUMED` events
  provide versioned, canonical-hash audit evidence without storing full prompts in trace.

## Critical Evidence

`test_task_brief_change_changes_only_target_real_llm_request_section` captures the final
`LLMRequest` twice with identical requirement, evidence, prior outputs, and output contract. It
changes only the target Task Brief and asserts that only `[Role Task Brief]` changes. Integration
tests drive all six production `AgentRunner` request builders through a deterministic fake provider
and prove role isolation plus one consumed event per submitted worker request.

## Validation

- Targeted Task Brief, planning, multi-agent, AgentRunner, and benchmark tests: `84 passed`.
- Full suite: `723 passed, 2 skipped, 3 warnings`.
- Mock benchmark: `12/12`; committed baseline unchanged and byte-identical.
- Repository security suite: `164 passed, 2 skipped`; MCP suite: `31 passed`.
- Ruff lint and format checks, repository secret scan, sdist/wheel build, version smoke, and CLI
  help smoke all passed.

## Known Limits

Enrichment provider calls remain outside unified RuntimeGuard accounting; token usage and
`agent_count` semantics remain unresolved. Review findings still do not drive revisions. This phase
provides deterministic mock-provider request evidence, not live-provider validation or proof that
Task Briefs improve output quality.
