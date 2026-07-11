# T-018 completion report - Tool Framework & Registry

## Result

Implemented the M5 Tool Framework foundation without adding any real repository
tools.

T-018 defines stable Tool metadata, structured Tool calls/results, a Tool
Protocol, explicit Tool Registry, one-call Tool Executor, structured errors, and
sensitive-information sanitization.

## Tool Framework architecture

```text
Future Worker
  -> ToolCall
  -> ToolExecutor
  -> ToolRegistry
  -> Tool Protocol
  -> Fake Tool in tests
```

## Responsibilities

- `Tool`: performs one operation and returns a `ToolResult`.
- `ToolRegistry`: explicitly registers tools, retrieves by name, and lists
  deterministic metadata.
- `ToolExecutor`: executes exactly one explicit `ToolCall` through the registry
  and converts failures into structured `ToolResult` values.
- Permission decisions remain deferred to T-020.
- Worker integration remains deferred to T-021.

## ToolCall and ToolResult contracts

`ToolCall` carries:

- `call_id`
- `tool_name`
- structured `arguments`
- sanitized `metadata`

`ToolResult` carries:

- `call_id`
- `tool_name`
- `status`
- structured `output`
- sanitized `metadata`
- `error_type`
- sanitized `error_message`
- `requires_review`

Successful results cannot carry error fields. Failed results must include an
explicit error message.

## Sensitive information handling

Tool Framework sanitization covers:

- `api_key`
- `access_token`
- `authorization`
- `password`
- `secret`
- `token`
- bearer tokens
- existing project secret patterns

Sanitization applies to ToolCall metadata/arguments, ToolResult
metadata/output, and error messages.

## Fake Tool tests

Tests define fake tools only inside `tests/test_tool_framework.py`:

- `FakeEchoTool`
- `FakeFailureTool`
- `FakeInvalidResultTool`
- `FakeMismatchTool`

No real repository tools were added to `src/specflow/tools/`.

## Validation

```powershell
uv sync --all-groups
uv run pytest tests/test_tool_framework.py -v
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
git diff --check
git status --short
```

Result:

- `uv run pytest tests/test_tool_framework.py -v`: 29 passed.
- `uv sync --all-groups`: passed.
- `uv run pytest -v`: 283 passed, 1 skipped, 1 warning.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: 83 files already formatted.
- `git diff --check`: passed.

## Warning source

The current full-suite warning is from third-party FastAPI/Starlette test client
compatibility, not new T-018 code. It is recorded in the final validation result
instead of expanding this task into dependency upgrades.

## Explicitly not implemented

- No read-only repository tools.
- No file read/write tools.
- No code search tools.
- No shell, PowerShell, or subprocess tools.
- No network tools.
- No Git tools.
- No database tools.
- No Permission Policy.
- No Worker Tool Integration.
- No Tool Loop.
- No automatic tool selection.
- No T-019 implementation.

## Next task

T-019 Read-only Repository Tools.
