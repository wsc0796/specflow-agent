# T-018 - Tool Framework & Registry

## Goal

Start M5 Tool Use & Repository Intelligence by creating a unified, explicit, and
safe Tool Framework.

T-018 defines how tools are described, registered, looked up, and executed once.
It does not implement any real repository tools.

## Building

- Tool metadata.
- Tool call/request model.
- Tool result model.
- Tool status enum.
- Tool Protocol.
- Tool Registry.
- Tool Executor.
- Structured error contract.
- Sensitive information sanitization.
- Fake Tool tests.

## Not building

- Read-only repository tools.
- File reading.
- Code search.
- Shell or PowerShell tools.
- `subprocess`.
- Network requests.
- Database access.
- Git operations.
- Permission Policy.
- Worker Tool Integration.
- Tool loops.
- Automatic tool selection.
- Tool Calling LLM schema.
- T-019 or later tasks.

## Architecture boundary

```text
Future Worker
  -> ToolCall
  -> ToolExecutor
  -> ToolRegistry
  -> Tool Protocol
  -> Fake Tool in tests only
```

Responsibilities:

- `ToolRegistry`: explicit registration and deterministic lookup.
- `ToolExecutor`: execute exactly one explicit `ToolCall` and convert failures
  into structured `ToolResult` values.
- `Tool`: perform one operation.
- Permission decisions remain deferred to T-020.
- Worker integration remains deferred to T-021.

## Required models

`ToolMetadata`:

- `name`
- `version`
- `description`
- `input_model`
- `output_model`
- `deterministic`
- `read_only`

`ToolCall`:

- `call_id`
- `tool_name`
- `arguments`
- `metadata`

`ToolStatus`:

- `success`
- `failed`

`ToolResult`:

- `call_id`
- `tool_name`
- `status`
- `output`
- `metadata`
- `error_type`
- `error_message`
- `requires_review`

## Required behavior

1. Tool names use stable lowercase identifiers.
2. Tool versions are explicit and stable.
3. Tool metadata is deterministic and serializable.
4. Tool calls contain only structured serializable arguments and metadata.
5. Tool results enforce success/failure consistency.
6. Error messages and metadata are sanitized.
7. Registry rejects duplicate names.
8. Registry lookup of missing tools fails clearly.
9. Registry metadata listing is deterministic and independent of registration
   order.
10. Executor only executes explicitly registered tools.
11. Executor does not accept arbitrary Python callables.
12. Executor executes exactly one target tool per call.
13. Executor does not mutate workflow state.
14. Executor does not call Workers.
15. Executor does not retry, call fallback, loop, or select tools automatically.

## Validation

Before completion:

```powershell
uv sync --all-groups
uv run pytest tests/test_tool_framework.py -v
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
git diff --check
git status --short
```

Write a completion report under `docs/reports/`, create one focused Git commit,
and push to GitHub. Do not start T-019.
