class AgentError(Exception):
    """Base exception for agent-related errors."""


class AgentModelValidationError(AgentError, ValueError):
    """Agent model validation failed."""


class AgentNotFoundError(AgentError):
    """Agent not found in registry."""


class DuplicateAgentError(AgentError):
    """Agent with same identity already registered."""


class AgentExecutionError(AgentError):
    """Agent execution failed."""
