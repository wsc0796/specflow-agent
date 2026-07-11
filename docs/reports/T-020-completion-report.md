# T-020 completion report - OpenAI-compatible LLM Provider

## Result

Implemented a configurable, synchronous OpenAI-compatible Provider on top of
the T-009 provider-neutral LLM contracts. `MockLLMClient` remains available and
unchanged.

## Numbering note

This task maps to the attachment's T-019 Provider slice. The repository already
used T-019 for Safe Read-only Repository Tools, so the Provider is recorded as
T-020 without rewriting published history.

## Architecture

```text
LLMRequest
  -> OpenAICompatibleLLMClient
  -> one HTTP POST /chat/completions
  -> response validation
  -> existing LLMResponse + LLMUsage
```

`OpenAICompatibleConfig` validates base URL, API key, model, and timeout. The
Provider maps one request and performs no retry, fallback, routing, Workflow, or
Worker behavior.

## Configuration and security

- Supports explicit construction and `SPECFLOW_LLM_*` process environment values.
- Requires an HTTP(S) URL with a host and rejects embedded credentials, queries,
  and fragments.
- Hides the API key from config and client representations.
- Does not log or retain request messages.
- Does not copy transport details or provider response bodies into exceptions.
- Maps timeout, network, authentication, rate limit, server, invalid JSON, and
  response-schema failures into the existing LLM exception family.
- Performs exactly one HTTP attempt.
- `.env` and `.env.*` remain ignored while `.env.example` is tracked.

## Tests

`tests/test_openai_compatible_provider.py` adds 26 cases for explicit and
environment configuration, invalid fields, response and usage mapping,
configured model selection, OpenAI request shape, timeout/network/status errors,
invalid JSON and schemas, credential-safe representations and errors, one-attempt
behavior, and continued Mock client support.

All tests use `httpx.MockTransport`; no real network or real API key is used.

## Quality gates

- `uv sync --all-groups`: passed.
- `uv run pytest tests/test_openai_compatible_provider.py -v`: 26 passed.
- `uv run pytest -v`: 345 passed, 2 skipped, 1 warning.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: 90 files already formatted.
- `git diff --check`: passed.

The existing warning is a third-party FastAPI/Starlette `TestClient`
deprecation warning and is unchanged by T-020.

## Live validation

Not executed in T-020. Automated tests prove the Provider contract through an
in-process mock transport only. No claim of a successful real-provider call is
made.

## Known limitations

- Synchronous non-streaming completions only.
- One configured Provider and model; no routing or automatic fallback.
- No retries in the Provider.
- No tool-calling schema.
- No repository evidence, Worker integration, CLI, or artifact delivery.

## Next task

T-021 Repository-aware Agent Integration is the next permitted task. No T-021
code is included here.
