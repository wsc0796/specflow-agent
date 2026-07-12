import pytest
from pydantic import BaseModel

from specflow.schema.exceptions import (
    RegistryFrozenError,
    SchemaConflictError,
    SchemaNotFoundError,
)
from specflow.schema.registry import SchemaRegistry


class SampleInput(BaseModel):
    name: str
    value: int


class SampleOutput(BaseModel):
    result: str


class DifferentModel(BaseModel):
    other: str


class TestSchemaRegistryRegistration:
    def test_register_and_retrieve_model(self):
        reg = SchemaRegistry()
        reg.register("agent/test/v1/input", SampleInput)
        assert reg.get("agent/test/v1/input") is SampleInput

    def test_idempotent_same_model(self):
        reg = SchemaRegistry()
        reg.register("agent/test/v1/input", SampleInput)
        reg.register("agent/test/v1/input", SampleInput)  # no-op

    def test_conflict_different_model_same_id(self):
        reg = SchemaRegistry()
        reg.register("agent/test/v1/input", SampleInput)
        with pytest.raises(SchemaConflictError):
            reg.register("agent/test/v1/input", DifferentModel)

    def test_reject_non_basemodel(self):
        reg = SchemaRegistry()
        with pytest.raises(ValueError):
            reg.register("agent/test/v1/input", dict)  # type: ignore

    def test_get_nonexistent_raises(self):
        reg = SchemaRegistry()
        with pytest.raises(SchemaNotFoundError):
            reg.get("nonexistent/schema/v1")

    def test_freeze_prevents_registration(self):
        reg = SchemaRegistry()
        reg.register("agent/test/v1/input", SampleInput)
        reg.freeze()
        assert reg.frozen is True
        with pytest.raises(RegistryFrozenError):
            reg.register("agent/test/v2/input", SampleInput)

    def test_export_json_schema(self):
        reg = SchemaRegistry()
        reg.register("agent/test/v1/input", SampleInput)
        exported = reg.export_json_schema("agent/test/v1/input")
        assert exported["type"] == "object"
        assert "name" in exported["properties"]

    def test_list_schemas(self):
        reg = SchemaRegistry()
        reg.register("agent/a/v1/input", SampleInput)
        reg.register("agent/b/v1/output", SampleOutput)
        ids = reg.list_schemas()
        assert "agent/a/v1/input" in ids
        assert "agent/b/v1/output" in ids
