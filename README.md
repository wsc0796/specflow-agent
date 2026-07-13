# SpecFlow Agent

A controlled multi-agent repository-analysis system for local Python projects.
It turns a requirement plus read-only repository evidence into structured
analysis, a technical plan, test strategy, risk review and auditable artifacts.
The orchestration is built from scratch without LangGraph or agent frameworks.

## Highlights

- **6-agent fixed topology** with Coordinator-driven deterministic orchestration
- **Parallel specialist execution** — Design, Test Strategy, and Risk Review run concurrently
- **Bounded Revision loop** — max 1 round, business rejection ≠ infrastructure failure
- **Repository evidence pipeline** — read-only tools → evidence → agent prompts → traceable references
- **Structured Agent Handoff** — schema-validated, canonical-JSON-hashed payloads between agents
- **Fail-closed production boundaries** — required-agent failure stops the run; input and output contracts are validated
- **Execution policy** — bounded LLM calls, revisions, wall time, evidence/tool limits, and classified retry behavior
- **Agent-level trace topology** — stage timing, parent/child spans, submission/completion timestamps
- **Dual pipeline** — legacy linear (Analyze→Generate→Review) preserved as A/B baseline
- **Live Provider validated** — DeepSeek v4-flash on sky-takeout-python: 6/6 agents, 7 handoffs, PASS
- **Reproducible benchmark** — 12 committed mock cases with a normalized artifact-contract baseline

## Quick start

```powershell
# Legacy linear pipeline (default)
uv run specflow run --repo . --requirement "Add a search endpoint" --output ./out --mock

# Multi-agent pipeline (Live Provider)
$env:SPECFLOW_LLM_BASE_URL = "https://api.deepseek.com"
$env:SPECFLOW_LLM_API_KEY = "<key>"
uv run specflow run --mode multi-agent --provider openai-compatible --model deepseek-v4-flash --repo . --requirement "Add a search endpoint" --output ./out
```

## Portfolio benchmark (mock-only)

Run the committed 12-case fixture suite through the existing multi-agent
pipeline. It produces ignored per-case artifacts plus a normalized, commit-safe
baseline; it proves deterministic artifact and schema contracts, not live model
quality.

```powershell
uv run specflow benchmark `
  --suite benchmarks/cases `
  --repo benchmarks/fixtures/portfolio-python `
  --output artifacts/benchmark-t048 `
  --baseline benchmarks/results/mock-baseline.json
```

Inspect `artifacts/benchmark-t048/benchmark-report.json` for runtime metrics
(including latency) and `benchmarks/results/mock-baseline.json` for the stable
portfolio baseline.

For a credential-free walkthrough, read
`docs/demo/portfolio-release-demo.md`. It distinguishes mock contract evidence
from the separately documented M6 live-provider validation.

## Current milestone

**M8 independent-review remediation — CLOSED on
`feature/m8-production-hardening`; not merged to `main`.** The follow-up T-040
and T-041 work adds RuntimeGuard budget enforcement and strict inter-agent
payload schemas. The current local baseline is **661 passed, 2 skipped, 3 known
warnings**. M8 is local mock acceptance and does not claim a new live-provider
run. See `docs/reports/T-040-completion-report.md`,
`docs/reports/T-041-completion-report.md`, and
`docs/roadmap/2026-07-13-portfolio-release-plan.md`.

M6 remains the latest live-provider validation milestone. M8 validation in this
repository is local mock acceptance; it does not add a new live-provider claim.

M1–M5 milestones (project scanning, technology detection, prompt/context/token
infrastructure, LLM client, trace/fallback, workflow state machine, worker
framework, tool framework, CLI, evaluation) are also complete.
See `docs/records/` for full history.

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

## Tool Framework

The Tool Framework starts M5. It provides `ToolMetadata`, `ToolCall`,
`ToolResult`, `ToolStatus`, a Tool Protocol, explicit `ToolRegistry`, and
`ToolExecutor`. T-018 includes only fake-tool tests and keeps Tool execution
independent of workflow state, retries, and automatic selection.

## Safe Repository Tools

T-019 adds `list_files`, `search_code`, and `read_file` as explicit Tools bound
to one validated repository root. Access rejects absolute paths, traversal,
symlink/reparse-point paths, ignored dependency/cache directories, sensitive
filenames, binary reads, and unbounded output. Search is literal and implemented
in Python without shell or subprocess use. Returned paths are relative and file
content is sanitized. These tools are read-only and cannot modify a repository.

## OpenAI-compatible Provider

T-020 adds a synchronous Provider that implements the existing `LLMClient`
Protocol without a vendor SDK. It reads an HTTP(S) base URL, API key, model, and
timeout from explicit configuration or `SPECFLOW_LLM_*` environment variables,
performs one `/chat/completions` request, and maps the response into the existing
`LLMResponse` and `LLMUsage` models. It does not retry, call fallback, log prompts,
or expose provider error bodies. `MockLLMClient` remains the default test double.

## Repository Evidence Pipeline

T-021 adds a bounded, deterministic evidence collection pipeline that bridges the
Tool Framework with the M4 Agent Workflow. The `EvidenceCollector` extracts
search keywords from the requirement, uses `list_files` / `search_code` /
`read_file` tools to gather real repository evidence, ranks files by match
relevance, and produces a stable `EvidenceBundle` with a deterministic hash.
The serialized evidence is injected into `WorkerContext.project_context` for
consumption by the Analyze/Generate/Review Worker chain. All tool calls are
recorded as sanitized `ToolCallRecord` entries. The pipeline enforces hard
limits on keywords, tool calls, selected files, and total evidence characters.

Example process configuration (use your own provider values and never commit the
real key):

```powershell
$env:SPECFLOW_LLM_BASE_URL = "https://provider.example/v1"
$env:SPECFLOW_LLM_API_KEY = "<set-locally>"
$env:SPECFLOW_LLM_MODEL = "provider-model"
$env:SPECFLOW_LLM_TIMEOUT_SECONDS = "60"
```

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
