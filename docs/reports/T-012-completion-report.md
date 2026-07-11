# T-012 completion report - Workflow State Machine

## Result

Implemented the deterministic Workflow State Machine that starts M4 Agent
Workflow without introducing Worker execution, LLM calls, LangGraph, RAG,
embeddings, Redis, or automatic code generation.

## Scope delivered

- Created `docs/tasks/T-012-workflow-state-machine.md`.
- Added `src/specflow/workflow/` modules:
  - `models.py`
  - `transitions.py`
  - `engine.py`
  - `exceptions.py`
  - `__init__.py`
- Added `tests/test_workflow.py`.
- Updated `README.md` and `AGENTS.md` to show T-012 as the current M4 entry
  point.

## Acceptance evidence

| Requirement | Evidence |
| --- | --- |
| New workflow starts in `created` | `test_new_workflow_starts_created` |
| Happy path reaches `completed` | `test_happy_path_transitions_to_completed_with_history` |
| Active states can fail | `test_active_states_can_transition_to_failed` |
| Illegal transitions rejected | `test_illegal_transition_is_rejected` |
| Terminal states reject further transitions | `test_terminal_states_reject_further_transitions` |
| State history is ordered | Happy-path and restore tests assert contiguous sequence values |
| Workflow can restore and continue | `test_workflow_can_restore_from_snapshot_and_continue` |
| Invalid recovery snapshots rejected | Restore rejection tests, including advanced state without history |
| No T-013 behavior | No Worker, Agent Executor, LLM call, LangGraph, RAG, embeddings, Redis, or code generation |

## Validation

```powershell
uv run pytest tests\test_workflow.py -v
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```

Result:

- `uv run pytest tests\test_workflow.py -v`: 12 passed.
- `uv run pytest -v`: 147 passed, 1 skipped, 1 warning.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: 55 files already formatted.

## Known limits

- Workflow state is in memory only.
- No Worker execution exists yet.
- No Agent Executor exists yet.
- No persisted workflow run storage exists yet.
- T-013 remains deferred.
