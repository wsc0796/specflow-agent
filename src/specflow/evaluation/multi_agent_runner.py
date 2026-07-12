from dataclasses import dataclass
from pathlib import Path

from specflow.evaluation.rubric import RubricDimension
from specflow.runner import run as run_legacy
from specflow.runner_multi import run_multi_agent

AB_DIMENSIONS = [
    RubricDimension("requirement_coverage", "需求覆盖率", max_score=2),
    RubricDimension("file_reference_rate", "真实文件引用率", max_score=2),
    RubricDimension("risk_coverage", "风险覆盖率", max_score=2),
    RubricDimension("test_completeness", "测试方案完整度", max_score=2),
    RubricDimension("review_findings", "Review 问题发现数", max_score=2),
    RubricDimension("human_edit_reduction", "人工修改量", max_score=2),
    RubricDimension("token_cost", "Token 成本", max_score=2),
    RubricDimension("end_to_end_latency", "端到端耗时", max_score=2),
    RubricDimension("fallback_rate", "Fallback 率", max_score=2),
    RubricDimension("revision_count", "Revision 次数", max_score=2),
]


@dataclass
class ABComparisonResult:
    case_id: str
    legacy_scores: dict[str, int]
    multi_agent_scores: dict[str, int]
    legacy_total: int
    multi_agent_total: int

    @property
    def improvement(self) -> int:
        return self.multi_agent_total - self.legacy_total

    @property
    def summary(self) -> str:
        return (
            f"Legacy: {self.legacy_total}/20 | "
            f"Multi-Agent: {self.multi_agent_total}/20 | "
            f"Delta: {self.improvement:+d}"
        )


def compare_legacy_vs_multi_agent(legacy_results: dict, multi_results: dict) -> ABComparisonResult:
    """Compare legacy and multi-agent evaluation results."""
    legacy_scores = {d["key"]: d["score"] for d in legacy_results.get("dimensions", [])}
    multi_scores = {d["key"]: d["score"] for d in multi_results.get("dimensions", [])}
    return ABComparisonResult(
        case_id=multi_results.get("case_id", "unknown"),
        legacy_scores=legacy_scores,
        multi_agent_scores=multi_scores,
        legacy_total=sum(legacy_scores.values()),
        multi_agent_total=sum(multi_scores.values()),
    )


def run_mock_ab_case(*, repo: Path, requirement: str, output: Path) -> ABComparisonResult:
    """Execute both pipelines on identical inputs and score artifact contracts only."""
    legacy_output = output / "legacy"
    multi_output = output / "multi-agent"
    legacy_code = run_legacy(
        repo=repo, requirement=requirement, output=legacy_output, provider="mock"
    )
    multi_code = run_multi_agent(repo=repo, requirement=requirement, output=multi_output, mock=True)
    legacy_artifact = next(legacy_output.glob("run-*"), None)
    multi_artifact = next(multi_output.glob("run-multi-*"), None)
    legacy = {
        "case_id": "mock-ab",
        "dimensions": [
            {
                "key": "artifact_completeness",
                "score": 2 if legacy_artifact and legacy_code in {0, 4} else 0,
            },
            {"key": "requirement_coverage", "score": 0},
        ],
    }
    multi = {
        "case_id": "mock-ab",
        "dimensions": [
            {
                "key": "artifact_completeness",
                "score": 2 if multi_artifact and multi_code == 0 else 0,
            },
            {"key": "requirement_coverage", "score": 0},
        ],
    }
    return compare_legacy_vs_multi_agent(legacy, multi)
