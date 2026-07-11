# SpecFlow Agent

SpecFlow Agent is a spec-driven development assistant for local Python/FastAPI
projects. Its MVP will safely scan a repository, build evidence-backed project
context, structure requirements, generate artifacts, review diffs, and enforce a
deterministic quality gate.

## Current milestone

Milestone 2 is complete — the system can safely scan a repository, identify its
Python/FastAPI technology stack with concrete evidence, and generate a
deterministic, sanitized `PROJECT_CONTEXT.md` artifact.

M3 is complete. T-006 adds a file-based Prompt Registry with versioned prompt
metadata, strict Jinja2 rendering, template-variable validation, and stable
prompt hashes. T-007 adds deterministic context assembly that combines sanitized
project context, prompt definitions, and user requirements into a `BuiltContext`
without calling an LLM. T-008 adds deterministic token budget control with
policy-based trimming and removed-section tracking. T-009 and T-010 add the mock
LLM runtime and metadata-only traces. T-011 adds fallback handling for predictable
degraded results.

M4 is complete. T-012 Workflow State Machine, T-013 Agent Executor, T-014
Worker Framework, T-015 Analyze Worker, T-016 Generate Worker, and T-017 Review
Worker are complete. The system can now
model workflow states, enforce legal transitions, record state history, restore
workflow snapshots, execute abstract step handlers deterministically, define
Worker contracts, register Workers explicitly, adapt Worker results into
Executor steps, and run the first real requirement-analysis Worker using the
existing Prompt, Context, Budget, LLM, Trace, and Fallback layers. It can also
consume `AnalysisOutput` to produce a bounded `GenerationOutput`. It still does
review `GenerationOutput` and distinguish business `REJECT` from execution
failure. It still does not implement automatic code generation or M5 behavior.

## T-001 foundation boundary

T-001 included only the FastAPI application package, `GET /health`, pytest, Ruff,
and setup/development-rule documentation. It deliberately excluded persistence,
project APIs, scanning, technology detection, project-context generation, prompts,
LLMs, workers, and workflow logic; later tasks added those capabilities incrementally.

## Prompt Registry

Prompt assets live under `prompts/` and are managed by Git so behavior changes
can be reviewed as ordinary diffs. The current registry supports loading a
prompt by name and version, validating YAML metadata, checking template variables
against declared `required_variables`, rendering with Jinja2 `StrictUndefined`,
and producing a stable `prompt_hash`.

## Context Builder

The Context Builder combines a sanitized `ProjectContext`, a versioned
`PromptDefinition`, and a user requirement into a deterministic `BuiltContext`.
It tracks sources, carries prompt and project hashes, estimates token count, and
rejects empty or secret-like inputs. It does not scan repositories, call LLMs,
write databases, or modify workflow state.

## Token Budget

The Token Budget Manager accepts a `BuiltContext`, applies a `BudgetPolicy`,
estimates input size deterministically, trims low-priority sections when needed,
records `removed_sections`, and returns a stable `BudgetResult`. It does not
call LLMs, summarize content, use embeddings/RAG, or modify workflow state.

## Runtime Foundation

The runtime foundation now supports provider-neutral LLM requests, deterministic
mock responses, metadata-only trace files, and fallback handling for retry, JSON
repair, and honest degraded baselines. It still does not implement Workers,
Agent Loop, Workflow orchestration, RAG, embeddings, Redis, or LangGraph.

## Workflow State Machine

The Workflow State Machine defines the first M4 boundary. A workflow run starts
in `created` and may move through `analyzing`, `generating`, `reviewing`, and
`completed`, with `failed` available from active states. Illegal transitions and
terminal-state transitions are rejected, while accepted transitions are recorded
in ordered state history.

## Agent Executor

The Agent Executor defines the second M4 boundary. It maps workflow states to
abstract steps, calls fake/stub `StepHandler` implementations, advances the
Workflow State Machine only through legal transitions, records structured
`ExecutionResult` values, and converts handler failures into explicit `failed`
workflow results. Real Workers remain deferred to T-014 and later tasks.

## Worker Framework

The Worker Framework defines the third M4 boundary. It provides `WorkerRole`,
`WorkerContext`, `WorkerResult`, Worker metadata, explicit `WorkerRegistry`
registration, and a `WorkerStepHandler` adapter for the existing Agent Executor.
It now includes `AnalyzeWorker`, the first real business Worker, which produces a
structured `AnalysisOutput` while preserving the Executor/Workflow boundary. It
also includes `GenerateWorker`, which consumes `AnalysisOutput` and produces a
structured `GenerationOutput`. It now includes `ReviewWorker`, which produces a
structured `ReviewOutput` and preserves the rule that `REJECT` is not a runtime
failure.

## Analyze Worker

The Analyze Worker consumes a user requirement and validated `ProjectContext`,
renders the versioned `analyze_requirement` prompt through the Context Builder,
applies token budgeting, calls the provider-neutral LLM abstraction, records a
metadata-only trace, and falls back to an honest degraded analysis when runtime
execution or structured parsing fails. Its output is a stable JSON
`AnalysisOutput` plus `analysis_hash`.

## Generate Worker

The Generate Worker consumes the original user requirement, validated
`ProjectContext`, and prior `AnalysisOutput`. It renders the versioned
`generate_spec` prompt, applies token budgeting, calls the provider-neutral LLM
abstraction, records a metadata-only trace, and falls back to an honest degraded
generation result when runtime execution or structured parsing fails. Its output
is a stable JSON `GenerationOutput` plus `generation_hash`.

## Review Worker

The Review Worker consumes the original user requirement, validated
`ProjectContext`, prior `AnalysisOutput`, and prior `GenerationOutput`. It
renders the versioned `review_generation` prompt, applies token budgeting, calls
the provider-neutral LLM abstraction, records a metadata-only trace, and returns
a stable JSON `ReviewOutput` plus `review_hash`. A business `REJECT` remains a
successful Worker execution and allows the workflow to complete; runtime or
input failures still fail the workflow.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Setup and run

```powershell
uv sync --all-groups
uv run uvicorn specflow.main:app --reload
```

Open `http://127.0.0.1:8000/health`. Expected response:

```json
{"status":"ok"}
```

Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

To register a project record (this does not scan or validate the path yet):

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/projects `
  -ContentType 'application/json' `
  -Body '{"name":"Example API","repository_path":"C:\\projects\\example-api"}'
```

## Verification

```powershell
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```

## Development process

Read `AGENTS.md`, the frozen baseline, and one active task document before making a
change. Each task must have tests, a completion report, and one focused Git commit.
