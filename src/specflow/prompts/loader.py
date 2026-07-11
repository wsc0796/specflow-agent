"""File-based prompt loading and validation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, meta

from specflow.prompts.exceptions import (
    PromptMetadataError,
    PromptNotFoundError,
    TemplateVariableMismatchError,
)
from specflow.prompts.models import PromptDefinition

_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_SAFE_VERSION_RE = re.compile(r"^v?[0-9]+(?:\.[0-9]+){2}$")
_REQUIRED_FIELDS = {
    "name",
    "version",
    "description",
    "purpose",
    "required_variables",
    "output_format",
    "owner",
    "created_at",
}


class PromptLoader:
    """Load a single prompt definition from the root prompt directory."""

    def __init__(self, prompts_root: Path) -> None:
        self._root = prompts_root.resolve()
        self._environment = Environment(autoescape=False)

    def load(self, name: str, version: str) -> PromptDefinition:
        self._validate_lookup(name, version)

        prompt_dir = (self._root / name).resolve()
        try:
            prompt_dir.relative_to(self._root)
        except ValueError:
            raise PromptNotFoundError(f"Prompt path escapes root: {name!r}")
        if not prompt_dir.is_dir():
            raise PromptNotFoundError(f"Prompt not found: {name}")

        metadata_path = prompt_dir / f"v{version.removeprefix('v')}.yaml"
        if not metadata_path.is_file():
            raise PromptNotFoundError(f"Prompt version not found: {name}@{version}")

        metadata = self._load_metadata(metadata_path)
        self._validate_metadata(metadata, expected_name=name, expected_version=version)
        template_path = self._template_path(prompt_dir, metadata)
        if not template_path.is_file():
            raise PromptMetadataError(f"Prompt template missing: {template_path.name}")

        template = template_path.read_text(encoding="utf-8")
        self._validate_template_variables(metadata, template)

        return PromptDefinition(
            name=str(metadata["name"]),
            version=str(metadata["version"]),
            description=str(metadata["description"]),
            purpose=str(metadata["purpose"]),
            required_variables=list(metadata["required_variables"]),
            output_format=dict(metadata["output_format"]),
            owner=str(metadata["owner"]),
            created_at=str(metadata["created_at"]),
            template=template,
            metadata=metadata,
        )

    @staticmethod
    def _validate_lookup(name: str, version: str) -> None:
        if not _SAFE_NAME_RE.fullmatch(name):
            raise PromptNotFoundError(f"Invalid prompt name: {name!r}")
        if not _SAFE_VERSION_RE.fullmatch(version):
            raise PromptNotFoundError(f"Invalid prompt version: {version!r}")

    @staticmethod
    def _load_metadata(path: Path) -> dict[str, Any]:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise PromptMetadataError(f"Prompt metadata YAML is invalid: {path.name}") from exc
        if not isinstance(raw, dict):
            raise PromptMetadataError(f"Prompt metadata must be a mapping: {path.name}")
        return raw

    @staticmethod
    def _validate_metadata(
        metadata: dict[str, Any],
        expected_name: str,
        expected_version: str,
    ) -> None:
        missing = sorted(_REQUIRED_FIELDS - set(metadata))
        if missing:
            raise PromptMetadataError(f"Prompt metadata missing fields: {', '.join(missing)}")

        if str(metadata["name"]) != expected_name:
            raise PromptMetadataError("Prompt metadata name does not match directory")
        if str(metadata["version"]).removeprefix("v") != expected_version.removeprefix("v"):
            raise PromptMetadataError("Prompt metadata version does not match requested version")

        required_variables = metadata["required_variables"]
        if not isinstance(required_variables, list) or not required_variables:
            raise PromptMetadataError("required_variables must be a non-empty list")
        if any(not isinstance(item, str) or not item.strip() for item in required_variables):
            raise PromptMetadataError("required_variables must contain non-empty strings")
        if len(required_variables) != len(set(required_variables)):
            raise PromptMetadataError("required_variables must not contain duplicates")

        if not isinstance(metadata["output_format"], dict):
            raise PromptMetadataError("output_format must be a mapping")
        for field in ["description", "purpose", "owner", "created_at"]:
            if not str(metadata[field]).strip():
                raise PromptMetadataError(f"{field} must not be empty")

    def _template_path(self, prompt_dir: Path, metadata: dict[str, Any]) -> Path:
        template_name = str(metadata.get("template_path", "template.md"))
        if not template_name.strip() or Path(template_name).is_absolute():
            raise PromptMetadataError("template_path must be a relative Markdown file")
        template_path = (prompt_dir / template_name).resolve()
        try:
            template_path.relative_to(prompt_dir)
        except ValueError:
            raise PromptMetadataError("template_path must stay inside the prompt directory")
        if template_path.suffix != ".md":
            raise PromptMetadataError("template_path must point to a Markdown file")
        return template_path

    def _validate_template_variables(self, metadata: dict[str, Any], template: str) -> None:
        parsed = self._environment.parse(template)
        template_variables = meta.find_undeclared_variables(parsed)
        required_variables = set(metadata["required_variables"])

        undeclared = sorted(template_variables - required_variables)
        unused = sorted(required_variables - template_variables)
        if undeclared or unused:
            parts: list[str] = []
            if undeclared:
                parts.append(f"template variables not declared: {', '.join(undeclared)}")
            if unused:
                parts.append(f"declared variables unused by template: {', '.join(unused)}")
            raise TemplateVariableMismatchError("; ".join(parts))
