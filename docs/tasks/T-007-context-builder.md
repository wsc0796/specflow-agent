# T-007 - Context Builder

## Goal

Create a Context Assembly layer that combines a sanitized `ProjectContext`, a
versioned `PromptDefinition`, a user requirement, and optional runtime variables
into a deterministic `BuiltContext` object for future LLM calls.

## In scope

- `src/specflow/context_builder/` module.
- Structured `BuiltContext` model.
- Deterministic system/user message assembly.
- Prompt rendering through T-006 `PromptDefinition`.
- Source tracking for project context and prompt assets.
- Stable `context_hash`.
- Simple deterministic token estimate.
- Input validation.
- Safety inheritance from T-005 redaction and sanitization.
- Unit tests for success and failure paths.

## Out of scope

- LLM calls.
- OpenAI SDK or provider-specific clients.
- Repository scanning or filesystem traversal.
- Technology detection.
- PROJECT_CONTEXT generation.
- Embeddings, RAG, vector stores, Redis, LangGraph, MCP, or Java support.
- Worker orchestration.
- Runtime workflow-state changes.
- Prompt Registry changes beyond using its public model.
- Token Budget Manager behavior beyond a simple estimate.

## Required API

```python
builder = ContextBuilder()
built = builder.build(
    prompt_definition=prompt,
    project_context=project_context,
    user_requirement="Add a safe endpoint",
)
```

`build()` must return a `BuiltContext` containing:

- `system_message`
- `user_message`
- `sources`
- `context_hash`
- `estimated_tokens`
- `prompt_name`
- `prompt_version`
- `prompt_hash`
- `project_context_hash`

## Assembly rules

1. `system_message` must be stable and must identify the bounded role of
   SpecFlow Agent as a local, spec-driven engineering assistant.
2. `user_message` must be rendered through `PromptDefinition.render()`.
3. Variables passed to the prompt must include:
   - `project_context`
   - `user_requirement`
4. Additional variables may be supplied, but they must be normalized by key order.
5. Source order must be deterministic.
6. `context_hash` must be based on content-significant fields only, not local
   filesystem paths or runtime timestamps.
7. An empty or unsupported `ProjectContext` must fail rather than producing a
   low-value LLM payload.
8. Raw secret patterns must not appear in the built messages.

## Acceptance criteria

1. A normal `ProjectContext` and prompt produce a `BuiltContext`.
2. The prompt receives rendered variables and returns expected user-message text.
3. Missing prompt variables fail through the prompt-rendering path.
4. Equal inputs produce equal `context_hash` values.
5. Variables supplied in different insertion orders produce equal output and hash.
6. Source tracking includes `PROJECT_CONTEXT.md`, prompt name/version/hash, and
   project context hash.
7. Sensitive raw values such as URL credentials, API keys, and JWTs do not appear
   in `system_message`, `user_message`, or `sources`.
8. Empty `ProjectContext` input fails explicitly.
9. The implementation does not call an LLM, scan a repository, modify runtime
   workflow state, or perform database writes.

## Validation

Before completion:

```powershell
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```

Write a completion report under `docs/reports/` and create one focused Git
commit. Do not start T-008.
