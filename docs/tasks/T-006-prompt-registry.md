# T-006 - Prompt Registry

## Goal

Create a Prompt Registry layer that treats prompts as versioned, reviewable
engineering assets. The registry loads prompt metadata and templates from the
repository, validates template variables, renders prompts with strict variable
handling, and returns structured prompt definitions.

## In scope

- Root-level `prompts/` assets managed by Git.
- Versioned prompt metadata files named like `v1.0.0.yaml`.
- Markdown template files referenced by version metadata. If `template_path` is
  omitted, the loader uses `template.md`.
- Prompt metadata validation.
- Prompt version isolation.
- Prompt loading by name and version.
- Strict Jinja2 rendering.
- Required-variable validation before rendering.
- Template variable mismatch detection.
- Stable prompt hash generation from metadata and template content.
- Unit tests for success and failure paths.

## Out of scope

- LLM calls.
- OpenAI SDK or provider-specific clients.
- Context Builder.
- Worker orchestration.
- Workflow-state changes.
- Prompt auto-optimization.
- Database persistence.
- Redis, LangGraph, vector stores, RAG, MCP, or multi-agent orchestration.

## Prompt asset layout

```text
prompts/
  analyze_requirement/
    v1.0.0.yaml
    template.md
  generate_spec/
    v1.0.0.yaml
    template.md
```

## Metadata schema

```yaml
name: analyze_requirement
version: 1.0.0
description: Analyze user requirement and extract engineering constraints.
purpose: requirement_analysis
template_path: template.md
required_variables:
  - project_context
  - user_requirement
output_format:
  type: json
owner: system
created_at: 2026-07-11
```

## Required API

```python
registry = PromptRegistry(prompts_root)
definition = registry.get("analyze_requirement", version="1.0.0")
rendered = definition.render(
    {
        "project_context": "...",
        "user_requirement": "...",
    }
)
```

`registry.get()` must return a structured `PromptDefinition` containing:

- `name`
- `version`
- `description`
- `purpose`
- `template`
- `metadata`
- `required_variables`
- `output_format`
- `owner`
- `created_at`
- `prompt_hash`

## Acceptance criteria

1. Loading `analyze_requirement` version `1.0.0` returns a `PromptDefinition`.
2. Two versions of the same prompt are isolated and return their own metadata,
   template content, and hash. Version metadata may point at different Markdown
   templates through `template_path`.
3. Missing prompt names or versions raise explicit prompt registry errors.
4. Invalid or incomplete metadata raises explicit validation errors.
5. Rendering uses Jinja2 `StrictUndefined`.
6. Missing required variables fail before producing output.
7. Variables present in a template but absent from metadata are detected during
   prompt loading.
8. Variables declared in metadata but unused by a template are detected during
   prompt loading.
9. `prompt_hash` is stable for unchanged metadata and template content and
   changes when either changes.
10. The implementation does not call an LLM, modify workflow state, or perform
    database writes.

## Validation

Before completion:

```powershell
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```

Write a completion report under `docs/reports/` and create one focused Git
commit.
