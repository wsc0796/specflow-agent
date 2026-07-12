"""Explicit models for deterministic and human evaluation evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from specflow.evaluation.exceptions import EvaluationError


class EvaluationMode(StrEnum):
    MOCK_CONTRACT = "mock_contract"
    LIVE_PROVIDER = "live_provider"


class EvaluationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class ScoreSource(StrEnum):
    AUTOMATED = "automated"
    HUMAN = "human"


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    title: str
    requirement: str
    repository_type: str
    expected_domains: tuple[str, ...]
    expected_file_patterns: tuple[str, ...]
    expected_risks: tuple[str, ...]
    expected_acceptance_topics: tuple[str, ...]
    forbidden_claims: tuple[str, ...]
    human_review_notes: str

    def __post_init__(self) -> None:
        for name in ("case_id", "title", "requirement", "repository_type", "human_review_notes"):
            if not getattr(self, name).strip():
                raise EvaluationError(f"EvaluationCase.{name} must not be empty")
        if "/" in self.case_id or "\\" in self.case_id or self.case_id in {".", ".."}:
            raise EvaluationError("EvaluationCase.case_id must be a safe identifier")
        for name in (
            "expected_domains",
            "expected_file_patterns",
            "expected_risks",
            "expected_acceptance_topics",
            "forbidden_claims",
        ):
            values = getattr(self, name)
            if not values or any(not value.strip() for value in values):
                raise EvaluationError(f"EvaluationCase.{name} must contain values")


@dataclass(frozen=True)
class EvaluationFinding:
    code: str
    message: str
    severity: str = "error"

    def __post_init__(self) -> None:
        if not self.code.strip() or not self.message.strip():
            raise EvaluationError("EvaluationFinding fields must not be empty")
        if self.severity not in {"error", "warning", "info"}:
            raise EvaluationError("EvaluationFinding.severity is invalid")


@dataclass(frozen=True)
class EvaluationScore:
    dimension: str
    score: int
    source: ScoreSource
    notes: str

    def __post_init__(self) -> None:
        if not self.dimension.strip() or not self.notes.strip():
            raise EvaluationError("EvaluationScore fields must not be empty")
        if self.score not in {0, 1, 2}:
            raise EvaluationError("EvaluationScore.score must be 0, 1, or 2")


@dataclass(frozen=True)
class EvaluationRun:
    case_id: str
    mode: EvaluationMode
    status: EvaluationStatus
    artifact_directory: str
    findings: tuple[EvaluationFinding, ...] = ()
    automated_scores: tuple[EvaluationScore, ...] = ()
    human_scores: tuple[EvaluationScore, ...] = ()

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.artifact_directory.strip():
            raise EvaluationError("EvaluationRun identifiers must not be empty")
        if any(score.source != ScoreSource.AUTOMATED for score in self.automated_scores):
            raise EvaluationError("automated_scores must have automated source")
        if any(score.source != ScoreSource.HUMAN for score in self.human_scores):
            raise EvaluationError("human_scores must have human source")


@dataclass(frozen=True)
class EvaluationReport:
    mode: EvaluationMode
    status: EvaluationStatus
    runs: tuple[EvaluationRun, ...]
    live_validation_status: EvaluationStatus
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class LiveValidationRecord:
    status: EvaluationStatus
    artifact_directory: str
    provider_type: str = ""
    model: str = ""
    findings: tuple[EvaluationFinding, ...] = field(default_factory=tuple)
