"""Evidence collection exceptions."""


class EvidenceError(Exception):
    """Base error for evidence collection failures."""


class EvidenceCollectionError(EvidenceError):
    """Raised when evidence collection cannot complete."""

    def __init__(
        self, message: str, *, tool_name: str | None = None, error_type: str | None = None
    ) -> None:
        super().__init__(message)
        self.audit_context: dict[str, str] = {}
        if tool_name in {"list_files", "search_code", "read_file"}:
            self.audit_context = {
                "tool_name": tool_name,
                "error_type": error_type
                if error_type
                in {
                    "RepositoryLimitError",
                    "RepositoryPathError",
                    "SensitiveFileError",
                    "BinaryFileError",
                    "ToolValidationError",
                    "ToolNotFoundError",
                    "ToolExecutionError",
                    "OSError",
                    "PermissionError",
                    "FileNotFoundError",
                }
                else "ToolExecutionError",
            }


class EvidenceLimitError(EvidenceError):
    """Raised when an evidence operation exceeds a configured limit."""
