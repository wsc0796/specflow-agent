# T-015 completion report - Analyze Worker

## Result

Implemented the first real business Worker: `AnalyzeWorker`.

The Worker analyzes a user requirement against a validated `ProjectContext`,
uses the existing M3 runtime components, and returns a deterministic
`AnalysisOutput` serialized through the T-014 `WorkerResult` contract.

## Scope delivered

- Created `docs/tasks/T-015-analyze-worker.md`.
- Added `src/specflow/workers/analyze.py`.
- Exported `AnalyzeWorker` and `AnalysisOutput` from `specflow.workers`.
- Updated `prompts/analyze_requirement/template.md` to request the structured
  analysis contract.
- Added `tests/test_analyze_worker.py`.
- Updated `README.md` and `AGENTS.md`.

## Runtime integration

`AnalyzeWorker` uses dependency injection for:

- `PromptRegistry`
- `ContextBuilder`
- `TokenBudgetManager`
- `LLMClient`
- `TraceRecorder`
- `FallbackManager`

No real provider SDK or API key loading was added. Tests use `MockLLMClient`.

## Output contract

`AnalysisOutput` includes:

- `requirement_summary`
- `goals`
- `non_goals`
- `assumptions`
- `affected_components`
- `risks`
- `acceptance_criteria`
- `evidence`
- `requires_review`
- `degraded`
- `analysis_hash`

The Worker returns:

- `analysis_json`
- `analysis_hash`

inside `WorkerResult.output`.

## Fallback and degraded behavior

- LLM runtime failure uses the existing `FallbackManager`.
- Invalid structured responses become honest degraded analysis outputs.
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

- Valid Worker metadata.
- Normal requirement analysis.
- Empty requirement rejection through `WorkerContext`.
- Invalid project context controlled failure.
- Structured output validation.
- Stable affected component ordering.
- Stable acceptance criteria ordering.
- Source evidence preservation.
- Mock LLM response consumption.
- LLM failure through fallback.
- Invalid structured response controlled degradation.
- Degraded result requires review.
- Trace metadata presence.
- Trace content safety.
- `WorkerStepHandler` / `AgentExecutor` integration.
- Worker does not mutate workflow state.
- Stable output hash for identical inputs.

## Validation

```powershell
uv sync --all-groups
uv run pytest tests/test_analyze_worker.py -v
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
git diff --check
```

Result:

- `uv run pytest tests/test_analyze_worker.py -v`: 22 passed.
- `uv sync --all-groups`: passed.
- `uv run pytest -v`: 211 passed, 1 skipped, 1 warning.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: 70 files already formatted.
- `git diff --check`: passed.

## Known limits

- No Generate Worker.
- No Review Worker.
- No automatic workflow loop.
- No real provider SDK integration.
- No repository code modification.
- T-016 Generate Worker remains the next permitted task.
