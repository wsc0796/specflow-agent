# Milestone 4 - Agent Workflow

## Status

Completed.

Milestone 4 establishes the deterministic Agent Workflow layer. The system now
has a state machine, executor, Worker framework, and three real business Workers
that can run in sequence with mock/provider-neutral runtime components.

## Completed tasks

- T-012 Workflow State Machine
  - Legal workflow states and transitions.
  - Ordered transition history.
  - Snapshot restoration with validation.
- T-013 Agent Executor
  - Deterministic step execution.
  - Handler success/failure handling.
  - Workflow advancement through T-012 rules.
- T-014 Worker Framework
  - Worker roles, context, results, metadata, registry, and adapter.
  - Adapter now supports static `WorkerContext` values and dynamic context
    factories for prior-output handoff.
- T-015 Analyze Worker
  - Produces structured `AnalysisOutput`.
  - Uses Prompt, Context, Budget, LLM, Trace, and Fallback layers.
- T-016 Generate Worker
  - Consumes `AnalysisOutput`.
  - Produces structured `GenerationOutput`.
  - Preserves `analysis_hash` lineage.
- T-017 Review Worker
  - Consumes `AnalysisOutput` and `GenerationOutput`.
  - Produces structured `ReviewOutput`.
  - Distinguishes business `REJECT` from runtime failure.

## End-to-end workflow

```text
created
  -> analyzing
  -> generating
  -> reviewing
  -> completed
```

Failure remains explicit:

```text
analyzing | generating | reviewing -> failed
```

Business review rejection is not a workflow failure:

```text
ReviewOutput.decision = REJECT
ReviewOutput.requires_revision = true
WorkflowState = completed
```

## Worker input/output contracts

### AnalyzeWorker

Input:

- user requirement
- validated `ProjectContext`

Output:

- `analysis_json`
- `analysis_hash`

### GenerateWorker

Input:

- user requirement
- validated `ProjectContext`
- prior `analysis_json`

Output:

- `generation_json`
- `generation_hash`
- `analysis_hash`

### ReviewWorker

Input:

- user requirement
- validated `ProjectContext`
- prior `analysis_json`
- prior `generation_json`

Output:

- `review_json`
- `review_hash`
- `analysis_hash`
- `generation_hash`

## Trace and fallback behavior

- Traces are metadata-only.
- Traces identify worker name, role, version, prompt hash, context hash,
  fallback level, and retry count.
- Traces do not store raw prompts, requirements, model responses, or secrets.
- LLM/runtime failures use the existing Fallback System.
- Degraded outputs require review or human review as appropriate.

## Validation

Final M4 validation:

```powershell
uv run pytest tests/test_m4_agent_workflow.py -v
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
git diff --check
```

Result:

- `uv run pytest tests/test_m4_agent_workflow.py -v`: 12 passed.
- `uv run pytest -v`: 254 passed, 1 skipped, 1 warning.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: 75 files already formatted.
- `git diff --check`: passed.

## Git commits

- `8ad0825` - `feat(workflow): add state machine foundation`
- `23e3763` - `feat(executor): add deterministic agent executor`
- `c10e37b` - `feat(workers): add worker framework`
- `39c9885` - `feat(workers): add analyze worker`
- `bd10314` - `feat(workers): add generate worker`
- `fa1e099` - `feat(workers): add review worker`

## Explicit limitations

- No real provider SDK integration.
- No API key loading.
- No automatic code modification.
- No tool calling.
- No Agent Loop or ReAct loop.
- No automatic review/regeneration loop.
- No LangGraph.
- No Redis.
- No RAG, embeddings, or vector database.
- No M5 implementation.

## Next milestone

M5 remains the next permitted milestone. Its scope must be defined by a future
task spec before implementation begins.
