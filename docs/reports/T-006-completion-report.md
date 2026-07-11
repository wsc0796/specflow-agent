# T-006 completion report - Prompt Registry

## Result

Implemented a file-based Prompt Registry that treats prompts as versioned,
reviewable engineering assets. The registry loads YAML metadata and Markdown
templates from `prompts/`, validates required metadata, checks template variables,
supports per-version template files through `template_path`, renders with Jinja2
`StrictUndefined`, and returns structured prompt definitions with stable hashes.

## Scope delivered

- Created `docs/tasks/T-006-prompt-registry.md` and froze the task boundary.
- Added Git-managed prompt assets:
  - `prompts/analyze_requirement/v1.0.0.yaml`
  - `prompts/analyze_requirement/template.md`
  - `prompts/generate_spec/v1.0.0.yaml`
  - `prompts/generate_spec/template.md`
- Added `src/specflow/prompts/` modules:
  - `models.py`
  - `loader.py`
  - `renderer.py`
  - `registry.py`
  - `exceptions.py`
- Added `tests/test_prompts.py`.
- Added `jinja2` and `pyyaml` as runtime dependencies.

## Acceptance evidence

| Requirement | Evidence |
| --- | --- |
| Load prompt by name and version | `PromptRegistry().get("analyze_requirement", "1.0.0")` returns `PromptDefinition` |
| Version isolation | Tests load separate metadata/template versions and verify distinct rendered output and hashes |
| Missing prompt/version errors | `PromptNotFoundError` coverage |
| Invalid metadata errors | `PromptMetadataError` coverage |
| Strict variable rendering | Jinja2 `StrictUndefined` via `PromptRenderer` |
| Missing variable fails | `MissingPromptVariableError` coverage |
| Undeclared template variable fails | `TemplateVariableMismatchError` coverage |
| Declared but unused variable fails | `TemplateVariableMismatchError` coverage |
| Stable prompt hash | Hash stability and template-change tests |
| No LLM / Worker / Workflow behavior | No provider SDK, worker module, workflow mutation, database writes, Redis, LangGraph, RAG, or vector store |

## Validation

```powershell
uv run pytest tests/test_prompts.py -v
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```

Result:

- `uv run pytest tests/test_prompts.py -v`: 14 passed.
- `uv run pytest -v`: 92 passed, 1 skipped, 1 warning.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: 19 files already formatted.

## Known limits

- Prompt assets are loaded from local files only.
- The registry does not persist prompt records to the database.
- The registry does not call an LLM or build final LLM request payloads.
- Context assembly remains deferred to T-007.

## Next task

T-007 may implement the Context Builder using deterministic `PROJECT_CONTEXT.md`
data and Prompt Registry definitions. It must still avoid LLM calls and Worker
orchestration.
