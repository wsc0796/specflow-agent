# M3 Runtime Foundation

Date: 2026-07-11

## Goal

Record the Agent Runtime Foundation checkpoint after T-009 and T-010. This is
not the final M3 closure because T-011 Fallback remains deferred.

## Completed capabilities

- Prompt Registry (T-006): file-based, versioned prompt assets with strict
  Jinja2 rendering and stable prompt hashes.
- Context Builder (T-007): deterministic `BuiltContext` assembly from sanitized
  project context, prompt definitions, and user requirements.
- Token Budget Manager (T-008): deterministic budget policy, token estimation,
  priority-based trimming, removed-section tracking, and stable budget hash.
- LLM Client (T-009): provider-neutral request/response models, client protocol,
  deterministic mock client, and explicit error contract.
- Trace System (T-010): metadata-only JSON traces for successful and failed mock
  LLM calls, including prompt/context hashes, usage, latency, status, and error
  type.

## Demo flow

```text
Prompt Registry
  -> Context Builder
  -> Token Budget Manager
  -> Mock LLM Client
  -> Trace Recorder
  -> Response
```

Example input:

```text
Analyze this FastAPI project.
```

The runtime foundation can now execute the mock flow without network access,
provider credentials, Worker orchestration, Agent Loop, Workflow state changes,
RAG, embeddings, Redis, LangGraph, MCP, or vector stores.

## Included commits

- `ce5f042` - T-006 Prompt Registry
- `bb07514` - T-007 Context Builder
- `5e9be6d` - T-008 Token Budget Manager
- `7205aac` - T-009 LLM Client
- `8186322` - T-010 Trace System

## Validation

- `uv run pytest -v`: 127 passed, 1 skipped, 1 warning.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: 43 files already formatted.

## Known limits

- Only `MockLLMClient` exists; real provider clients are not implemented.
- Trace storage is local JSON only; no database persistence exists.
- No fallback handling exists yet.
- No Worker, Agent Loop, or Workflow orchestration exists yet.

## Next gate

T-011 Fallback may begin after this checkpoint. M3 should only be treated as
fully complete after fallback behavior and its quality gate are implemented.
