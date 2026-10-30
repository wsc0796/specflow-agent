"""Model-owned report and fixed-review payloads, without host resource identities."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from specflow.contract_review.schemas import ID, RepoPath, Role, Selector, StrictModel, Text

LongText = Annotated[str, Field(min_length=1, max_length=4000)]
IDs = Annotated[list[ID], Field(max_length=100)]
NonEmptyIDs = Annotated[list[ID], Field(min_length=1, max_length=100)]
Notes = Annotated[list[Text], Field(max_length=20)]


class SourceRef(StrictModel):
    source_id: ID
    selector: Selector


SourceRefs = Annotated[list[SourceRef], Field(max_length=100)]


class SourceMaterial(StrictModel):
    kind: Literal["source"]
    source_ref: SourceRef


class RuleMaterial(StrictModel):
    kind: Literal["rule"]
    adoption_id: ID


class ObservationMaterial(StrictModel):
    kind: Literal["observation"]
    observation_id: ID


MaterialRef = Annotated[
    SourceMaterial | RuleMaterial | ObservationMaterial, Field(discriminator="kind")
]
Materials = Annotated[list[MaterialRef], Field(max_length=30)]


class Coverage(StrictModel):
    target_id: ID
    status: Literal["covered", "partial", "not_read"]
    source_refs: SourceRefs
    missing_information: Notes


class CheckResult(StrictModel):
    check_id: ID
    status: Literal["checked", "evidence_missing", "unsupported", "not_checked"]
    finding_ids: IDs
    source_refs: SourceRefs
    observation_refs: IDs
    missing_information: Notes


class RuleUse(StrictModel):
    adoption_id: ID
    usage: Literal["support", "conflict", "historical", "excluded"]
    explanation: Text


class RelatedFinding(StrictModel):
    report_revision_id: ID
    finding_id: ID


class Finding(StrictModel):
    id: ID
    target_ids: NonEmptyIDs
    judgment_status: Literal[
        "supported_deviation",
        "no_deviation",
        "legitimate_version_difference",
        "needs_decision",
        "insufficient_evidence",
    ]
    affected_artifacts: Annotated[list[Role], Field(min_length=1, max_length=6)]
    labels: Annotated[
        list[
            Literal[
                "documentation_drift",
                "example_drift",
                "implementation_contract_violation",
                "test_expectation_conflict",
                "rule_conflict",
                "legitimate_version_difference",
            ]
        ],
        Field(max_length=6),
    ]
    claim: LongText
    rule_refs: IDs
    source_refs: SourceRefs
    observation_refs: IDs
    verification_evidence_refs: IDs
    execution_verification: Literal["NOT_RUN"]
    limitations: Notes
    related_findings: Annotated[list[RelatedFinding], Field(max_length=100)] = Field(
        default_factory=list
    )


class QuestionOption(StrictModel):
    id: ID
    label: Annotated[str, Field(min_length=1, max_length=128)]
    consequence: Text


class Question(StrictModel):
    id: ID
    kind: Literal["rule_conflict", "scope_choice", "missing_evidence", "execution_boundary"]
    prompt: Text
    blocking: bool
    target_ids: NonEmptyIDs
    finding_ids: NonEmptyIDs
    work_item_ids: IDs
    rule_refs: IDs
    evidence_refs: Materials
    why_blocking: Text | None = None
    options: Annotated[list[QuestionOption], Field(max_length=10)]
    allowed_answer_types: Annotated[
        list[Literal["select", "clarify", "mark_insufficient"]], Field(min_length=1, max_length=3)
    ]

    @model_validator(mode="after")
    def answer_contract(self):
        if self.blocking != (self.why_blocking is not None):
            raise ValueError("why_blocking is required exactly for a blocking question")
        if "select" in self.allowed_answer_types and len(self.options) < 2:
            raise ValueError("Select needs at least two options")
        if len({option.id for option in self.options}) != len(self.options):
            raise ValueError("Duplicate option ID")
        return self


class HandlingIntent(StrictModel):
    kind: Literal[
        "align_documentation",
        "align_example",
        "restore_implementation",
        "correct_test_expectation",
        "obtain_evidence",
        "resolve_rule",
    ]
    text: Text


class IncludedScope(StrictModel):
    artifact_role: Role
    paths: Annotated[list[RepoPath], Field(min_length=1, max_length=100)]


class ExcludedScope(StrictModel):
    paths: Annotated[list[RepoPath], Field(min_length=1, max_length=100)]
    reason: Text


class ProposedScope(StrictModel):
    include: Annotated[list[IncludedScope], Field(min_length=1, max_length=100)]
    exclude: Annotated[list[ExcludedScope], Field(max_length=100)]


class TypedRef(StrictModel):
    kind: Literal["question", "finding", "work_item", "target", "rule", "source"]
    id: ID


class Blocker(StrictModel):
    code: Literal[
        "missing_rule",
        "missing_evidence",
        "unresolved_question",
        "dependency_not_ready",
        "scope_unresolved",
        "other",
    ]
    reason: Text
    refs: Annotated[list[TypedRef], Field(max_length=100)]


class WorkItem(StrictModel):
    id: ID
    title: Annotated[str, Field(min_length=1, max_length=256)]
    finding_ids: NonEmptyIDs
    target_ids: NonEmptyIDs
    rule_refs: IDs
    source_refs: SourceRefs
    handling_intent: HandlingIntent
    proposed_scope: ProposedScope
    depends_on: IDs
    readiness: Literal["ready", "not_ready"]
    blockers: Annotated[list[Blocker], Field(max_length=100)]
    acceptance_ids: IDs
    execution_authorized: Literal[False]

    @model_validator(mode="after")
    def readiness_contract(self):
        if self.readiness == "ready" and (self.blockers or not self.acceptance_ids):
            raise ValueError("Ready work needs acceptance and no blocker")
        if self.readiness == "not_ready" and not self.blockers:
            raise ValueError("Not-ready work needs a blocker")
        return self


class VerificationMethod(StrictModel):
    kind: Literal["static_review", "external_controlled_execution"]
    procedure: LongText
    required_environment: Text


class AcceptanceItem(StrictModel):
    id: ID
    work_item_id: ID
    finding_ids: NonEmptyIDs
    target_ids: NonEmptyIDs
    rule_refs: IDs
    source_refs: SourceRefs
    given: Text
    when: Text
    then: Text
    verification_method: VerificationMethod
    expected_evidence: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=1000)]],
        Field(min_length=1, max_length=20),
    ]
    evidence_refs: IDs
    execution_status: Literal["NOT_RUN"]


class ReportPayload(StrictModel):
    schema_version: Literal["contract-review-report-payload.v2.1"]
    summary: LongText
    coverage: Annotated[list[Coverage], Field(min_length=1, max_length=100)]
    check_results: Annotated[list[CheckResult], Field(min_length=1, max_length=200)]
    rule_uses: Annotated[list[RuleUse], Field(max_length=100)]
    findings: Annotated[list[Finding], Field(min_length=1, max_length=100)]
    questions: Annotated[list[Question], Field(max_length=20)]
    work_items: Annotated[list[WorkItem], Field(max_length=100)]
    acceptance_items: Annotated[list[AcceptanceItem], Field(max_length=200)]
    adopted_child_result_refs: Annotated[list, Field(max_length=0)]
    limitations: Notes


class ActionReason(StrictModel):
    gap: Text
    evidence_refs: Materials
    expected_information: Text


class SubmitReport(StrictModel):
    schema_version: Literal["contract-review-action.v2.1"]
    action: Literal["submit_report"]
    reason: ActionReason
    report: ReportPayload


class ReviewIssue(StrictModel):
    subject_kind: Literal["finding", "question", "work_item", "acceptance", "report"]
    subject_id: Annotated[str, Field(max_length=64)]
    code: Literal[
        "unsupported_claim",
        "wrong_scope",
        "version_mismatch",
        "missing_evidence",
        "wrong_artifact",
        "handoff_incomplete",
        "bad_reference",
        "other",
    ]
    reason: Text
    evidence_refs: Materials


class ReviewResult(StrictModel):
    schema_version: Literal["contract-review-review-result.v2"]
    type: Literal["review_result"]
    candidate_report_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    outcome: Literal["accept", "revise", "insufficient"]
    issues: Annotated[list[ReviewIssue], Field(max_length=20)]
    revision_feedback: Annotated[str, Field(max_length=4000)]

    @model_validator(mode="after")
    def feedback_contract(self):
        if self.outcome == "accept" and (self.issues or self.revision_feedback):
            raise ValueError("Accept must not contain issues or feedback")
        if self.outcome != "accept" and (not self.issues or not self.revision_feedback.strip()):
            raise ValueError("Rework needs explicit issues and feedback")
        return self
