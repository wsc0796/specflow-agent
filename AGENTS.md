# SpecFlow Agent Development Rules

## Current phase

The project has completed Milestone 3 (Agent Runtime Foundation), Milestone 4
(Agent Workflow), and started Milestone 5 (Tool Use & Repository Intelligence).
T-012 Workflow State Machine, T-013 Agent
Executor, T-014 Worker Framework, T-015 Analyze Worker, T-016 Generate Worker,
T-017 Review Worker, T-018 Tool Framework, T-019 Read-only Repository Tools,
T-020 OpenAI-compatible LLM Provider, T-021 Repository-aware Agent
Integration, T-022 CLI and Artifact Delivery, and T-023 Phase A real-repository
Mock evaluation preparation are completed. Implemented:
health endpoint, Project persistence API, safe scanning, deterministic technology
identification with evidence, sanitized PROJECT_CONTEXT.md generation, Prompt
Registry, Context Builder, Token Budget Manager, LLM Client abstraction, Trace
System, Fallback System, deterministic workflow state transitions, and
deterministic Agent Executor step advancement, Worker Framework contracts, the
first real requirement-analysis Worker, a generation Worker that consumes
AnalysisOutput, a review Worker that distinguishes business REJECT from
execution failure, explicit Tool models, Registry, and Executor contracts, plus
repository-root-bound `list_files`, `search_code`, and `read_file` tools with
bounded, sanitized output, plus one configurable Provider that maps a single
OpenAI-compatible HTTP completion into the existing LLM contracts, and a bounded
deterministic evidence collection pipeline that uses the Tool Framework to feed
real repository evidence into the Analyze/Generate/Review Worker chain, plus a
`specflow run` CLI with structured JSON + Markdown artifact delivery, plus a
deterministic real-repository evaluation layer and safe Live Artifact import
validation. The next permitted work is T-023 Live Artifact validation only.
M5 must not be closed until a user supplies a non-mock Live artifact.
Future task IDs are not permission to implement future features.

## Mandatory workflow

1. Read `docs/00-SPEC-BASELINE.md`, this file, and the active task spec before editing.
2. Implement one task at a time; keep changes small and testable.
3. Do not add dependencies unless the active task needs them.
4. Before completion, run `uv run pytest -v`, `uv run ruff check .`, and
   `uv run ruff format --check .`.
5. Write a completion report in `docs/reports/` and make one focused Git commit.
6. After every completed task, update its completion report. After every completed
   milestone, add a dated milestone record under `docs/records/` covering delivered
   capabilities, validation evidence, commit IDs, known limits, and the next gate.
7. After the milestone quality gate passes, push its reviewed commits and milestone
   record to the configured GitHub `origin`. Never push without a configured remote
   or after a failed quality gate; report that configuration blocker instead.

## Architecture constraints

- Use the `src/` layout.
- M4 work must proceed one task spec at a time. Do not introduce Worker
  orchestration without an explicit active Worker/Executor task spec.
- Do not add prompts, workers, LLM calls, workflow orchestration, Redis,
  LangGraph, vector stores, MCP, Java support, or automatic code changes before
  their explicitly assigned task.
- Keep HTTP-boundary code separate from future business and persistence layers.
- Never weaken tests merely to make them pass.

## Commands

```powershell
uv sync --all-groups
uv run uvicorn specflow.main:app --reload
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```
