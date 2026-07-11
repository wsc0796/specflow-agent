# T-020 - OpenAI-compatible LLM Provider

## Goal

Add one configurable, synchronous OpenAI-compatible HTTP provider on top of the
existing T-009 `LLMClient`, `LLMRequest`, `LLMResponse`, usage, and exception
contracts. Keep `MockLLMClient` unchanged and available.

This task maps to the attachment's T-019 Provider slice because the repository
had already assigned T-019 to Safe Read-only Repository Tools.

## Building

- `OpenAICompatibleConfig` from explicit values or environment variables.
- `OpenAICompatibleLLMClient` implementing the existing `LLMClient` Protocol.
- Configurable base URL, API key, model, and timeout.
- One bounded synchronous `POST` to `<base-url>/chat/completions` per call.
- Normalized content, model, token usage, finish reason, and latency.
- Safe mapping of timeouts, network errors, HTTP errors, and malformed responses.
- Runtime `httpx` dependency and an environment-variable example.
- Mock-transport tests with no public network access.

## Configuration

- `SPECFLOW_LLM_BASE_URL`
- `SPECFLOW_LLM_API_KEY`
- `SPECFLOW_LLM_MODEL`
- `SPECFLOW_LLM_TIMEOUT_SECONDS`

The configured model is the Provider's source of truth for the outbound request.
Application composition must construct Workers with the same model in a later
integration task.

## Security and error contract

1. API keys never appear in `repr`, exceptions, traces, artifacts, or logs.
2. The Provider never logs or stores request message bodies.
3. Server response/error bodies are not copied into public errors.
4. Base URLs must use HTTP(S), include a host, contain no credentials, and have
   no query or fragment.
5. Missing or invalid configuration raises `LLMConfigurationError`.
6. Timeouts raise `LLMTimeoutError`.
7. Network, status, JSON, and schema failures raise sanitized `LLMResponseError`.
8. The Provider performs one HTTP attempt only and does not call fallback.

## Not building

- Provider SDKs, streaming, tool calling, retries, fallback, multi-provider
  routing, Workflow/Worker orchestration, repository evidence integration, CLI,
  artifacts, or T-021 and later work.
- A committed `.env` or any real credential.
- An automatic live test in pytest or CI.

## Validation

```powershell
uv sync --all-groups
uv run pytest tests/test_openai_compatible_provider.py -v
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
git diff --check
```

Write `docs/reports/T-020-completion-report.md`, create one focused commit, and
push it before starting T-021.
