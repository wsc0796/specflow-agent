"""Phase 2 contract tests: finding-driven revision end to end.

Covers strict schemas, real revision LLMRequest wiring, resolution integrity,
terminal states, golden resolved / human-review cases, and out-of-scope guards.
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from task_brief_test_helpers import controlled_evidence, execution_input, task_brief

from specflow.agents.adapter import AgentRunner
from specflow.agents.models import AgentIdentity, AgentRole
from specflow.llm.models import LLMUsage
from specflow.plan.hash_utils import canonical_json_bytes
from specflow.revision.models import (
    FindingResolution,
    FindingSeverity,
    ResolutionStatus,
    ReviewFinding,
    RevisionContext,
    RevisionInput,
    RevisionResult,
    ValidatedAgentOutput,
    derive_finding_id,
)
from specflow.runner_multi import run_multi_agent
from specflow.schema.agent_payloads import DesignPayload, ReviewPayload
from specflow.schema.models import AgentExecutionInput
from specflow.schema.registry import SchemaRegistry


def _finding(
    *,
    description: str = "Initial design omits module_b",
    target_agent_id: str = "design-agent-v1",
    evidence_refs: tuple[str, ...] = (),
    affected_artifact: str | None = None,
) -> ReviewFinding:
    finding_id = derive_finding_id(
        target_agent_id=target_agent_id,
        category="completeness",
        description=description,
        affected_artifact=affected_artifact,
        evidence_refs=evidence_refs,
    )
    return ReviewFinding(
        finding_id=finding_id,
        severity=FindingSeverity.WARNING,
        category="completeness",
        description=description,
        target_agent_id=target_agent_id,
        affected_artifact=affected_artifact,
        evidence_refs=evidence_refs,
        recommendation="Add module_b coverage to the output.",
    )


def _identity(agent_id: str = "design-agent-v1") -> AgentIdentity:
    return AgentIdentity(
        agent_id=agent_id,
        role=AgentRole.DESIGN,
        version="1.0.0",
        description="Fixed role description",
        prompt_id="prompts/test/v1",
        prompt_version="1.0.0",
        input_schema_id="agent/design/v1/input",
        output_schema_id="agent/design/v1/output",
        tool_permissions=frozenset({"read_file"}),
    )


def _registry() -> SchemaRegistry:
    registry = SchemaRegistry()
    registry.register("agent/design/v1/output", DesignPayload)
    registry.freeze()
    return registry


def _prior_output(
    agent_id: str = "design-agent-v1",
    payload: dict[str, Any] | None = None,
) -> ValidatedAgentOutput:
    return ValidatedAgentOutput(
        agent_id=agent_id,
        schema_id="agent/design/v1/output",
        payload=payload or {"summary": "previous design"},
    )


def _revision_context(
    *,
    findings: tuple[ReviewFinding, ...],
    prior: ValidatedAgentOutput | None = None,
    revision_round: int = 1,
    max_revision_rounds: int = 1,
    revision_id: str = "revision-1-design-agent-v1-deadbeef",
) -> RevisionContext:
    selected_prior = prior or _prior_output()
    return RevisionContext(
        revision_id=revision_id,
        revision_round=revision_round,
        max_revision_rounds=max_revision_rounds,
        target_agent_id=selected_prior.agent_id,
        prior_output=selected_prior,
        prior_output_hash=sha256(canonical_json_bytes(selected_prior.payload)).hexdigest(),
        findings=findings,
    )


def _capture_request(
    execution: AgentExecutionInput,
) -> tuple[list[Any], str]:
    class CapturingClient:
        def __init__(self) -> None:
            self.requests: list[Any] = []

        def complete(self, request):
            self.requests.append(request)

            class Response:
                content = json.dumps(
                    {
                        "revised_output": {"summary": "revised design"},
                        "resolutions": [
                            {
                                "finding_id": finding.finding_id,
                                "status": "resolved",
                                "explanation": "fixed",
                            }
                            for finding in execution.revision_context.findings
                        ],
                    }
                )
                input_tokens = 10
                output_tokens = 5
                usage = LLMUsage(input_tokens=10, output_tokens=5)

            return Response()

    client = CapturingClient()
    result = AgentRunner(
        _identity(),
        client,
        model="test-model",
        schema_registry=_registry(),
    ).execute({"validated_input": execution})
    assert result["success"] is True
    return client.requests, client.requests[-1].messages[-1].content


REVISION_SECTIONS = (
    "Original Requirement",
    "Verified Repository Evidence",
    "Role Task Brief",
    "Previous Validated Output",
    "Review Findings To Resolve",
    "Revision Context",
    "Revision Rules",
    "Role-specific Output Contract",
    "Finding Resolution Contract",
)


class TestFindingSchema:
    def test_finding_rejects_extra_fields(self) -> None:
        data = _finding().model_dump(mode="json")
        data["raw_provider_field"] = "nope"
        with pytest.raises(ValidationError, match="Extra inputs"):
            ReviewFinding.model_validate(data)

    def test_finding_id_is_stable_for_normalized_input(self) -> None:
        first = _finding(description="  Missing   module_b ")
        second = _finding(description="Missing module_b")
        assert first.finding_id == second.finding_id
        assert first.finding_id.startswith("F-")

    def test_different_findings_have_different_ids(self) -> None:
        assert (
            _finding(description="Missing module_b").finding_id
            != _finding(description="Wrong error handling").finding_id
        )

    def test_empty_description_and_recommendation_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReviewFinding.model_validate(
                {
                    **(_finding().model_dump(mode="json")),
                    "description": "   ",
                }
            )
        with pytest.raises(ValidationError):
            ReviewFinding.model_validate(
                {
                    **(_finding().model_dump(mode="json")),
                    "recommendation": "",
                }
            )

    def test_legacy_string_cannot_become_finding(self) -> None:
        with pytest.raises(ValidationError):
            ReviewPayload.model_validate(
                {
                    "decision": "REJECT",
                    "summary": "Blocked",
                    "requires_revision": True,
                    "findings": ["plain string finding"],
                }
            )


class TestRevisionInputSchema:
    def _input(
        self,
        *,
        findings: tuple[ReviewFinding, ...],
        prior: ValidatedAgentOutput | None = None,
        revision_round: int = 1,
        max_revision_rounds: int = 1,
    ) -> RevisionInput:
        selected_prior = prior or _prior_output()
        brief = task_brief(
            agent_id=selected_prior.agent_id,
            role=AgentRole.DESIGN,
            output_schema_id=selected_prior.schema_id,
        )
        return RevisionInput.build(
            run_id="run-test",
            revision_id="revision-1-design-agent-v1-deadbeef",
            revision_round=revision_round,
            max_revision_rounds=max_revision_rounds,
            target_agent_id=selected_prior.agent_id,
            role=AgentRole.DESIGN,
            original_requirement="Add module_b",
            verified_evidence=controlled_evidence(),
            task_brief=brief,
            prior_output=selected_prior,
            findings=findings,
            output_schema_id=selected_prior.schema_id,
        )

    def test_round_starts_at_one_and_respects_max(self) -> None:
        with pytest.raises(ValidationError, match="revision_round"):
            self._input(findings=(_finding(),), revision_round=0)
        with pytest.raises(ValidationError, match="revision_round"):
            self._input(findings=(_finding(),), revision_round=2, max_revision_rounds=1)

    def test_prior_output_hash_is_derived_and_verified(self) -> None:
        revision_input = self._input(findings=(_finding(),))
        expected = sha256(canonical_json_bytes(revision_input.prior_output.payload)).hexdigest()
        assert revision_input.prior_output_hash == expected
        tampered = revision_input.model_dump(mode="json")
        tampered["prior_output_hash"] = "0" * 64
        with pytest.raises(ValidationError, match="prior_output_hash"):
            RevisionInput.model_validate(tampered)

    def test_findings_must_target_the_revised_agent(self) -> None:
        foreign = _finding(target_agent_id="test-strategy-agent-v1")
        with pytest.raises(ValidationError, match="must target"):
            self._input(findings=(foreign,))

    def test_task_brief_identity_must_match(self) -> None:
        with pytest.raises(ValidationError, match="Task brief agent"):
            RevisionInput.model_validate(
                {
                    **self._input(findings=(_finding(),)).model_dump(mode="json"),
                    "task_brief": task_brief(
                        agent_id="other-agent",
                        role=AgentRole.DESIGN,
                        output_schema_id="agent/design/v1/output",
                    ).model_dump(mode="json"),
                }
            )


class TestRevisionResultSchema:
    def _result(
        self,
        *,
        findings: tuple[ReviewFinding, ...],
        statuses: tuple[ResolutionStatus, ...] | None = None,
    ) -> RevisionResult:
        resolutions = tuple(
            FindingResolution(
                finding_id=finding.finding_id,
                status=statuses[index] if statuses else ResolutionStatus.RESOLVED,
                explanation="explained",
            )
            for index, finding in enumerate(findings)
        )
        return RevisionResult.build(
            revision_id="revision-1-design-agent-v1-deadbeef",
            revision_round=1,
            parent_output_hash="a" * 64,
            revised_output=_prior_output(payload={"summary": "revised"}),
            input_finding_ids=tuple(finding.finding_id for finding in findings),
            resolutions=resolutions,
        )

    def test_every_finding_has_exactly_one_resolution(self) -> None:
        findings = (_finding(), _finding(description="Second issue"))
        with pytest.raises(ValueError, match="exactly cover"):
            RevisionResult.build(
                revision_id="r1",
                revision_round=1,
                parent_output_hash="a" * 64,
                revised_output=_prior_output(),
                input_finding_ids=tuple(f.finding_id for f in findings),
                resolutions=(
                    FindingResolution(
                        finding_id=findings[0].finding_id,
                        status=ResolutionStatus.RESOLVED,
                        explanation="fixed",
                    ),
                ),
            )

    def test_unknown_and_duplicate_resolution_ids_rejected(self) -> None:
        findings = (_finding(),)
        with pytest.raises(ValueError, match="exactly cover"):
            RevisionResult.build(
                revision_id="r1",
                revision_round=1,
                parent_output_hash="a" * 64,
                revised_output=_prior_output(),
                input_finding_ids=tuple(f.finding_id for f in findings),
                resolutions=(
                    FindingResolution(
                        finding_id="F-ffffffff",
                        status=ResolutionStatus.RESOLVED,
                        explanation="wrong id",
                    ),
                ),
            )
        with pytest.raises(ValueError, match="unique"):
            RevisionResult.build(
                revision_id="r1",
                revision_round=1,
                parent_output_hash="a" * 64,
                revised_output=_prior_output(),
                input_finding_ids=tuple(f.finding_id for f in findings),
                resolutions=(
                    FindingResolution(
                        finding_id=findings[0].finding_id,
                        status=ResolutionStatus.RESOLVED,
                        explanation="dup",
                    ),
                    FindingResolution(
                        finding_id=findings[0].finding_id,
                        status=ResolutionStatus.NOT_APPLICABLE,
                        explanation="dup",
                    ),
                ),
            )

    def test_unresolved_ids_consistent_with_resolutions(self) -> None:
        result = self._result(
            findings=(_finding(),),
            statuses=(ResolutionStatus.UNRESOLVED,),
        )
        assert result.unresolved_finding_ids == (result.resolutions[0].finding_id,)


class TestRevisionRequestWiring:
    def _execution(self, *, findings, prior=None, round_=1) -> AgentExecutionInput:
        brief = task_brief(
            agent_id="design-agent-v1",
            role=AgentRole.DESIGN,
            output_schema_id="agent/design/v1/output",
        )
        return execution_input(
            brief=brief,
            evidence=controlled_evidence(content="Evidence byte-identical"),
            requirement="Add module_b",
            prior_outputs={"repository-analyst-agent-v1": {"summary": "analysis"}},
        ).model_copy(
            update={
                "revision_context": _revision_context(
                    findings=findings,
                    prior=prior,
                    revision_round=round_,
                )
            }
        )

    def test_findings_prior_output_and_round_enter_real_request(self) -> None:
        finding = _finding(description="REVISION_MARKER_omits_module_b")
        execution = self._execution(findings=(finding,), round_=3)
        _, message = _capture_request(execution)
        assert "REVISION_MARKER_omits_module_b" in message
        assert finding.finding_id in message
        assert '"previous design"' in message
        assert '"revision_round": 3' in message
        assert "Add module_b" in message
        assert "Evidence byte-identical" in message
        assert "Inspect the design boundary" in message

    def test_changing_finding_changes_only_findings_section(self) -> None:
        def run(finding: ReviewFinding) -> tuple[str, dict[str, str]]:
            execution = self._execution(findings=(finding,))
            _, message = _capture_request(execution)
            positions = {name: message.index(f"[{name}]") for name in REVISION_SECTIONS}
            sections: dict[str, str] = {}
            names = list(REVISION_SECTIONS)
            for index, name in enumerate(names):
                start = positions[name] + len(name) + 2
                end = positions[names[index + 1]] if index + 1 < len(names) else len(message)
                sections[name] = message[start:end].strip()
            return message, sections

        first_message, first_sections = run(_finding(description="Finding alpha"))
        second_message, second_sections = run(_finding(description="Finding beta"))
        assert first_message != second_message
        assert (
            first_sections["Review Findings To Resolve"]
            != second_sections["Review Findings To Resolve"]
        )
        for name in set(REVISION_SECTIONS) - {"Review Findings To Resolve"}:
            assert first_sections[name] == second_sections[name]

    def test_revision_prompt_is_distinct_from_first_run_prompt(self) -> None:
        finding = _finding()
        execution = self._execution(findings=(finding,))
        _, revision_message = _capture_request(execution)
        for section in (
            "Previous Validated Output",
            "Review Findings To Resolve",
            "Revision Rules",
            "Finding Resolution Contract",
        ):
            assert f"[{section}]" in revision_message
        normal_execution = execution_input(
            brief=task_brief(
                agent_id="design-agent-v1",
                role=AgentRole.DESIGN,
                output_schema_id="agent/design/v1/output",
            ),
            evidence=controlled_evidence(content="Evidence byte-identical"),
            requirement="Add module_b",
        )

        class NormalClient:
            def __init__(self) -> None:
                self.requests = []

            def complete(self, request):
                self.requests.append(request)

                class Response:
                    content = json.dumps({"summary": "design"})
                    input_tokens = 1
                    output_tokens = 1
                    usage = LLMUsage(input_tokens=1, output_tokens=1)

                return Response()

        client = NormalClient()
        AgentRunner(
            _identity(),
            client,
            model="test",
            schema_registry=_registry(),
        ).execute({"validated_input": normal_execution})
        normal_message = client.requests[-1].messages[-1].content
        assert "[Previous Validated Output]" not in normal_message
        assert "[Review Findings To Resolve]" not in normal_message

    def test_prior_output_hash_mismatch_fails_before_provider_call(self) -> None:
        prior = _prior_output(payload={"summary": "previous design"})
        tampered = _revision_context(
            findings=(_finding(),),
            prior=prior,
        ).model_dump(mode="json")
        tampered["prior_output_hash"] = "0" * 64
        # A hash mismatch is rejected at the earliest contract boundary, so it
        # can never reach a provider call.
        with pytest.raises(ValidationError, match="prior_output_hash"):
            RevisionContext.model_validate(tampered)

    def test_revision_target_identity_mismatch_fails_before_provider_call(self) -> None:
        execution = self._execution(findings=(_finding(),))
        execution = execution.model_copy(
            update={
                "revision_context": _revision_context(
                    findings=(_finding(),),
                    prior=_prior_output(agent_id="other-agent-v1"),
                )
            }
        )
        with pytest.raises(ValidationError, match="Revision context target"):
            AgentExecutionInput.model_validate(execution.model_dump(mode="json"))


def _review_output(
    *,
    decision: str,
    findings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "agent_id": "review-agent-v1",
        "role": "review",
        "output": {
            "decision": decision,
            "summary": "Mock review",
            "requires_revision": decision == "REJECT",
            "findings": findings or [],
        },
    }


class TestRunnerGoldenCases:
    def _repo(self, tmp_path: Path) -> Path:
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "app.py").write_text("# app with no module_b\n", encoding="utf-8")
        return repo

    def test_golden_resolved_case(self, tmp_path: Path) -> None:
        repo = self._repo(tmp_path)
        output = tmp_path / "out"
        finding = _finding(description="Initial design omits module_b")
        finding_payload = finding.model_dump(mode="json")

        def design_executor(context: dict[str, Any]) -> dict[str, Any]:
            validated_input = context.get("validated_input")
            revision = getattr(validated_input, "revision_context", None)
            if revision is None:
                return {
                    "agent_id": "design-agent-v1",
                    "role": "design",
                    "output": {"summary": "Design without module_b"},
                }
            revised = {"summary": "Design with module_b added"}
            result = RevisionResult.build(
                revision_id=revision.revision_id,
                revision_round=revision.revision_round,
                parent_output_hash=revision.prior_output_hash,
                revised_output=ValidatedAgentOutput(
                    agent_id="design-agent-v1",
                    schema_id="agent/design/v1/output",
                    payload=revised,
                ),
                input_finding_ids=tuple(f.finding_id for f in revision.findings),
                resolutions=tuple(
                    FindingResolution(
                        finding_id=f.finding_id,
                        status=ResolutionStatus.RESOLVED,
                        explanation="Added module_b coverage",
                        changed_sections=("summary",),
                    )
                    for f in revision.findings
                ),
            )
            return {
                "agent_id": "design-agent-v1",
                "role": "design",
                "output": revised,
                "revision_result": result.model_dump(mode="json"),
            }

        reviews: list[str] = []

        def review_executor(context: dict[str, Any]) -> dict[str, Any]:
            if not reviews:
                reviews.append("REJECT")
                return _review_output(decision="REJECT", findings=[finding_payload])
            reviews.append("PASS")
            return _review_output(decision="PASS")

        code = run_multi_agent(
            repo=repo,
            requirement="Add module_b support",
            output=output,
            mock=True,
            _executor_overrides={
                "design-agent-v1": design_executor,
                "review-agent-v1": review_executor,
            },
        )
        assert code == 0
        run_dir = next(output.glob("run-multi-*"))
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["workflow_state"] == "completed"
        assert manifest["review"]["decision"] == "PASS"
        assert manifest["revision"]["task_count"] == 1
        assert manifest["revision"]["unresolved_finding_count"] == 0
        resolutions = json.loads((run_dir / "finding-resolutions.json").read_text(encoding="utf-8"))
        assert resolutions[0]["finding_id"] == finding.finding_id
        assert resolutions[0]["status"] == "resolved"
        traces = json.loads((run_dir / "traces.json").read_text(encoding="utf-8"))
        event_types = [t["event_type"] for t in traces if "event_type" in t]
        assert event_types.count("FINDING_RESOLVED") == 1
        assert "HUMAN_REVIEW_REQUIRED" not in event_types
        assert reviews == ["REJECT", "PASS"]

    def test_golden_needs_human_review_case(self, tmp_path: Path) -> None:
        repo = self._repo(tmp_path)
        output = tmp_path / "out"
        finding = _finding(description="Unresolvable design conflict")
        finding_payload = finding.model_dump(mode="json")

        def design_executor(context: dict[str, Any]) -> dict[str, Any]:
            validated_input = context.get("validated_input")
            revision = getattr(validated_input, "revision_context", None)
            if revision is None:
                return {
                    "agent_id": "design-agent-v1",
                    "role": "design",
                    "output": {"summary": "Initial design"},
                }
            revised = {"summary": "Revised but conflict remains"}
            result = RevisionResult.build(
                revision_id=revision.revision_id,
                revision_round=revision.revision_round,
                parent_output_hash=revision.prior_output_hash,
                revised_output=ValidatedAgentOutput(
                    agent_id="design-agent-v1",
                    schema_id="agent/design/v1/output",
                    payload=revised,
                ),
                input_finding_ids=tuple(f.finding_id for f in revision.findings),
                resolutions=tuple(
                    FindingResolution(
                        finding_id=f.finding_id,
                        status=ResolutionStatus.UNRESOLVED,
                        explanation="Requires product owner decision",
                    )
                    for f in revision.findings
                ),
            )
            return {
                "agent_id": "design-agent-v1",
                "role": "design",
                "output": revised,
                "revision_result": result.model_dump(mode="json"),
            }

        def reject_review(context: dict[str, Any]) -> dict[str, Any]:
            return _review_output(decision="REJECT", findings=[finding_payload])

        code = run_multi_agent(
            repo=repo,
            requirement="Resolve design conflict",
            output=output,
            mock=True,
            _executor_overrides={
                "design-agent-v1": design_executor,
                "review-agent-v1": reject_review,
            },
        )
        assert code == 5
        run_dir = next(output.glob("run-multi-*"))
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["workflow_state"] == "needs_human_review"
        assert manifest["revision"]["unresolved_finding_count"] == 1
        traces = json.loads((run_dir / "traces.json").read_text(encoding="utf-8"))
        event_types = [t["event_type"] for t in traces if "event_type" in t]
        assert event_types.count("FINDING_UNRESOLVED") == 1
        assert event_types.count("HUMAN_REVIEW_REQUIRED") == 1
        assert event_types.count("REVISION_REQUEST_SUBMITTED") == 0  # mock path stays honest

    def test_unknown_finding_target_fails_closed(self, tmp_path: Path) -> None:
        repo = self._repo(tmp_path)
        output = tmp_path / "out"
        ghost = _finding(description="Targets a ghost agent", target_agent_id="ghost-agent-v1")

        def reject_review(context: dict[str, Any]) -> dict[str, Any]:
            return _review_output(decision="REJECT", findings=[ghost.model_dump(mode="json")])

        assert (
            run_multi_agent(
                repo=repo,
                requirement="Test",
                output=output,
                mock=True,
                _executor_overrides={"review-agent-v1": reject_review},
            )
            == 3
        )
        manifest = json.loads(
            (next(output.glob("run-multi-*")) / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["workflow_state"] == "failed"

    def test_unknown_evidence_ref_fails_closed(self, tmp_path: Path) -> None:
        repo = self._repo(tmp_path)
        output = tmp_path / "out"
        finding = _finding(
            description="Cites missing evidence",
            evidence_refs=("evidence-not-in-bundle",),
        )

        def reject_review(context: dict[str, Any]) -> dict[str, Any]:
            return _review_output(decision="REJECT", findings=[finding.model_dump(mode="json")])

        assert (
            run_multi_agent(
                repo=repo,
                requirement="Test",
                output=output,
                mock=True,
                _executor_overrides={"review-agent-v1": reject_review},
            )
            == 3
        )

    def test_unknown_artifact_fails_closed(self, tmp_path: Path) -> None:
        repo = self._repo(tmp_path)
        output = tmp_path / "out"
        finding = _finding(
            description="Cites unknown artifact",
            affected_artifact="secret-plan.md",
        )

        def reject_review(context: dict[str, Any]) -> dict[str, Any]:
            return _review_output(decision="REJECT", findings=[finding.model_dump(mode="json")])

        assert (
            run_multi_agent(
                repo=repo,
                requirement="Test",
                output=output,
                mock=True,
                _executor_overrides={"review-agent-v1": reject_review},
            )
            == 3
        )

    def test_reject_with_empty_findings_fails_closed(self, tmp_path: Path) -> None:
        repo = self._repo(tmp_path)
        output = tmp_path / "out"

        def reject_review(context: dict[str, Any]) -> dict[str, Any]:
            return _review_output(decision="REJECT")

        assert (
            run_multi_agent(
                repo=repo,
                requirement="Test",
                output=output,
                mock=True,
                _executor_overrides={"review-agent-v1": reject_review},
            )
            == 3
        )

    def test_multi_target_round_is_deterministic_and_isolated(self, tmp_path: Path) -> None:
        repo = self._repo(tmp_path)
        output = tmp_path / "out"
        design_finding = _finding(
            description="Design issue",
            target_agent_id="design-agent-v1",
        )
        test_finding = _finding(
            description="Test strategy issue",
            target_agent_id="test-strategy-agent-v1",
        )

        def revise(agent_id: str) -> Any:
            def executor(context: dict[str, Any]) -> dict[str, Any]:
                validated_input = context.get("validated_input")
                revision = getattr(validated_input, "revision_context", None)
                payload = {"summary": f"revised {agent_id}"}
                if revision is None:
                    return {
                        "agent_id": agent_id,
                        "role": "design" if "design" in agent_id else "test_strategy",
                        "output": payload,
                    }
                result = RevisionResult.build(
                    revision_id=revision.revision_id,
                    revision_round=revision.revision_round,
                    parent_output_hash=revision.prior_output_hash,
                    revised_output=ValidatedAgentOutput(
                        agent_id=agent_id,
                        schema_id=validated_input.output_schema_id,
                        payload=payload,
                    ),
                    input_finding_ids=tuple(f.finding_id for f in revision.findings),
                    resolutions=tuple(
                        FindingResolution(
                            finding_id=f.finding_id,
                            status=ResolutionStatus.RESOLVED,
                            explanation=f"resolved in {agent_id}",
                        )
                        for f in revision.findings
                    ),
                )
                return {
                    "agent_id": agent_id,
                    "role": "design" if "design" in agent_id else "test_strategy",
                    "output": payload,
                    "revision_result": result.model_dump(mode="json"),
                }

            return executor

        reviews: list[str] = []

        def review_executor(context: dict[str, Any]) -> dict[str, Any]:
            if not reviews:
                reviews.append("REJECT")
                return _review_output(
                    decision="REJECT",
                    findings=[
                        design_finding.model_dump(mode="json"),
                        test_finding.model_dump(mode="json"),
                    ],
                )
            reviews.append("PASS")
            return _review_output(decision="PASS")

        code = run_multi_agent(
            repo=repo,
            requirement="Multi-target revision",
            output=output,
            mock=True,
            _executor_overrides={
                "design-agent-v1": revise("design-agent-v1"),
                "test-strategy-agent-v1": revise("test-strategy-agent-v1"),
                "review-agent-v1": review_executor,
            },
        )
        assert code == 0
        run_dir = next(output.glob("run-multi-*"))
        revision_tasks = json.loads((run_dir / "revision-tasks.json").read_text(encoding="utf-8"))
        assert [task["target_agent_id"] for task in revision_tasks] == [
            "design-agent-v1",
            "test-strategy-agent-v1",
        ]
        assert {task["round_number"] for task in revision_tasks} == {1}
        revision_inputs = json.loads((run_dir / "revision-inputs.json").read_text(encoding="utf-8"))
        for revision_input in revision_inputs:
            finding_targets = {finding["target_agent_id"] for finding in revision_input["findings"]}
            assert finding_targets == {revision_input["target_agent_id"]}
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["revision"]["task_count"] == 2
        assert manifest["revision"]["target_agents"] == [
            "design-agent-v1",
            "test-strategy-agent-v1",
        ]

    def test_trace_never_contains_prompt_content(self, tmp_path: Path) -> None:
        repo = self._repo(tmp_path)
        output = tmp_path / "out"
        marker = "PROMPT_SECRET_MARKER_7f3a"
        finding = _finding(description=f"Contains {marker}")

        def reject_review(context: dict[str, Any]) -> dict[str, Any]:
            return _review_output(decision="REJECT", findings=[finding.model_dump(mode="json")])

        assert (
            run_multi_agent(
                repo=repo,
                requirement="Test",
                output=output,
                mock=True,
                _executor_overrides={"review-agent-v1": reject_review},
            )
            == 5
        )
        run_dir = next(output.glob("run-multi-*"))
        traces = (run_dir / "traces.json").read_text(encoding="utf-8")
        assert marker not in traces
        assert "revised design" not in traces
        assert "previous design" not in traces

    def test_manifest_records_revision_artifact_hashes(self, tmp_path: Path) -> None:
        repo = self._repo(tmp_path)
        output = tmp_path / "out"
        finding = _finding()
        reviews: list[str] = []

        def review_executor(context: dict[str, Any]) -> dict[str, Any]:
            if not reviews:
                reviews.append("REJECT")
                return _review_output(decision="REJECT", findings=[finding.model_dump(mode="json")])
            reviews.append("PASS")
            return _review_output(decision="PASS")

        assert (
            run_multi_agent(
                repo=repo,
                requirement="Test",
                output=output,
                mock=True,
                _executor_overrides={"review-agent-v1": review_executor},
            )
            == 0
        )
        run_dir = next(output.glob("run-multi-*"))
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        for name, digest in manifest["revision_artifacts"].items():
            assert sha256((run_dir / name).read_bytes()).hexdigest() == digest
