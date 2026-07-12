"""Review Worker implementation for T-017."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from specflow.context import ProjectContext
from specflow.context_builder import ContextBuilder
from specflow.fallback import FallbackLevel, FallbackManager
from specflow.llm import LLMClient, LLMMessage, LLMRequest, LLMResponse
from specflow.prompts import PromptRegistry
from specflow.token_budget import BudgetPolicy, TokenBudgetManager
from specflow.trace import LLMTrace, TraceRecorder
from specflow.workers.analyze import AnalysisOutput
from specflow.workers.base import BaseWorker
from specflow.workers.generate import GenerationOutput
from specflow.workers.models import (
    WorkerContext,
    WorkerMetadata,
    WorkerResult,
    WorkerRole,
    sanitize_worker_text,
)

_SEVERITIES = {"info", "low", "medium", "high", "critical"}


class ReviewDecision(StrEnum):
    PASS = "PASS"
    REJECT = "REJECT"


@dataclass(frozen=True)
class ReviewIssue:
    code: str
    severity: str
    message: str
    related_requirement: str
    suggestion: str

    def __post_init__(self) -> None:
        for field_name in ["code", "severity", "message", "related_requirement", "suggestion"]:
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"ReviewIssue.{field_name} must not be empty")
        if self.severity not in _SEVERITIES:
            raise ValueError("ReviewIssue.severity is invalid")

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "related_requirement": self.related_requirement,
            "severity": self.severity,
            "suggestion": self.suggestion,
        }


@dataclass(frozen=True)
class ReviewOutput:
    decision: ReviewDecision
    summary: str
    issues: tuple[ReviewIssue, ...]
    missing_requirements: tuple[str, ...]
    risk_findings: tuple[str, ...]
    acceptance_criteria_results: tuple[tuple[str, bool, str], ...]
    severity: str
    requires_revision: bool
    requires_human_review: bool
    analysis_hash: str
    generation_hash: str
    degraded: bool
    review_hash: str = field(default="")

    def __post_init__(self) -> None:
        if not isinstance(self.decision, ReviewDecision):
            raise ValueError("ReviewOutput.decision must be a ReviewDecision")
        if not isinstance(self.summary, str) or not self.summary.strip():
            raise ValueError("ReviewOutput.summary must not be empty")
        if self.severity not in _SEVERITIES:
            raise ValueError("ReviewOutput.severity is invalid")
        for hash_name in ["analysis_hash", "generation_hash"]:
            if not isinstance(getattr(self, hash_name), str) or len(getattr(self, hash_name)) != 64:
                raise ValueError(f"ReviewOutput.{hash_name} must be a stable hash")
        if self.decision == ReviewDecision.REJECT and not self.requires_revision:
            raise ValueError("REJECT review output must require revision")
        if self.degraded and not self.requires_human_review:
            raise ValueError("Degraded review output must require human review")
        if not self.acceptance_criteria_results:
            raise ValueError("ReviewOutput.acceptance_criteria_results must not be empty")
        if not self.review_hash:
            object.__setattr__(self, "review_hash", self._calculate_hash())

    @classmethod
    def from_json(
        cls,
        content: str,
        *,
        analysis_hash: str,
        generation_hash: str,
    ) -> ReviewOutput:
        raw = json.loads(content)
        if not isinstance(raw, dict):
            raise ValueError("ReviewOutput JSON must be an object")
        required = {
            "decision",
            "summary",
            "issues",
            "missing_requirements",
            "risk_findings",
            "acceptance_criteria_results",
            "severity",
            "requires_revision",
            "requires_human_review",
            "analysis_hash",
            "generation_hash",
            "degraded",
        }
        missing = sorted(required - set(raw))
        if missing:
            raise ValueError(f"ReviewOutput missing fields: {', '.join(missing)}")
        if raw["analysis_hash"] != analysis_hash or raw["generation_hash"] != generation_hash:
            raise ValueError("ReviewOutput lineage hashes do not match inputs")
        return cls(
            decision=ReviewDecision(str(raw["decision"])),
            summary=sanitize_worker_text(str(raw["summary"])),
            issues=_issues(raw["issues"]),
            missing_requirements=_stable_tuple(raw["missing_requirements"], allow_empty=True),
            risk_findings=_stable_tuple(raw["risk_findings"], allow_empty=True),
            acceptance_criteria_results=_criteria_results(raw["acceptance_criteria_results"]),
            severity=sanitize_worker_text(str(raw["severity"])).lower(),
            requires_revision=_bool_field(raw, "requires_revision"),
            requires_human_review=_bool_field(raw, "requires_human_review"),
            analysis_hash=analysis_hash,
            generation_hash=generation_hash,
            degraded=_bool_field(raw, "degraded"),
        )

    @classmethod
    def degraded_output(
        cls,
        *,
        reason: str,
        analysis: AnalysisOutput,
        generation: GenerationOutput,
    ) -> ReviewOutput:
        safe_reason = sanitize_worker_text(reason)
        return cls(
            decision=ReviewDecision.REJECT,
            summary="Review could not be completed deterministically.",
            issues=(
                ReviewIssue(
                    code="REVIEW_DEGRADED",
                    severity="high",
                    message=f"Manual review required: {safe_reason}",
                    related_requirement=analysis.requirement_summary,
                    suggestion="Human reviewer must inspect the generated plan.",
                ),
            ),
            missing_requirements=("Unknown until manual review completes.",),
            risk_findings=("Runtime review output was unavailable or invalid.",),
            acceptance_criteria_results=tuple(
                (criterion, False, "Requires manual review.")
                for criterion, _ in generation.acceptance_criteria_mapping
            ),
            severity="high",
            requires_revision=True,
            requires_human_review=True,
            analysis_hash=analysis.analysis_hash,
            generation_hash=generation.generation_hash,
            degraded=True,
        )

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def as_dict(self) -> dict[str, object]:
        return {
            "acceptance_criteria_results": [
                {"criterion": criterion, "notes": notes, "passed": passed}
                for criterion, passed, notes in self.acceptance_criteria_results
            ],
            "analysis_hash": self.analysis_hash,
            "decision": self.decision.value,
            "degraded": self.degraded,
            "generation_hash": self.generation_hash,
            "issues": [issue.as_dict() for issue in self.issues],
            "missing_requirements": list(self.missing_requirements),
            "requires_human_review": self.requires_human_review,
            "requires_revision": self.requires_revision,
            "review_hash": self.review_hash,
            "risk_findings": list(self.risk_findings),
            "severity": self.severity,
            "summary": self.summary,
        }

    def _calculate_hash(self) -> str:
        import hashlib

        payload = dict(self.as_dict())
        payload.pop("review_hash", None)
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ReviewWorker(BaseWorker):
    """Review generated output against analysis and requirements."""

    def __init__(
        self,
        *,
        project_context: ProjectContext,
        llm_client: LLMClient,
        trace_recorder: TraceRecorder,
        prompt_registry: PromptRegistry | None = None,
        context_builder: ContextBuilder | None = None,
        budget_manager: TokenBudgetManager | None = None,
        fallback_manager: FallbackManager | None = None,
        model: str = "mock-model",
        prompt_name: str = "review_generation",
        prompt_version: str = "1.0.0",
    ) -> None:
        super().__init__(
            WorkerMetadata(
                name="review-worker",
                role=WorkerRole.REVIEW,
                version="1.0.0",
                description="Review generated implementation plans against analysis.",
            )
        )
        self._project_context = project_context
        self._llm_client = llm_client
        self._trace_recorder = trace_recorder
        self._prompt_registry = prompt_registry or PromptRegistry()
        self._context_builder = context_builder or ContextBuilder()
        self._budget_manager = budget_manager or TokenBudgetManager(
            BudgetPolicy(max_tokens=4096, reserved_response_tokens=1024)
        )
        self._fallback_manager = fallback_manager or FallbackManager()
        self._model = model
        self._prompt_name = prompt_name
        self._prompt_version = prompt_version

    def execute(self, context: WorkerContext) -> WorkerResult:
        analysis, generation, failure = self._inputs_from_prior_outputs(context)
        if failure is not None:
            return failure
        assert analysis is not None and generation is not None

        try:
            prompt = self._prompt_registry.get(self._prompt_name, self._prompt_version)
            built_context = self._context_builder.build(
                prompt_definition=prompt,
                project_context=self._project_context,
                user_requirement=context.requirement,
                variables={
                    "requirement_analysis": analysis.to_json(),
                    "generation_output": generation.to_json(),
                },
            )
            budget = self._budget_manager.apply(built_context)
        except Exception as exc:
            return WorkerResult.failure_result(
                worker_name=self.name,
                worker_role=self.role,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

        response_holder: dict[str, LLMResponse] = {}

        def operation() -> str:
            response = self._llm_client.complete(
                LLMRequest(
                    model=self._model,
                    messages=[
                        LLMMessage(role="system", content=budget.context.system_message),
                        LLMMessage(role="user", content=budget.context.user_message),
                    ],
                    temperature=0.0,
                    max_tokens=budget.policy.reserved_response_tokens or 1024,
                    response_format="json",
                )
            )
            response_holder["response"] = response
            return response.content

        fallback = self._fallback_manager.execute(operation, expect_json=True)
        output, parse_error = self._parse_or_degrade(
            fallback.content,
            fallback.status,
            analysis=analysis,
            generation=generation,
        )
        if (analysis.degraded or generation.degraded) and not output.degraded:
            output = ReviewOutput(
                decision=output.decision,
                summary=output.summary,
                issues=output.issues,
                missing_requirements=output.missing_requirements,
                risk_findings=output.risk_findings,
                acceptance_criteria_results=output.acceptance_criteria_results,
                severity=output.severity,
                requires_revision=output.requires_revision,
                requires_human_review=True,
                analysis_hash=output.analysis_hash,
                generation_hash=output.generation_hash,
                degraded=True,
            )
        effective_fallback_level = (
            FallbackLevel.RULE_BASELINE.value if parse_error else fallback.fallback_level.value
        )
        self._record_trace(
            context=context,
            prompt_hash=prompt.prompt_hash,
            context_hash=budget.context_hash,
            fallback_level=effective_fallback_level,
            retry_count=fallback.retry_count,
            status="success" if not output.degraded else "degraded",
            response=response_holder.get("response"),
            error_type=fallback.error_type or (type(parse_error).__name__ if parse_error else None),
        )

        return WorkerResult.success_result(
            worker_name=self.name,
            worker_role=self.role,
            output=(
                ("review_json", output.to_json()),
                ("review_hash", output.review_hash),
                ("analysis_hash", output.analysis_hash),
                ("generation_hash", output.generation_hash),
            ),
            metadata={
                "analysis_hash": output.analysis_hash,
                "decision": output.decision.value,
                "degraded": str(output.degraded).lower(),
                "fallback_level": effective_fallback_level,
                "generation_hash": output.generation_hash,
                "requires_human_review": str(output.requires_human_review).lower(),
                "requires_revision": str(output.requires_revision).lower(),
                "review_hash": output.review_hash,
            },
        )

    def _inputs_from_prior_outputs(
        self,
        context: WorkerContext,
    ) -> tuple[AnalysisOutput | None, GenerationOutput | None, WorkerResult | None]:
        prior = dict(context.prior_outputs)
        raw_analysis = prior.get("analysis_json")
        raw_generation = prior.get("generation_json")
        if raw_analysis is None:
            return (
                None,
                None,
                self._failure("MissingAnalysisOutput", "ReviewWorker requires analysis_json"),
            )
        if raw_generation is None:
            return (
                None,
                None,
                self._failure(
                    "MissingGenerationOutput",
                    "ReviewWorker requires generation_json",
                ),
            )
        try:
            analysis = AnalysisOutput.from_json(raw_analysis)
            generation = GenerationOutput.from_json(
                raw_generation,
                analysis_hash=analysis.analysis_hash,
            )
        except Exception as exc:
            return None, None, self._failure(type(exc).__name__, f"Invalid review input: {exc}")
        return analysis, generation, None

    def _failure(self, error_type: str, error_message: str) -> WorkerResult:
        return WorkerResult.failure_result(
            worker_name=self.name,
            worker_role=self.role,
            error_type=error_type,
            error_message=error_message,
        )

    @staticmethod
    def _parse_or_degrade(
        content: str,
        fallback_status: str,
        *,
        analysis: AnalysisOutput,
        generation: GenerationOutput,
    ) -> tuple[ReviewOutput, Exception | None]:
        if fallback_status == "degraded":
            return ReviewOutput.degraded_output(
                reason=content,
                analysis=analysis,
                generation=generation,
            ), None
        try:
            return ReviewOutput.from_json(
                content,
                analysis_hash=analysis.analysis_hash,
                generation_hash=generation.generation_hash,
            ), None
        except Exception as exc:
            return (
                ReviewOutput.degraded_output(
                    reason=str(exc),
                    analysis=analysis,
                    generation=generation,
                ),
                exc,
            )

    def _record_trace(
        self,
        *,
        context: WorkerContext,
        prompt_hash: str,
        context_hash: str,
        fallback_level: str,
        retry_count: int,
        status: str,
        response: LLMResponse | None,
        error_type: str | None,
    ) -> None:
        self._trace_recorder.record(
            LLMTrace(
                run_id=_safe_trace_run_id(context.run_id, "review"),
                prompt_name=self._prompt_name,
                prompt_version=self._prompt_version,
                prompt_hash=prompt_hash,
                context_hash=context_hash,
                model=self._model,
                latency_ms=response.latency_ms if response else 0,
                input_tokens=response.usage.input_tokens if response else 0,
                output_tokens=response.usage.output_tokens if response else 0,
                status=status,
                error_type=error_type,
                fallback_level=fallback_level,
                retry_count=retry_count,
                metadata={
                    "worker_name": self.name,
                    "worker_role": self.role.value,
                    "worker_version": self.version,
                },
            )
        )


def _issues(value: Any) -> tuple[ReviewIssue, ...]:
    if not isinstance(value, list):
        raise ValueError("ReviewOutput.issues must be a list")
    issues: list[ReviewIssue] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("ReviewOutput.issues items must be objects")
        issues.append(
            ReviewIssue(
                code=sanitize_worker_text(str(item.get("code", ""))),
                severity=sanitize_worker_text(str(item.get("severity", ""))).lower(),
                message=sanitize_worker_text(str(item.get("message", ""))),
                related_requirement=sanitize_worker_text(str(item.get("related_requirement", ""))),
                suggestion=sanitize_worker_text(str(item.get("suggestion", ""))),
            )
        )
    return tuple(sorted(issues, key=lambda issue: (issue.severity, issue.code, issue.message)))


def _stable_tuple(value: Any, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError("ReviewOutput sequence fields must be lists")
    if any(not isinstance(item, str) for item in value):
        raise ValueError("ReviewOutput sequence fields must contain strings")
    clean = {sanitize_worker_text(item).strip() for item in value if item.strip()}
    if not clean and not allow_empty:
        raise ValueError("ReviewOutput sequence fields must not be empty")
    return tuple(sorted(clean))


def _criteria_results(value: Any) -> tuple[tuple[str, bool, str], ...]:
    if not isinstance(value, list):
        raise ValueError("ReviewOutput.acceptance_criteria_results must be a list")
    results: list[tuple[str, bool, str]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("ReviewOutput.acceptance_criteria_results items must be objects")
        criterion = item.get("criterion")
        passed = item.get("passed")
        notes = item.get("notes")
        if not isinstance(criterion, str) or not isinstance(notes, str):
            raise ValueError("ReviewOutput.acceptance criteria values must be strings")
        if not isinstance(passed, bool):
            raise ValueError("ReviewOutput.acceptance criteria passed must be boolean")
        results.append((sanitize_worker_text(criterion), passed, sanitize_worker_text(notes)))
    if not results:
        raise ValueError("ReviewOutput.acceptance_criteria_results must not be empty")
    return tuple(sorted(set(results), key=lambda item: item[0]))


def _bool_field(raw: dict[str, object], field_name: str) -> bool:
    value = raw[field_name]
    if not isinstance(value, bool):
        raise ValueError(f"ReviewOutput.{field_name} must be a boolean")
    return value


def _safe_trace_run_id(run_id: str, suffix: str) -> str:
    safe_run_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", run_id.strip()).strip(".-")
    if not safe_run_id:
        safe_run_id = "run"
    return f"{safe_run_id}-{suffix}"
