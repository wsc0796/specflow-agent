# T-016 completion report - Generate Worker

## Result

Implemented `GenerateWorker`, the second real business Worker in M4.

The Worker consumes a valid T-015 `AnalysisOutput`, uses the existing M3 runtime
components, and returns a deterministic `GenerationOutput` serialized through
the T-014 `WorkerResult` contract.

## Scope delivered

- Created `docs/tasks/T-016-generate-worker.md`.
- Added `src/specflow/workers/generate.py`.
- Exported `GenerateWorker` and `GenerationOutput` from `specflow.workers`.
- Updated `prompts/generate_spec/` to request structured JSON output and include
  the original user requirement.
- Added `tests/test_generate_worker.py`.
- Updated `README.md` and `AGENTS.md`.

## Runtime integration

`GenerateWorker` uses dependency injection for:

- `PromptRegistry`
- `ContextBuilder`
- `TokenBudgetManager`
- `LLMClient`
- `TraceRecorder`
- `FallbackManager`

No real provider SDK, API key loading, tool calling, command execution, or code
modification was added. Tests use `MockLLMClient`.

## Input contract

`GenerateWorker` requires `analysis_json` in `WorkerContext.prior_outputs`.
Missing or invalid analysis output returns a controlled `WorkerResult` failure.

Degraded analysis output is allowed to continue, but generated output propagates:

- `degraded=true`
- `requires_review=true`
- original `analysis_hash`

## Output contract

`GenerationOutput` includes:

- `requirement_summary`
- `proposed_solution`
- `architecture_or_design`
- `affected_components`
- `implementation_steps`
- `api_or_data_changes`
- `test_plan`
- `risks`
- `acceptance_criteria_mapping`
- `analysis_hash`
- `requires_review`
- `degraded`
- `generation_hash`

The Worker returns:

- `generation_json`
- `generation_hash`
- `analysis_hash`

inside `WorkerResult.output`.

## Fallback and degraded behavior

- LLM runtime failure uses the existing `FallbackManager`.
- Invalid structured responses become honest degraded generation outputs.
- Every degraded result sets `requires_review=true`.
- Degraded outputs are still successful Worker executions because the Worker
  produced a controlled result.

## Trace behavior

Trace records are metadata-only and include:

- worker name, role, and version
- prompt name/version/hash
- context hash
- fallback level
- retry count

Trace records do not store raw prompt content, raw requirement text, model
response content, or secret values.

## Test scenarios

- Normal generation output.
- Missing `AnalysisOutput` failure.
- Invalid `AnalysisOutput` failure.
- Degraded analysis propagation.
- `analysis_hash` preservation.
- Structured acceptance-criteria mapping.
- Stable implementation-step ordering.
- No code-modification output.
- Mock LLM response consumption.
- LLM failure through fallback.
- Invalid structured response controlled degradation.
- Sensitive data not leaking to output or trace.
- WorkerResult contract.
- `WorkerStepHandler` / `AgentExecutor` integration.
- Same generate step executes only once.
- Stable generation hash.

## Validation

```powershell
uv run pytest tests/test_generate_worker.py -v
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
git diff --check
```

Result:

- `uv run pytest tests/test_generate_worker.py -v`: 16 passed.
- `uv run pytest -v`: 227 passed, 1 skipped, 1 warning.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: 72 files already formatted.
- `git diff --check`: passed.

## Known limits

- No Review Worker.
- No automatic review loop.
- No real provider SDK integration.
- No repository code modification.
- T-017 Review Worker remains the next permitted task.
