"""Artifact store exceptions."""


class ArtifactError(Exception):
    """Base error for artifact store failures."""


class ArtifactWriteError(ArtifactError):
    """Raised when an artifact cannot be written."""


class ArtifactExistsError(ArtifactError):
    """Raised when an artifact directory already exists."""
