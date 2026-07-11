from pathlib import Path

import pytest

from specflow.prompts import (
    MissingPromptVariableError,
    PromptMetadataError,
    PromptNotFoundError,
    PromptRegistry,
    TemplateVariableMismatchError,
)


def _write_prompt(
    root: Path,
    name: str,
    version: str,
    template: str,
    required_variables: list[str],
    description: str = "Test prompt.",
    template_path: str = "template.md",
) -> None:
    prompt_dir = root / name
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_dir.joinpath(f"v{version}.yaml").write_text(
        "\n".join(
            [
                f"name: {name}",
                f"version: {version}",
                f"description: {description}",
                "purpose: test",
                f"template_path: {template_path}",
                "required_variables:",
                *[f"  - {item}" for item in required_variables],
                "output_format:",
                "  type: text",
                "owner: system",
                "created_at: 2026-07-11",
                "",
            ]
        ),
        encoding="utf-8",
    )
    prompt_dir.joinpath(template_path).write_text(template, encoding="utf-8")


def test_loads_repository_prompt_definition() -> None:
    definition = PromptRegistry().get("analyze_requirement", version="1.0.0")

    assert definition.name == "analyze_requirement"
    assert definition.version == "1.0.0"
    assert definition.purpose == "requirement_analysis"
    assert definition.required_variables == ["project_context", "user_requirement"]
    assert definition.output_format == {"type": "json"}
    assert len(definition.prompt_hash) == 64


def test_renders_prompt_with_required_variables() -> None:
    definition = PromptRegistry().get("analyze_requirement", version="1.0.0")

    rendered = definition.render(
        {
            "project_context": "FastAPI project",
            "user_requirement": "Add safe prompt registry",
        }
    )

    assert "FastAPI project" in rendered
    assert "Add safe prompt registry" in rendered


def test_missing_required_variable_fails_before_output() -> None:
    definition = PromptRegistry().get("analyze_requirement", version="1.0.0")

    with pytest.raises(MissingPromptVariableError):
        definition.render({"project_context": "FastAPI project"})


def test_missing_prompt_name_raises_explicit_error(tmp_path: Path) -> None:
    registry = PromptRegistry(tmp_path)

    with pytest.raises(PromptNotFoundError):
        registry.get("missing", version="1.0.0")


def test_missing_prompt_version_raises_explicit_error(tmp_path: Path) -> None:
    _write_prompt(tmp_path, "demo", "1.0.0", "Hello {{ name }}", ["name"])
    registry = PromptRegistry(tmp_path)

    with pytest.raises(PromptNotFoundError):
        registry.get("demo", version="1.1.0")


def test_rejects_path_traversal_prompt_name(tmp_path: Path) -> None:
    registry = PromptRegistry(tmp_path)

    with pytest.raises(PromptNotFoundError):
        registry.get("../demo", version="1.0.0")


def test_version_isolation_returns_distinct_templates_and_hashes(tmp_path: Path) -> None:
    prompt_dir = tmp_path / "demo"
    _write_prompt(
        tmp_path,
        "demo",
        "1.0.0",
        "Hello {{ name }}",
        ["name"],
        "Version one.",
        "v1.0.0.md",
    )
    prompt_dir.joinpath("v1.1.0.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "version: 1.1.0",
                "description: Version two.",
                "purpose: test",
                "template_path: v1.1.0.md",
                "required_variables:",
                "  - name",
                "output_format:",
                "  type: text",
                "owner: system",
                "created_at: 2026-07-11",
                "",
            ]
        ),
        encoding="utf-8",
    )
    prompt_dir.joinpath("v1.1.0.md").write_text("Hi {{ name }}", encoding="utf-8")
    registry = PromptRegistry(tmp_path)

    v100 = registry.get("demo", version="1.0.0")
    v110 = registry.get("demo", version="1.1.0")

    assert v100.description == "Version one."
    assert v110.description == "Version two."
    assert v100.template == "Hello {{ name }}"
    assert v110.template == "Hi {{ name }}"
    assert v100.prompt_hash != v110.prompt_hash


def test_invalid_metadata_missing_required_field_fails(tmp_path: Path) -> None:
    prompt_dir = tmp_path / "demo"
    prompt_dir.mkdir()
    prompt_dir.joinpath("v1.0.0.yaml").write_text(
        "name: demo\nversion: 1.0.0\n",
        encoding="utf-8",
    )
    prompt_dir.joinpath("template.md").write_text("Hello {{ name }}", encoding="utf-8")

    with pytest.raises(PromptMetadataError):
        PromptRegistry(tmp_path).get("demo", version="1.0.0")


def test_template_variable_not_declared_in_metadata_fails(tmp_path: Path) -> None:
    _write_prompt(tmp_path, "demo", "1.0.0", "Hello {{ name }} {{ age }}", ["name"])

    with pytest.raises(TemplateVariableMismatchError):
        PromptRegistry(tmp_path).get("demo", version="1.0.0")


def test_declared_variable_unused_by_template_fails(tmp_path: Path) -> None:
    _write_prompt(tmp_path, "demo", "1.0.0", "Hello {{ name }}", ["name", "age"])

    with pytest.raises(TemplateVariableMismatchError):
        PromptRegistry(tmp_path).get("demo", version="1.0.0")


def test_prompt_hash_is_stable_for_same_metadata_and_template(tmp_path: Path) -> None:
    _write_prompt(tmp_path, "demo", "1.0.0", "Hello {{ name }}", ["name"])
    registry = PromptRegistry(tmp_path)

    first = registry.get("demo", version="1.0.0")
    second = registry.get("demo", version="1.0.0")

    assert first.prompt_hash == second.prompt_hash


def test_prompt_hash_changes_when_template_changes(tmp_path: Path) -> None:
    _write_prompt(tmp_path, "demo", "1.0.0", "Hello {{ name }}", ["name"])
    registry = PromptRegistry(tmp_path)
    first = registry.get("demo", version="1.0.0")

    (tmp_path / "demo" / "template.md").write_text("Goodbye {{ name }}", encoding="utf-8")
    second = registry.get("demo", version="1.0.0")

    assert first.prompt_hash != second.prompt_hash


def test_prompt_hash_changes_when_metadata_changes(tmp_path: Path) -> None:
    _write_prompt(tmp_path, "demo", "1.0.0", "Hello {{ name }}", ["name"], "Before.")
    registry = PromptRegistry(tmp_path)
    first = registry.get("demo", version="1.0.0")

    metadata_path = tmp_path / "demo" / "v1.0.0.yaml"
    metadata_path.write_text(
        metadata_path.read_text(encoding="utf-8").replace("Before.", "After."),
        encoding="utf-8",
    )
    second = registry.get("demo", version="1.0.0")

    assert first.prompt_hash != second.prompt_hash


def test_template_path_escape_is_rejected(tmp_path: Path) -> None:
    prompt_dir = tmp_path / "demo"
    prompt_dir.mkdir()
    prompt_dir.joinpath("v1.0.0.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "version: 1.0.0",
                "description: Bad template path.",
                "purpose: test",
                "template_path: ../outside.md",
                "required_variables:",
                "  - name",
                "output_format:",
                "  type: text",
                "owner: system",
                "created_at: 2026-07-11",
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(PromptMetadataError):
        PromptRegistry(tmp_path).get("demo", version="1.0.0")
