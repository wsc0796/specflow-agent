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


class RepositoryToolError(ToolError):
    """Base error for repository-bound Tool failures."""


class RepositoryPathError(RepositoryToolError):
    """Raised when a repository path is missing, unsafe, or escapes its root."""


class SensitiveFileError(RepositoryToolError):
    """Raised when a repository Tool is asked to expose a sensitive file."""


class BinaryFileError(RepositoryToolError):
    """Raised when a repository Tool is asked to return binary content."""


class RepositoryLimitError(RepositoryToolError):
    """Raised when a repository operation exceeds a configured safety limit."""
