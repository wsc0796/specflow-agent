"""Build deterministic prompt-ready context payloads."""

from __future__ import annotations

import re
from collections.abc import Mapping

from specflow.context import ProjectContext, _redact_secrets, _strip_control
from specflow.context_builder.exceptions import ContextBuildError
from specflow.context_builder.models import BuiltContext, ContextSource
from specflow.context_builder.serializer import ProjectContextSerializer
from specflow.prompts.models import PromptDefinition

_SYSTEM_MESSAGE = (
    "You are SpecFlow Agent, a local spec-driven engineering assistant. "
    "Use only the provided project context, prompt instructions, and user requirement. "
    "Do not claim to inspect files, call tools, or execute code."
)

_RAW_SECRET_PATTERNS = [
    re.compile(r"https?://[^/\s:@]+:[^/\s:@]+@"),
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}"),
    re.compile(r"eyJ[a-zA-Z0-9_-]{12,}\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]*"),
    re.compile(r"(?:token|api_key|secret|password)[=:]\s*(?!<redacted>)\S+", re.IGNORECASE),
]


class ContextBuilder:
    """Assemble ProjectContext and PromptDefinition into a BuiltContext."""

    def __init__(self, serializer: ProjectContextSerializer | None = None) -> None:
        self._serializer = serializer or ProjectContextSerializer()

    def build(
        self,
        prompt_definition: PromptDefinition,
        project_context: ProjectContext,
        user_requirement: str,
        variables: Mapping[str, object] | None = None,
    ) -> BuiltContext:
        self._validate_project_context(project_context)
        safe_requirement = self._validate_text("user_requirement", user_requirement)

        project_context_text = self._serializer.serialize(project_context)
        render_variables = self._render_variables(
            project_context_text=project_context_text,
            user_requirement=safe_requirement,
            variables=variables or {},
        )
        user_message = prompt_definition.render(render_variables)

        sources = self._sources(prompt_definition, project_context)
        built = BuiltContext(
            system_message=_SYSTEM_MESSAGE,
            user_message=user_message,
            sources=sources,
            estimated_tokens=self._estimate_tokens(_SYSTEM_MESSAGE, user_message),
            prompt_name=prompt_definition.name,
            prompt_version=prompt_definition.version,
            prompt_hash=prompt_definition.prompt_hash,
            project_context_hash=project_context.content_hash(),
        )
        self._assert_no_raw_secrets(built)
        return built

    @staticmethod
    def _validate_project_context(project_context: ProjectContext) -> None:
        if not project_context.project_name.strip():
            raise ContextBuildError("ProjectContext.project_name must not be empty")
        if project_context.language == "unknown":
            raise ContextBuildError("ProjectContext must contain a supported language")
        if project_context.total_files <= 0:
            raise ContextBuildError("ProjectContext must contain detected project facts")

    @staticmethod
    def _validate_text(field_name: str, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ContextBuildError(f"{field_name} must not be empty")
        return _strip_control(_redact_secrets(clean))

    @staticmethod
    def _render_variables(
        project_context_text: str,
        user_requirement: str,
        variables: Mapping[str, object],
    ) -> dict[str, object]:
        render_variables: dict[str, object] = {
            "project_context": project_context_text,
            "user_requirement": user_requirement,
        }
        for key in sorted(variables):
            if key in render_variables:
                raise ContextBuildError(f"Reserved prompt variable cannot be overridden: {key}")
            render_variables[key] = variables[key]
        return render_variables

    @staticmethod
    def _sources(
        prompt_definition: PromptDefinition,
        project_context: ProjectContext,
    ) -> list[ContextSource]:
        return [
            ContextSource(
                kind="project_context",
                identifier="PROJECT_CONTEXT.md",
                hash=project_context.content_hash(),
            ),
            ContextSource(
                kind="prompt",
                identifier=f"{prompt_definition.name}@{prompt_definition.version}",
                hash=prompt_definition.prompt_hash,
            ),
        ]

    @staticmethod
    def _estimate_tokens(*messages: str) -> int:
        total_chars = sum(len(message) for message in messages)
        return max(1, (total_chars + 3) // 4)

    @staticmethod
    def _assert_no_raw_secrets(built: BuiltContext) -> None:
        combined = "\n".join(
            [
                built.system_message,
                built.user_message,
                *[
                    f"{source.kind}:{source.identifier}:{source.hash or ''}"
                    for source in built.sources
                ],
            ]
        )
        for pattern in _RAW_SECRET_PATTERNS:
            if pattern.search(combined):
                raise ContextBuildError("BuiltContext contains raw secret-like content")
