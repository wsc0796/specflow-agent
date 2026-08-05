"""Run the frozen live-provider v1 evaluation without exposing credentials."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from specflow.evaluation.live_provider_v1 import (
    LiveEvaluationError,
    build_live_report,
    load_live_suite,
    load_pricing_rule,
    load_provider_config,
    run_live_suite,
    write_live_report,
)


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[1]
    args = _parse_args(argv, root)
    try:
        suite = load_live_suite(
            tasks_dir=args.tasks,
            controls_dir=args.controls,
            lock_path=args.suite_lock,
        )
        config = load_provider_config(model_override=args.model)
        pricing = load_pricing_rule(
            args.pricing,
            provider="openai-compatible",
            model=config.model,
        )
        results = run_live_suite(
            suite=suite,
            repository_root=args.repo,
            runs_root=args.runs_root,
            config=config,
            pricing=pricing,
        )
        if not results or not isinstance(results[0].get("batch_id"), str):
            raise LiveEvaluationError("live evaluation did not produce a batch identity")
        report = build_live_report(args.runs_root, batch_id=str(results[0]["batch_id"]))
        write_live_report(report, args.report)
    except LiveEvaluationError as exc:
        print(f"Live evaluation blocked: {exc}", file=sys.stderr)
        return 2

    quality_passed = all(
        item.get("deterministic_status") == "passed"
        for item in results
        if item.get("evaluation_class") == "quality"
    )
    controls_passed = all(
        item.get("deterministic_status") == "passed"
        for item in results
        if item.get("evaluation_class") == "control"
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "quality_task_count": report["quality_task_count"],
                "control_count": report["control_count"],
                "report": str(args.report),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if quality_passed and controls_passed else 3


def _parse_args(argv: list[str] | None, root: Path) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the frozen SpecFlow live-provider v1 evaluation suite."
    )
    parser.add_argument(
        "--repo",
        type=Path,
        required=True,
        help="Clean target repository at suite commit",
    )
    parser.add_argument(
        "--pricing",
        type=Path,
        required=True,
        help="Untracked, explicit Provider pricing rule matching the configured model",
    )
    parser.add_argument(
        "--tasks",
        type=Path,
        default=root / "evals" / "live-provider-v1" / "tasks",
    )
    parser.add_argument(
        "--controls",
        type=Path,
        default=root / "evals" / "live-provider-v1" / "controls",
    )
    parser.add_argument(
        "--suite-lock",
        type=Path,
        default=root / "evals" / "live-provider-v1" / "suite-lock.json",
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=root / "evals" / "live-provider-v1" / "runs",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=root / "docs" / "reports" / "live-provider-evaluation-v1.md",
    )
    parser.add_argument("--model", default="", help="Optional override for SPECFLOW_LLM_MODEL")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
