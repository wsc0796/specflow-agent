# T-007 completion report - Context Builder

## Result

Implemented a deterministic Context Builder that assembles a sanitized
`ProjectContext`, a T-006 `PromptDefinition`, a user requirement, and optional
runtime variables into a structured `BuiltContext`. The builder prepares future
LLM input without calling an LLM, scanning repositories, writing databases, or
touching workflow state.

## Scope delivered

- Created `docs/tasks/T-007-context-builder.md` and froze the task boundary.
- Added `src/specflow/context_builder/` modules:
  - `models.py`
  - `builder.py`
  - `serializer.py`
  - `exceptions.py`
  - `__init__.py`
- Added `tests/test_context_builder.py`.
- Updated `README.md` and `AGENTS.md`.

## Acceptance evidence

| Requirement | Evidence |
| --- | --- |
| Normal context build | `ContextBuilder.build()` returns `BuiltContext` |
| Prompt variable rendering | Tests verify `project_context` and `user_requirement` appear in rendered user message |
| Missing prompt variable failure | `MissingPromptVariableError` coverage through `PromptDefinition.render()` |
| Stable hash | Equal inputs produce equal `context_hash` |
| Variable order determinism | Different insertion order produces equal output and hash |
| Source tracking | Sources include `PROJECT_CONTEXT.md`, prompt name/version/hash, and project context hash |
| Sensitive values do not reappear | Sanitized evidence remains safe; raw secret-like evidence is rejected |
| Empty or unsupported ProjectContext failure | `ContextBuildError` coverage |
| No LLM / scan / Worker / runtime Workflow | No provider SDK, scanner, repository traversal, worker module, runtime workflow mutation, database write, Redis, LangGraph, RAG, or vector store |

## Validation

```powershell
uv run pytest tests/test_context_builder.py -v
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```

Result:

- `uv run pytest tests/test_context_builder.py -v`: 13 passed.
- `uv run pytest -v`: 105 passed, 1 skipped, 1 warning.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: 24 files already formatted.

## Known limits

- Token count is a deterministic character-based estimate, not a provider
  tokenizer result.
- The builder does not trim or budget context; that remains T-008.
- The builder does not create LLM requests or call an LLM; that remains T-009.
- The builder does not record traces; that remains T-010.

## Next task

T-008 may implement the Token Budget Manager. It must not call an LLM or
introduce Worker orchestration.
