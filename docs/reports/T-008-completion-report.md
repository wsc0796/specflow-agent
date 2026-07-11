# T-008 completion report - Token Budget Manager

## Result

Implemented a deterministic Token Budget Manager that accepts a T-007
`BuiltContext`, applies a `BudgetPolicy`, estimates token usage, detects budget
overflow, trims lower-priority sections, records `removed_sections`, and returns
a stable `BudgetResult`.

## Preflight note

`docs/records/M3-agent-infrastructure.md` was requested as preflight context but
does not exist yet because M3 is still in progress. T-008 did not create or close
the M3 milestone record.

## Scope delivered

- Created `docs/tasks/T-008-token-budget.md`.
- Added `src/specflow/token_budget/` modules:
  - `models.py`
  - `manager.py`
  - `estimator.py`
  - `exceptions.py`
  - `__init__.py`
- Added `tests/test_token_budget.py`.
- Updated `README.md` and `AGENTS.md`.

## Acceptance evidence

| Requirement | Evidence |
| --- | --- |
| Token estimation | `TokenEstimator` character-based deterministic estimate |
| Budget Policy | `BudgetPolicy` with max/reserved/input budget and section priorities |
| Over-limit detection | Oversized context triggers trimming |
| Deterministic trimming | Same input and policy produce same removed sections and hash |
| Priority preservation | Requirement/project overview/technology stack survive before unknowns/warnings/evidence |
| removed_sections tracking | `RemovedSection` records name, estimated tokens, and priority |
| Stable context_hash | `BudgetResult.context_hash` and trimmed `BuiltContext.context_hash` are stable |
| Sensitive values do not reappear | Redacted values remain redacted after budgeting |
| Invalid budget failure | Impossible or invalid policies raise `TokenBudgetError` |
| No LLM / summary / RAG / Worker / Workflow | No provider SDK, summarization, embeddings, worker module, runtime workflow mutation, database write, Redis, LangGraph, RAG, or vector store |

## Validation

```powershell
uv run pytest tests/test_token_budget.py -v
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```

Result:

- `uv run pytest tests/test_token_budget.py -v`: 14 passed.
- `uv run pytest -v`: 119 passed, 1 skipped, 1 warning.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: 31 files already formatted.

## Known limits

- Token estimation is deterministic and character-based; provider-specific
  tokenizers remain out of scope.
- Trimming removes sections; it does not summarize or compress them.
- The manager budgets already-built context only; it does not render prompts or
  build LLM requests.
- LLM Client remains deferred to T-009.

## Next task

T-009 may implement the LLM Client. Do not start Worker orchestration.
