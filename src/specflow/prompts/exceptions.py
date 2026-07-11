"""Prompt Registry exceptions."""


class PromptRegistryError(Exception):
    """Base error for Prompt Registry failures."""


class PromptNotFoundError(PromptRegistryError):
    """Raised when a prompt name or version cannot be found."""


class PromptMetadataError(PromptRegistryError):
    """Raised when prompt metadata is missing or invalid."""


class TemplateVariableMismatchError(PromptRegistryError):
    """Raised when metadata variables and template variables differ."""


class MissingPromptVariableError(PromptRegistryError):
    """Raised when rendering input lacks required variables."""


class PromptRenderError(PromptRegistryError):
    """Raised when Jinja rendering fails."""
