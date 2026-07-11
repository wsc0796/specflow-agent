# T-012 - Workflow State Machine

## Goal

Start Milestone 4 by creating the deterministic Workflow State Machine layer.
This task defines how an Agent workflow run moves between states, records state
history, and can be restored from recorded state without introducing Workers,
LLM calls, or orchestration behavior.

## In scope

- `src/specflow/workflow/` module.
- Workflow state model.
- Transition rules.
- Workflow engine for state transitions.
- State history entries.
- Workflow restoration from current state and history.
- Unit tests for legal transitions, illegal transitions, history, and recovery.

## Out of scope

- Worker framework.
- Agent executor.
- Analyze Worker.
- Generate Worker.
- Review Worker.
- LLM calls.
- Prompt rendering.
- Token budgeting.
- Trace recording.
- Fallback execution.
- LangGraph.
- RAG or embeddings.
- Redis or database persistence.
- Automatic code generation.

## Required states

- `created`
- `analyzing`
- `generating`
- `reviewing`
- `completed`
- `failed`

## Required behavior

The Workflow State Machine must:

1. Start every new workflow run in `created`.
2. Allow only explicit legal transitions.
3. Reject illegal transitions with a clear workflow error.
4. Record every accepted transition in deterministic order.
5. Allow the current state to be queried.
6. Restore a workflow engine from a known current state and history.
7. Treat terminal states as terminal: `completed` and `failed` cannot transition
   further.

## Legal transitions

```text
created -> analyzing
analyzing -> generating
analyzing -> failed
generating -> reviewing
generating -> failed
reviewing -> completed
reviewing -> failed
```

No other transitions are valid in T-012.

## Models

`WorkflowState`:

- enum of supported states.

`StateTransition`:

- `from_state`
- `to_state`
- `reason`
- `sequence`

`WorkflowSnapshot`:

- `current_state`
- `history`

## Acceptance criteria

1. A new workflow run starts in `created`.
2. The happy path can move through:
   `created -> analyzing -> generating -> reviewing -> completed`.
3. Failure can happen from active states:
   `analyzing`, `generating`, or `reviewing`.
4. Illegal transitions are rejected.
5. Terminal states reject further transitions.
6. State history records accepted transitions in order.
7. A workflow engine can be restored from a snapshot and continue from the
   restored current state if that state is not terminal.
8. The implementation does not introduce Worker, Agent Executor, LLM calls,
   LangGraph, RAG, embeddings, Redis, database persistence, or automatic code
   generation.

## Validation

Before completion:

```powershell
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```

Write a completion report under `docs/reports/`, create one focused Git commit,
and push to GitHub. Do not start T-013.
