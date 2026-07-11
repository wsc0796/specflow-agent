"""Analyze Worker implementation for T-015."""

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
from specflow.workers.base import BaseWorker
from specflow.workers.models import (
    WorkerContext,
    WorkerMetadata,
    WorkerResult,
    WorkerRole,
    sanitize_worker_text,
)


@dataclass(frozen=True)
class AnalysisOutput:
    """Structured requirement analysis output."""

    requirement_summary: str
    goals: tuple[str, ...]
    non_goals: tuple[str, ...]
    assumptions: tuple[str, ...]
    affected_components: tuple[str, ...]
    risks: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    evidence: tuple[str, ...]
    requires_review: bool
    degraded: bool
    analysis_hash: str = field(default="")

    def __post_init__(self) -> None:
        if not self.requirement_summary.strip():
            raise ValueError("AnalysisOutput.requirement_summary must not be empty")
        for field_name in [
            "goals",
            "non_goals",
            "assumptions",
            "affected_components",
            "risks",
            "acceptance_criteria",
            "evidence",
        ]:
            value = getattr(self, field_name)
            if not isinstance(value, tuple):
                raise ValueError(f"AnalysisOutput.{field_name} must be a tuple")
            if any(not isinstance(item, str) or not item.strip() for item in value):
                raise ValueError(f"AnalysisOutput.{field_name} must contain non-empty strings")
        if not isinstance(self.requires_review, bool) or not isinstance(self.degraded, bool):
            raise ValueError("AnalysisOutput review flags must be booleans")
        if self.degraded and not self.requires_review:
            raise ValueError("Degraded AnalysisOutput must require review")
        if not self.analysis_hash:
            object.__setattr__(self, "analysis_hash", self._calculate_hash())

    @classmethod
    def from_json(cls, content: str) -> AnalysisOutput:
        """Parse and validate deterministic JSON analysis output."""
        raw = json.loads(content)
        if not isinstance(raw, dict):
            raise ValueError("AnalysisOutput JSON must be an object")
        required = {
            "requirement_summary",
            "goals",
            "non_goals",
            "assumptions",
            "affected_components",
            "risks",
            "acceptance_criteria",
            "evidence",
            "requires_review",
            "degraded",
        }
        missing = sorted(required - set(raw))
        if missing:
            raise ValueError(f"AnalysisOutput missing fields: {', '.join(missing)}")
        requires_review = _bool_field(raw, "requires_review")
        degraded = _bool_field(raw, "degraded")
        return cls(
            requirement_summary=sanitize_worker_text(str(raw["requirement_summary"])),
            goals=_stable_tuple(raw["goals"]),
            non_goals=_stable_tuple(raw["non_goals"]),
            assumptions=_stable_tuple(raw["assumptions"]),
            affected_components=_stable_tuple(raw["affected_components"]),
            risks=_stable_tuple(raw["risks"]),
            acceptance_criteria=_stable_tuple(raw["acceptance_criteria"]),
            evidence=_stable_tuple(raw["evidence"]),
            requires_review=requires_review,
            degraded=degraded,
        )

    @classmethod
    def degraded_output(cls, reason: str) -> AnalysisOutput:
        """Return an honest degraded baseline output."""
        safe_reason = sanitize_worker_text(reason)
        return cls(
            requirement_summary="Analysis could not be completed deterministically.",
            goals=("Manual requirement analysis is required.",),
            non_goals=("No implementation or specification generation was performed.",),
            assumptions=("Runtime output was unavailable or invalid.",),
            affected_components=("unknown",),
            risks=(f"Manual review required: {safe_reason}",),
            acceptance_criteria=("A human reviewer must validate the requirement analysis.",),
            evidence=("fallback:rule_baseline",),
            requires_review=True,
            degraded=True,
        )

    def to_json(self) -> str:
        """Serialize output with stable key ordering."""
        return json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable mapping."""
        return {
            "acceptance_criteria": list(self.acceptance_criteria),
            "affected_components": list(self.affected_components),
            "analysis_hash": self.analysis_hash,
            "assumptions": list(self.assumptions),
            "degraded": self.degraded,
            "evidence": list(self.evidence),
            "goals": list(self.goals),
            "non_goals": list(self.non_goals),
            "requirement_summary": self.requirement_summary,
            "requires_review": self.requires_review,
            "risks": list(self.risks),
        }

    def _calculate_hash(self) -> str:
        import hashlib

        payload = {
            "acceptance_criteria": list(self.acceptance_criteria),
            "affected_components": list(self.affected_components),
            "assumptions": list(self.assumptions),
            "degraded": self.degraded,
            "evidence": list(self.evidence),
            "goals": list(self.goals),
            "non_goals": list(self.non_goals),
            "requirement_summary": self.requirement_summary,
            "requires_review": self.requires_review,
            "risks": list(self.risks),
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class AnalyzeWorker(BaseWorker):
    """Analyze a requirement using the existing M3 runtime components."""

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
        prompt_name: str = "analyze_requirement",
        prompt_version: str = "1.0.0",
    ) -> None:
        super().__init__(
            WorkerMetadata(
                name="analyze-worker",
                role=WorkerRole.ANALYZE,
                version="1.0.0",
                description="Analyze user requirements against project context.",
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
        """Execute requirement analysis and return a WorkerResult."""
        try:
            prompt = self._prompt_registry.get(self._prompt_name, self._prompt_version)
            built_context = self._context_builder.build(
                prompt_definition=prompt,
                project_context=self._project_context,
                user_requirement=context.requirement,
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
        output, parse_error = self._parse_or_degrade(fallback.content, fallback.status)
        effective_fallback_level = (
            FallbackLevel.RULE_BASELINE.value if parse_error else fallback.fallback_level.value
        )
        status = "success" if not output.degraded else "degraded"
        self._record_trace(
            context=context,
            prompt_hash=prompt.prompt_hash,
            context_hash=budget.context_hash,
            fallback_level=effective_fallback_level,
            retry_count=fallback.retry_count,
            status=status,
            response=response_holder.get("response"),
            error_type=fallback.error_type or (type(parse_error).__name__ if parse_error else None),
        )

        metadata = {
            "analysis_hash": output.analysis_hash,
            "context_hash": budget.context_hash,
            "degraded": str(output.degraded).lower(),
            "fallback_level": effective_fallback_level,
            "prompt_hash": prompt.prompt_hash,
            "requires_review": str(output.requires_review).lower(),
        }
        return WorkerResult.success_result(
            worker_name=self.name,
            worker_role=self.role,
            output=(
                ("analysis_json", output.to_json()),
                ("analysis_hash", output.analysis_hash),
            ),
            metadata=metadata,
        )

    @staticmethod
    def _parse_or_degrade(
        content: str,
        fallback_status: str,
    ) -> tuple[AnalysisOutput, Exception | None]:
        if fallback_status == "degraded":
            return AnalysisOutput.degraded_output(content), None
        try:
            output = AnalysisOutput.from_json(content)
        except Exception as exc:
            return AnalysisOutput.degraded_output(str(exc)), exc
        return output, None

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
                run_id=_safe_trace_run_id(context.run_id, "analyze"),
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
        raise ValueError("AnalysisOutput sequence fields must be lists")
    if any(not isinstance(item, str) for item in value):
        raise ValueError("AnalysisOutput sequence fields must contain strings")
    clean = {sanitize_worker_text(item).strip() for item in value if item.strip()}
    if not clean:
        raise ValueError("AnalysisOutput sequence fields must not be empty")
    return tuple(sorted(clean))


def _bool_field(raw: dict[str, object], field_name: str) -> bool:
    value = raw[field_name]
    if not isinstance(value, bool):
        raise ValueError(f"AnalysisOutput.{field_name} must be a boolean")
    return value


def _safe_trace_run_id(run_id: str, suffix: str) -> str:
    safe_run_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", run_id.strip()).strip(".-")
    if not safe_run_id:
        safe_run_id = "run"
    return f"{safe_run_id}-{suffix}"
