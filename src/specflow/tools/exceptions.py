"""Tool Framework exceptions."""


class ToolError(Exception):
    """Base error for Tool Framework failures."""


class ToolValidationError(ToolError):
    """Raised when a tool model is invalid."""


class ToolRegistrationError(ToolError):
    """Raised when a tool cannot be registered."""


class DuplicateToolError(ToolRegistrationError):
    """Raised when a tool name is already registered."""


class ToolNotFoundError(ToolError):
    """Raised when a tool cannot be found."""


class ToolExecutionError(ToolError):
    """Raised when tool execution contract is violated."""
