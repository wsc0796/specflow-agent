class SchemaError(Exception):
    """Base exception for schema-related errors."""


class SchemaConflictError(SchemaError):
    """Same schema_id registered with a different model."""


class SchemaNotFoundError(SchemaError):
    """Schema ID not found in registry."""


class RegistryFrozenError(SchemaError):
    """Attempted to register after freeze()."""
