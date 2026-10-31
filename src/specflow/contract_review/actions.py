"""Parent and one-level child action protocols for the dynamic engine."""

from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from specflow.contract_review.common import ReviewError
from specflow.contract_review.protocol import (
    ActionReason,
    ChildReview,
    Finding,
    MaterialRef,
    Notes,
    ReportPayload,
)
from specflow.contract_review.schemas import StrictModel, Text


class ParentAction(StrictModel):
    schema_version: Literal["contract-review-action.v2.1"]
    reason: ActionReason
    child_result_reviews: Annotated[list[ChildReview], Field(max_length=20)] = Field(
        default_factory=list
    )


class ToolAction(ParentAction):
    action: Literal["tool_call"]
    tool: Literal[
        "list_sources",
        "search_sources",
        "read_source",
        "inspect_python_contract",
        "inspect_json_contract",
    ]
    arguments: dict


class ParentSubmit(ParentAction):
    action: Literal["submit_report"]
    report: ReportPayload


class DelegateAction(ParentAction):
    action: Literal["delegate_task"]
    capability_id: Literal["contract_fact_extract.v1", "docs_examples_alignment.v1"]
    objective: Text
    allowed_material_refs: Annotated[list[MaterialRef], Field(min_length=1, max_length=30)]
    expected_evidence: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=1000)]],
        Field(min_length=1, max_length=20),
    ]
    result_schema: Literal["contract-review-child-result.v1"]


class ChildResult(StrictModel):
    schema_version: Literal["contract-review-child-result.v1"]
    status: Literal["completed", "insufficient", "failed"]
    findings: Annotated[list[Finding], Field(max_length=50)]
    evidence_refs: Annotated[list[MaterialRef], Field(max_length=100)]
    limitations: Notes
    unresolved_gaps: Notes


class ChildTool(StrictModel):
    schema_version: Literal["contract-review-child-action.v1"]
    action: Literal["tool_call"]
    reason: ActionReason
    tool: Literal[
        "list_sources",
        "search_sources",
        "read_source",
        "inspect_python_contract",
        "inspect_json_contract",
    ]
    arguments: dict


class ChildSubmit(StrictModel):
    schema_version: Literal["contract-review-child-action.v1"]
    action: Literal["submit_report"]
    reason: ActionReason
    report: ChildResult


PARENT_ACTION = TypeAdapter(
    Annotated[ToolAction | ParentSubmit | DelegateAction, Field(discriminator="action")]
)
CHILD_ACTION = TypeAdapter(Annotated[ChildTool | ChildSubmit, Field(discriminator="action")])


def parse_action(raw, *, child=False, delegation=False):
    if isinstance(raw, dict):
        if child and raw.get("action") == "delegate_task":
            raise ReviewError("ACTION_NOT_ALLOWED", "子 Agent 不得再次委派。")
        if (
            not child
            and not delegation
            and (raw.get("action") == "delegate_task" or "child_result_reviews" in raw)
        ):
            raise ReviewError("OPTION_NOT_ENABLED", "此输入未启用委派。")
    return (CHILD_ACTION if child else PARENT_ACTION).validate_python(raw)
