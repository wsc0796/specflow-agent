"""Strict arguments for the five registered snapshot-only tools."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from specflow.contract_review.protocol import SourceRef
from specflow.contract_review.schemas import ID, JsonSelector, Role, StrictModel


class ToolResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    result_kind: Literal["data", "empty", "dependency_error", "unsupported"]
    body: dict[str, JsonValue]
    source_refs: Annotated[list[SourceRef], Field(max_length=1000)]
    completeness: Literal["complete", "truncated"]
    truncation: dict | None
    error: dict | None


class ListSources(StrictModel):
    roles: Annotated[list[Role], Field(min_length=1, max_length=6)] | None = None
    path_prefix: Annotated[str, Field(max_length=1024)] = ""
    limit: Annotated[int, Field(ge=1, le=50)] = 20
    cursor: Annotated[str, Field(min_length=1, max_length=512)] | None = None


class SearchSources(StrictModel):
    query: Annotated[str, Field(min_length=1, max_length=256)]
    source_ids: Annotated[list[ID], Field(min_length=1, max_length=100)]
    case_sensitive: bool = True
    max_matches: Annotated[int, Field(ge=1, le=50)] = 20

    @model_validator(mode="after")
    def unique_sources(self):
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError("Duplicate source ID")
        return self


class ReadSource(StrictModel):
    source_id: ID
    start_line: Annotated[int, Field(ge=1)]
    end_line: Annotated[int, Field(ge=1)]

    @model_validator(mode="after")
    def bounded_range(self):
        if not self.start_line <= self.end_line < self.start_line + 200:
            raise ValueError("Read range must contain 1 to 200 lines")
        return self


class InspectPython(StrictModel):
    source_id: ID
    selectors: Annotated[
        list[Literal["routes", "response_fields", "state_guards", "assignments", "call_refs"]],
        Field(min_length=1, max_length=5),
    ]

    @model_validator(mode="after")
    def unique_selectors(self):
        if len(set(self.selectors)) != len(self.selectors):
            raise ValueError("Duplicate inspection selector")
        return self


class InspectJson(StrictModel):
    source_id: ID
    pointer: Annotated[str, Field(max_length=1024)] = ""
    local_ref_source_ids: Annotated[list[ID], Field(max_length=20)] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_pointer(self):
        JsonSelector(kind="json_pointer", pointer=self.pointer)
        if len(set(self.local_ref_source_ids)) != len(self.local_ref_source_ids):
            raise ValueError("Duplicate local reference source")
        return self


TOOL_ARGUMENTS = {
    "list_sources": ListSources,
    "search_sources": SearchSources,
    "read_source": ReadSource,
    "inspect_python_contract": InspectPython,
    "inspect_json_contract": InspectJson,
}

CAPABILITIES = {
    "contract_fact_extract.v1": (
        "list_sources",
        "search_sources",
        "read_source",
        "inspect_json_contract",
    ),
    "docs_examples_alignment.v1": (
        "list_sources",
        "search_sources",
        "read_source",
        "inspect_python_contract",
    ),
}
CAPABILITY_PURPOSES = {
    "contract_fact_extract.v1": "只提取允许材料中的规范条款、适用范围和缺口，不认证批准者。",
    "docs_examples_alignment.v1": "只对照已选规则检查允许的文档或示例片段，返回候选发现与证据。",
}


def contains_selector(grant, requested, line_count):
    if grant["kind"] == "full":
        return True
    if requested["kind"] == "full":
        return (
            grant["kind"] == "lines"
            and grant["start_line"] == 1
            and grant["end_line"] >= line_count
        )
    if grant["kind"] == requested["kind"] == "lines":
        return (
            grant["start_line"]
            <= requested["start_line"]
            <= requested["end_line"]
            <= grant["end_line"]
        )
    if grant["kind"] == requested["kind"] == "json_pointer":
        prefix, pointer = grant["pointer"], requested["pointer"]
        return prefix == "" or pointer == prefix or pointer.startswith(prefix + "/")
    return False


def covers_selector(grants, requested, line_count):
    if not grants:
        return False
    if any(contains_selector(grant, requested, line_count) for grant in grants):
        return True
    if requested["kind"] not in ("full", "lines"):
        return False
    start, end = (
        (1, line_count)
        if requested["kind"] == "full"
        else (requested["start_line"], requested["end_line"])
    )
    next_line = start
    for lower, upper in sorted(
        (grant["start_line"], grant["end_line"]) for grant in grants if grant["kind"] == "lines"
    ):
        if lower <= next_line <= upper:
            next_line = upper + 1
    return next_line > end
