"""Jinja2 prompt rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING

from jinja2 import Environment, StrictUndefined, TemplateError

from specflow.prompts.exceptions import MissingPromptVariableError, PromptRenderError

if TYPE_CHECKING:
    from specflow.prompts.models import PromptDefinition


class PromptRenderer:
    """Render prompt definitions using StrictUndefined."""

    def __init__(self) -> None:
        self._environment = Environment(
            autoescape=False,
            keep_trailing_newline=True,
            undefined=StrictUndefined,
        )

    def render(self, definition: PromptDefinition, variables: dict[str, object]) -> str:
        missing = sorted(set(definition.required_variables) - set(variables))
        if missing:
            raise MissingPromptVariableError(
                f"Missing required variables for {definition.name}@{definition.version}: "
                f"{', '.join(missing)}"
            )

        try:
            return self._environment.from_string(definition.template).render(**variables)
        except TemplateError as exc:
            raise PromptRenderError(
                f"Could not render {definition.name}@{definition.version}: {exc}"
            ) from exc
