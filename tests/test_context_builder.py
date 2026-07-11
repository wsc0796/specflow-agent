import pytest

from specflow.context import ProjectContext
from specflow.context_builder import BuiltContext, ContextBuilder, ContextBuildError
from specflow.prompts import MissingPromptVariableError
from specflow.prompts.models import PromptDefinition
from specflow.technology import Evidence


def _project_context(**overrides) -> ProjectContext:
    values = {
        "project_name": "demo-api",
        "root_path": "D:/private/demo-api",
        "language": "python",
        "frameworks": ["fastapi"],
        "validation_library": "pydantic",
        "orm": "sqlalchemy",
        "database": "sqlite",
        "test_framework": "pytest",
        "lint_tools": ["ruff"],
        "dependency_files": ["pyproject.toml"],
        "entry_candidates": ["src/main.py"],
        "top_level_directories": ["src", "tests"],
        "total_files": 12,
        "ignored_directories": [".git", ".venv"],
        "oversized_files": [],
        "parse_warnings": [],
        "technology_evidence": [Evidence(file="pyproject.toml", matched="fastapi")],
        "generated_at": "2026-07-11T12:00:00+00:00",
    }
    values.update(overrides)
    return ProjectContext(**values)


def _prompt(required_variables: list[str] | None = None, template: str | None = None):
    required = required_variables or ["project_context", "user_requirement"]
    return PromptDefinition(
        name="analyze_requirement",
        version="1.0.0",
        description="Analyze requirement.",
        purpose="requirement_analysis",
        required_variables=required,
        output_format={"type": "json"},
        owner="system",
        created_at="2026-07-11",
        template=template
        or "Project:\n{{ project_context }}\n\nRequirement:\n{{ user_requirement }}",
        metadata={
            "name": "analyze_requirement",
            "version": "1.0.0",
            "description": "Analyze requirement.",
            "purpose": "requirement_analysis",
            "required_variables": required,
            "output_format": {"type": "json"},
            "owner": "system",
            "created_at": "2026-07-11",
        },
    )


def test_builds_context_from_project_context_prompt_and_requirement() -> None:
    built = ContextBuilder().build(
        prompt_definition=_prompt(),
        project_context=_project_context(),
        user_requirement="Add a safe endpoint",
    )

    assert isinstance(built, BuiltContext)
    assert "SpecFlow Agent" in built.system_message
    assert "demo-api" in built.user_message
    assert "Add a safe endpoint" in built.user_message
    assert built.prompt_name == "analyze_requirement"
    assert built.prompt_version == "1.0.0"
    assert len(built.context_hash) == 64
    assert built.estimated_tokens > 0


def test_prompt_variables_are_rendered() -> None:
    prompt = _prompt(template="{{ project_context }}\nTASK={{ user_requirement }}")

    built = ContextBuilder().build(
        prompt_definition=prompt,
        project_context=_project_context(),
        user_requirement="Generate task spec",
    )

    assert "language: python" in built.user_message
    assert "TASK=Generate task spec" in built.user_message


def test_missing_prompt_variable_fails_through_prompt_rendering() -> None:
    prompt = _prompt(
        required_variables=["project_context", "user_requirement", "runtime_metadata"],
        template="{{ project_context }} {{ user_requirement }} {{ runtime_metadata }}",
    )

    with pytest.raises(MissingPromptVariableError):
        ContextBuilder().build(
            prompt_definition=prompt,
            project_context=_project_context(),
            user_requirement="Need runtime metadata",
        )


def test_same_input_produces_same_hash() -> None:
    builder = ContextBuilder()
    prompt = _prompt()
    ctx = _project_context()

    first = builder.build(prompt, ctx, "Add Context Builder")
    second = builder.build(prompt, ctx, "Add Context Builder")

    assert first.context_hash == second.context_hash
    assert first.user_message == second.user_message


