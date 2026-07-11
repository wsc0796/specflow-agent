# T-010 - Trace System

## Goal

Create a trace system that records LLM execution metadata so future agent
behavior can be inspected and reproduced without storing sensitive prompt or
context content.

## In scope

- `src/specflow/trace/` module.
- `LLMTrace` model.
- `TraceRecorder`.
- JSON trace storage.
- Success and failure trace records.
- Integration with T-009 `LLMClient` via a small tracing wrapper.
- Sensitive information protection.
- Unit and integration tests.

## Out of scope

- Database persistence.
- Workflow orchestration.
- Worker orchestration.
- Agent loop.
- Real provider clients.
- Prompt/content logging.
- RAG, embeddings, Redis, LangGraph, MCP, or Java support.

## Trace data

Trace records must include:

- `run_id`
- `prompt_name`
- `prompt_version`
- `prompt_hash`
- `context_hash`
- `model`
- `latency_ms`
- `input_tokens`
- `output_tokens`
- `status`
- `error_type`

## Required API

```python
recorder = TraceRecorder(JsonTraceStorage(traces_root))
response = recorder.complete_with_trace(
    client=client,
    request=request,
    prompt_name="analyze_requirement",
    prompt_version="1.0.0",
    prompt_hash="abc",
    context_hash="xyz",
)
```

## Acceptance criteria

1. A successful mock LLM call writes one JSON trace file.
2. Success trace includes prompt hash, context hash, latency, usage, and
   `status="success"`.
3. A failed mock LLM call writes a JSON trace with `status="failed"` and
   `error_type`.
4. Trace JSON must not include raw API keys, passwords, tokens, prompt content,
   user message content, or context content.
5. Trace writing is deterministic enough for tests: generated filenames must be
   stable when `run_id` is supplied.
6. The implementation does not introduce database persistence, Worker
   orchestration, Agent Loop, Workflow state, real provider clients, RAG,
   embeddings, Redis, LangGraph, MCP, or Java support.

## Validation

Before completion:

```powershell
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```

Write a completion report under `docs/reports/` and create one focused Git
commit. Do not start T-011.
