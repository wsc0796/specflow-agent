from pathlib import Path

from specflow.evaluation.models import EvaluationCase

MULTI_AGENT_EVAL_CASE = EvaluationCase(
    case_id="multi-agent-v1",
    description="A/B comparison: legacy linear vs multi-agent on same repo+requirement",
    repo_path=Path("C:/Users/50469/github-projects/sky-takeout-python"),
    requirement="为订单增加超时自动取消功能",
    expected_artifacts_count=10,
    min_dimension_score=1,
)
