# T-017 completion report - Review Worker

## Result

Implemented `ReviewWorker`, the third real business Worker in M4.

The Worker consumes valid T-015 `AnalysisOutput` and T-016 `GenerationOutput`,
uses the existing M3 runtime components, and returns a deterministic
`ReviewOutput` serialized through the T-014 `WorkerResult` contract.

## Scope delivered

- Created `docs/tasks/T-017-review-worker.md`.
- Added `prompts/review_generation/`.
- Added `src/specflow/workers/review.py`.
- Exported `ReviewWorker`, `ReviewOutput`, `ReviewIssue`, and `ReviewDecision`
  from `specflow.workers`.
- Added `tests/test_review_worker.py`.
- Updated `README.md` and `AGENTS.md`.

## Runtime integration

`ReviewWorker` uses dependency injection for:

- `PromptRegistry`
- `ContextBuilder`
- `TokenBudgetManager`
- `LLMClient`
- `TraceRecorder`
- `FallbackManager`

No real provider SDK, API key loading, tool calling, command execution, code
modification, or automatic review loop was added. Tests use `MockLLMClient`.

## Critical semantic boundary

`decision=REJECT` is a business review result, not an execution failure.

- `REJECT` returns `WorkerResult.success=true`.
- `REJECT` sets `requires_revision=true`.
- The workflow can still transition from `reviewing` to `completed`.
- Missing required inputs or Worker failures still cause `AgentExecutor` to
  transition to `failed`.

## Output contract

`ReviewOutput` includes:

- `decision`
- `summary`
- `issues`
- `missing_requirements`
- `risk_findings`
- `acceptance_criteria_results`
- `severity`
- `requires_revision`
- `requires_human_review`
- `analysis_hash`
- `generation_hash`
- `degraded`
- `review_hash`

`ReviewIssue` includes:

- `code`
- `severity`
- `message`
- `related_requirement`
- `suggestion`

## Fallback and degraded behavior

- LLM runtime failure uses the existing `FallbackManager`.
- Invalid structured responses become honest degraded review outputs.
- Degraded review outputs require human review.
- Upstream degraded analysis or generation propagates to review human-review
  requirements.

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

- PASS review output.
- REJECT review as successful Worker execution.
- REJECT workflow completion.
- Worker input failure drives workflow failure.
- Missing analysis input.
- Missing generation input.
- Hash lineage preservation.
- Issue ordering and severity.
- Acceptance criteria checks.
- Upstream degraded propagation.
- LLM failure through fallback.
- Invalid response controlled degradation.
- Sensitive data sanitization.
- No automatic rework loop.
- Stable review hash.

## Validation

```powershell
uv run pytest tests/test_review_worker.py -v
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
git diff --check
```

Result:

- `uv run pytest tests/test_review_worker.py -v`: 15 passed.
- `uv run pytest -v`: 242 passed, 1 skipped, 1 warning.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: 74 files already formatted.
- `git diff --check`: passed.

## Known limits

- No automatic review loop.
- No real provider SDK integration.
- No repository code modification.
- M4 end-to-end integration and milestone record remain next.
