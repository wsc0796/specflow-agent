"""Generate Worker implementation for T-016."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
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
from specflow.workers.models import (
    WorkerContext,
    WorkerMetadata,
    WorkerResult,
    WorkerRole,
    sanitize_worker_text,
)


@dataclass(frozen=True)
class GenerationOutput:
    """Structured specification-generation output."""

    requirement_summary: str
    proposed_solution: str
    architecture_or_design: str
    affected_components: tuple[str, ...]
    implementation_steps: tuple[str, ...]
    api_or_data_changes: tuple[str, ...]
    test_plan: tuple[str, ...]
    risks: tuple[str, ...]
    acceptance_criteria_mapping: tuple[tuple[str, str], ...]
    analysis_hash: str
    requires_review: bool
    degraded: bool
    generation_hash: str = field(default="")

    def __post_init__(self) -> None:
        for field_name in ["requirement_summary", "proposed_solution", "architecture_or_design"]:
            if (
                not isinstance(getattr(self, field_name), str)
                or not getattr(self, field_name).strip()
            ):
                raise ValueError(f"GenerationOutput.{field_name} must not be empty")
        if not isinstance(self.analysis_hash, str) or len(self.analysis_hash) != 64:
            raise ValueError("GenerationOutput.analysis_hash must be a stable hash")
        for field_name in [
            "affected_components",
            "implementation_steps",
            "api_or_data_changes",
            "test_plan",
            "risks",
        ]:
            value = getattr(self, field_name)
            if not isinstance(value, tuple):
                raise ValueError(f"GenerationOutput.{field_name} must be a tuple")
            if any(not isinstance(item, str) or not item.strip() for item in value):
                raise ValueError(f"GenerationOutput.{field_name} must contain strings")
        if not self.acceptance_criteria_mapping:
            raise ValueError("GenerationOutput.acceptance_criteria_mapping must not be empty")
        for criterion, implementation in self.acceptance_criteria_mapping:
            if not criterion.strip() or not implementation.strip():
                raise ValueError("GenerationOutput.acceptance_criteria_mapping is invalid")
        if not isinstance(self.requires_review, bool) or not isinstance(self.degraded, bool):
            raise ValueError("GenerationOutput review flags must be booleans")
        if self.degraded and not self.requires_review:
            raise ValueError("Degraded GenerationOutput must require review")
        if not self.generation_hash:
            object.__setattr__(self, "generation_hash", self._calculate_hash())

    @classmethod
    def from_json(cls, content: str, *, analysis_hash: str) -> GenerationOutput:
        raw = json.loads(content)
        if not isinstance(raw, dict):
            raise ValueError("GenerationOutput JSON must be an object")
        required = {
            "requirement_summary",
            "proposed_solution",
            "architecture_or_design",
            "affected_components",
            "implementation_steps",
            "api_or_data_changes",
            "test_plan",
            "risks",
            "acceptance_criteria_mapping",
            "analysis_hash",
            "requires_review",
            "degraded",
        }
        missing = sorted(required - set(raw))
        if missing:
            raise ValueError(f"GenerationOutput missing fields: {', '.join(missing)}")
        if raw["analysis_hash"] != analysis_hash:
            raise ValueError("GenerationOutput analysis_hash does not match AnalysisOutput")
        return cls(
            requirement_summary=sanitize_worker_text(str(raw["requirement_summary"])),
            proposed_solution=sanitize_worker_text(str(raw["proposed_solution"])),
            architecture_or_design=sanitize_worker_text(str(raw["architecture_or_design"])),
            affected_components=_stable_tuple(raw["affected_components"]),
            implementation_steps=_stable_tuple(raw["implementation_steps"]),
            api_or_data_changes=_stable_tuple(raw["api_or_data_changes"]),
            test_plan=_stable_tuple(raw["test_plan"]),
            risks=_stable_tuple(raw["risks"]),
            acceptance_criteria_mapping=_stable_mapping(raw["acceptance_criteria_mapping"]),
            analysis_hash=analysis_hash,
            requires_review=_bool_field(raw, "requires_review"),
            degraded=_bool_field(raw, "degraded"),
        )

    @classmethod
    def degraded_output(cls, *, reason: str, analysis: AnalysisOutput) -> GenerationOutput:
        safe_reason = sanitize_worker_text(reason)
        return cls(
            requirement_summary=analysis.requirement_summary,
            proposed_solution="Generation could not be completed deterministically.",
            architecture_or_design="Manual design review is required.",
            affected_components=analysis.affected_components,
            implementation_steps=("Manual implementation planning is required.",),
            api_or_data_changes=("No automatic API or data changes were produced.",),
            test_plan=("A human reviewer must define the test plan.",),
            risks=(f"Manual review required: {safe_reason}",),
            acceptance_criteria_mapping=tuple(
                (criterion, "Requires manual implementation mapping.")
                for criterion in analysis.acceptance_criteria
            ),
            analysis_hash=analysis.analysis_hash,
            requires_review=True,
            degraded=True,
        )

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def as_dict(self) -> dict[str, object]:
        return {
            "acceptance_criteria_mapping": [
                {"criterion": criterion, "implementation": implementation}
                for criterion, implementation in self.acceptance_criteria_mapping
            ],
            "affected_components": list(self.affected_components),
            "analysis_hash": self.analysis_hash,
            "api_or_data_changes": list(self.api_or_data_changes),
            "architecture_or_design": self.architecture_or_design,
            "degraded": self.degraded,
            "generation_hash": self.generation_hash,
            "implementation_steps": list(self.implementation_steps),
            "proposed_solution": self.proposed_solution,
            "requirement_summary": self.requirement_summary,
            "requires_review": self.requires_review,
            "risks": list(self.risks),
            "test_plan": list(self.test_plan),
        }

    def _calculate_hash(self) -> str:
        import hashlib

        payload = dict(self.as_dict())
        payload.pop("generation_hash", None)
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class GenerateWorker(BaseWorker):
    """Generate a bounded implementation plan from an AnalysisOutput."""

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
        prompt_name: str = "generate_spec",
        prompt_version: str = "1.0.0",
    ) -> None:
        super().__init__(
            WorkerMetadata(
                name="generate-worker",
                role=WorkerRole.GENERATE,
                version="1.0.0",
                description="Generate a bounded implementation plan from requirement analysis.",
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
        analysis, failure = self._analysis_from_prior_outputs(context)
        if failure is not None:
            return failure
        assert analysis is not None

        try:
            prompt = self._prompt_registry.get(self._prompt_name, self._prompt_version)
            built_context = self._context_builder.build(
                prompt_definition=prompt,
                project_context=self._project_context,
                user_requirement=context.requirement,
                variables={"requirement_analysis": analysis.to_json()},
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
        )
        if analysis.degraded and not output.degraded:
            output = GenerationOutput(
                requirement_summary=output.requirement_summary,
                proposed_solution=output.proposed_solution,
                architecture_or_design=output.architecture_or_design,
                affected_components=output.affected_components,
                implementation_steps=output.implementation_steps,
                api_or_data_changes=output.api_or_data_changes,
                test_plan=output.test_plan,
                risks=output.risks,
                acceptance_criteria_mapping=output.acceptance_criteria_mapping,
                analysis_hash=output.analysis_hash,
                requires_review=True,
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
                ("generation_json", output.to_json()),
                ("generation_hash", output.generation_hash),
                ("analysis_hash", output.analysis_hash),
            ),
            metadata={
                "analysis_hash": output.analysis_hash,
                "context_hash": budget.context_hash,
                "degraded": str(output.degraded).lower(),
                "fallback_level": effective_fallback_level,
                "generation_hash": output.generation_hash,
                "prompt_hash": prompt.prompt_hash,
                "requires_review": str(output.requires_review).lower(),
            },
        )

    def _analysis_from_prior_outputs(
        self,
        context: WorkerContext,
    ) -> tuple[AnalysisOutput | None, WorkerResult | None]:
        prior = dict(context.prior_outputs)
        raw_analysis = prior.get("analysis_json")
        if raw_analysis is None:
            return None, WorkerResult.failure_result(
                worker_name=self.name,
                worker_role=self.role,
                error_type="MissingAnalysisOutput",
                error_message="GenerateWorker requires analysis_json in prior_outputs",
            )
        try:
            return AnalysisOutput.from_json(raw_analysis), None
        except Exception as exc:
            return None, WorkerResult.failure_result(
                worker_name=self.name,
                worker_role=self.role,
                error_type=type(exc).__name__,
                error_message=f"Invalid AnalysisOutput: {exc}",
            )

    @staticmethod
    def _parse_or_degrade(
        content: str,
        fallback_status: str,
        *,
        analysis: AnalysisOutput,
    ) -> tuple[GenerationOutput, Exception | None]:
        if fallback_status == "degraded":
            return GenerationOutput.degraded_output(reason=content, analysis=analysis), None
        try:
            return GenerationOutput.from_json(content, analysis_hash=analysis.analysis_hash), None
        except Exception as exc:
            return GenerationOutput.degraded_output(reason=str(exc), analysis=analysis), exc

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
                run_id=_safe_trace_run_id(context.run_id, "generate"),
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


def _stable_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError("GenerationOutput sequence fields must be lists")
    if any(not isinstance(item, str) for item in value):
        raise ValueError("GenerationOutput sequence fields must contain strings")
    clean = {sanitize_worker_text(item).strip() for item in value if item.strip()}
    if not clean:
        raise ValueError("GenerationOutput sequence fields must not be empty")
    return tuple(sorted(clean))


def _stable_mapping(value: Any) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list):
        raise ValueError("GenerationOutput.acceptance_criteria_mapping must be a list")
    pairs: list[tuple[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("GenerationOutput.acceptance_criteria_mapping items must be objects")
        criterion = item.get("criterion")
        implementation = item.get("implementation")
        if not isinstance(criterion, str) or not isinstance(implementation, str):
            raise ValueError("GenerationOutput.acceptance_criteria_mapping values must be strings")
        pairs.append((sanitize_worker_text(criterion), sanitize_worker_text(implementation)))
    if not pairs:
        raise ValueError("GenerationOutput.acceptance_criteria_mapping must not be empty")
    return tuple(sorted(set(pairs)))


def _bool_field(raw: dict[str, object], field_name: str) -> bool:
    value = raw[field_name]
    if not isinstance(value, bool):
        raise ValueError(f"GenerationOutput.{field_name} must be a boolean")
    return value


def _safe_trace_run_id(run_id: str, suffix: str) -> str:
    safe_run_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", run_id.strip()).strip(".-")
    if not safe_run_id:
        safe_run_id = "run"
    return f"{safe_run_id}-{suffix}"
