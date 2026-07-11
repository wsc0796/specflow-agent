"""Evidence collection exceptions."""


class EvidenceError(Exception):
    """Base error for evidence collection failures."""


class EvidenceCollectionError(EvidenceError):
    """Raised when evidence collection cannot complete."""


class EvidenceLimitError(EvidenceError):
    """Raised when an evidence operation exceeds a configured limit."""
