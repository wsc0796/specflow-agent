# T-009 - LLM Client

## Goal

Create a provider-neutral LLM client abstraction that can accept a structured
request and return a structured response without depending on network access,
API keys, provider SDKs, or model behavior.

## In scope

- `src/specflow/llm/` module.
- `LLMRequest` model.
- `LLMMessage` model.
- `LLMResponse` model.
- `LLMUsage` model.
- `LLMClient` protocol.
- Deterministic `MockLLMClient`.
- Explicit LLM exception hierarchy.
- Request validation.
- Response structure stability.
- Unit tests for success and failure paths.

## Out of scope

- OpenAI SDK.
- DeepSeek SDK.
- Claude/Gemini/provider SDKs.
- API key management.
- Network calls.
- Streaming.
- Tool calling.
- Worker orchestration.
- Agent loop.
- Workflow-state changes.
- Trace recording. Trace belongs to T-010.

## Required API

```python
client = MockLLMClient(response_content="mock response")
response = client.complete(
    LLMRequest(
        model="mock-model",
        messages=[LLMMessage(role="user", content="hello")],
        temperature=0.0,
        max_tokens=128,
    )
)
```

## Data contract

`LLMRequest` must contain:

- `model`
- `messages`
- `temperature`
- `max_tokens`
- `response_format`

`LLMResponse` must contain:

- `content`
- `model`
- `usage`
- `latency_ms`
- `finish_reason`

## Error contract

Define:

- `LLMError`
- `LLMTimeoutError`
- `LLMResponseError`

Mock failures must convert into explicit LLM errors rather than leaking arbitrary
exceptions to callers.

## Acceptance criteria

1. Normal mock request with `hello` returns `mock response`.
2. Invalid request, such as `model=""`, fails explicitly.
3. Response structure is stable and includes usage, latency, model, and finish
   reason.
4. Mock failures are converted into `LLMResponseError`.
5. Implementation does not import provider SDKs, perform network calls, manage
   API keys, stream tokens, call tools, introduce workers, or mutate workflow
   state.

## Validation

Before completion:

```powershell
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```

Write a completion report under `docs/reports/` and create one focused Git
commit. Do not start T-010 until T-009 is committed.