def test_variable_insertion_order_does_not_change_output_or_hash() -> None:
    prompt = _prompt(
        required_variables=["project_context", "user_requirement", "alpha", "beta"],
        template=(
            "{{ project_context }}\n{{ user_requirement }}\nalpha={{ alpha }}\nbeta={{ beta }}"
        ),
    )
    builder = ContextBuilder()
    ctx = _project_context()

    first = builder.build(prompt, ctx, "Order check", {"beta": "B", "alpha": "A"})
    second = builder.build(prompt, ctx, "Order check", {"alpha": "A", "beta": "B"})

    assert first.user_message == second.user_message
    assert first.context_hash == second.context_hash


def test_source_tracking_contains_project_context_and_prompt_references() -> None:
    prompt = _prompt()
    ctx = _project_context()

    built = ContextBuilder().build(prompt, ctx, "Trace sources")

    assert [source.kind for source in built.sources] == ["project_context", "prompt"]
    assert built.sources[0].identifier == "PROJECT_CONTEXT.md"
    assert built.sources[0].hash == ctx.content_hash()
    assert built.sources[1].identifier == "analyze_requirement@1.0.0"
    assert built.sources[1].hash == prompt.prompt_hash
    assert built.project_context_hash == ctx.content_hash()
    assert built.prompt_hash == prompt.prompt_hash


def test_raw_secret_values_do_not_enter_built_context() -> None:
    ctx = _project_context(
        technology_evidence=[
            Evidence(
                file="pyproject.toml",
                matched="https://<credentials>@example.com/pkg.whl",
            ),
            Evidence(file="config.py", matched="api_key=<redacted>"),
            Evidence(file="auth.py", matched="<jwt>"),
        ],
    )

    built = ContextBuilder().build(_prompt(), ctx, "Review sanitized context")
    combined = "\n".join(
        [
            built.system_message,
            built.user_message,
            *[f"{source.kind}:{source.identifier}:{source.hash or ''}" for source in built.sources],
        ]
    )

    assert "user:pass" not in combined
    assert "sk-secret" not in combined
    assert "eyJhbGci" not in combined


def test_serializer_inherits_t005_redaction_and_control_stripping() -> None:
    ctx = _project_context(
        project_name="demo\napi",
        technology_evidence=[
            Evidence(
                file="config.py",
                matched="https://user:pass@example.com/pkg.whl\ntoken=raw-secret",
            ),
        ],
    )

    built = ContextBuilder().build(_prompt(), ctx, "Review sanitized context")

    assert "demo api" in built.user_message
    assert "user:pass" not in built.user_message
    assert "raw-secret" not in built.user_message
    assert "https://<credentials>@example.com/pkg.whl token=<redacted>" in built.user_message


def test_raw_secret_like_input_is_redacted_before_output() -> None:
    ctx = _project_context(
        technology_evidence=[
            Evidence(file="config.py", matched="api_key=sk-abc123def456ghi789jkl012"),
        ],
    )

    built = ContextBuilder().build(_prompt(), ctx, "Do not leak secrets")

    assert "sk-abc123" not in built.user_message
    assert "api_key=<redacted>" in built.user_message


def test_empty_project_context_fails() -> None:
    ctx = ProjectContext(project_name="empty", root_path="D:/empty")

    with pytest.raises(ContextBuildError):
        ContextBuilder().build(_prompt(), ctx, "Analyze empty project")


def test_unsupported_non_empty_project_context_fails() -> None:
    ctx = _project_context(language="unknown", total_files=12)

    with pytest.raises(ContextBuildError):
        ContextBuilder().build(_prompt(), ctx, "Analyze unsupported project")


def test_blank_user_requirement_fails() -> None:
    with pytest.raises(ContextBuildError):
        ContextBuilder().build(_prompt(), _project_context(), "   ")


def test_reserved_prompt_variables_cannot_be_overridden() -> None:
    with pytest.raises(ContextBuildError):
        ContextBuilder().build(
            _prompt(),
            _project_context(),
            "Override attempt",
            variables={"project_context": "fake"},
        )
