from __future__ import annotations

from pydantic import BaseModel

from specflow.schema.exceptions import (
    RegistryFrozenError,
    SchemaConflictError,
    SchemaNotFoundError,
)


class SchemaRegistry:
    """Stable, versioned schema registry. Pydantic models are the truth source."""

    def __init__(self) -> None:
        self._models: dict[str, type[BaseModel]] = {}
        self._frozen = False

    def register(self, schema_id: str, model: type[BaseModel]) -> None:
        if self._frozen:
            raise RegistryFrozenError("Cannot register after freeze()")
        if not isinstance(model, type) or not issubclass(model, BaseModel):
            raise ValueError(
                f"Schema model must be a BaseModel subclass, got {type(model)}"
            )
        if not schema_id.strip():
            raise ValueError("schema_id must not be empty")
        existing = self._models.get(schema_id)
        if existing is not None:
            if existing is model:
                return  # idempotent
            raise SchemaConflictError(
                f"Schema ID '{schema_id}' already registered with a different model"
            )
        self._models[schema_id] = model

    def get(self, schema_id: str) -> type[BaseModel]:
        try:
            return self._models[schema_id]
        except KeyError:
            raise SchemaNotFoundError(f"Schema ID not found: {schema_id}")

    def export_json_schema(self, schema_id: str) -> dict[str, object]:
        model = self.get(schema_id)
        return model.model_json_schema()

    def list_schemas(self) -> tuple[str, ...]:
        return tuple(sorted(self._models.keys()))

    def freeze(self) -> None:
        self._frozen = True

    @property
    def frozen(self) -> bool:
        return self._frozen
