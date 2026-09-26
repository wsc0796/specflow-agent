"""Command-line entry point for SpecFlow Agent."""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from specflow import __version__


def main(argv: list[str] | None = None) -> None:
    """Parse arguments and delegate to the runner."""
    args = _parse_args(argv or sys.argv[1:])

    if args.command == "benchmark":
        from specflow.evaluation.benchmark import (
            load_benchmark_cases,
            normalized_baseline,
            run_mock_benchmark,
            write_json,
        )

        try:
            report = run_mock_benchmark(
                load_benchmark_cases(Path(args.suite)),
                repo=Path(args.repo),
                output=Path(args.output),
            )
            write_json(report, Path(args.output) / "benchmark-report.json")
            if args.baseline:
                write_json(normalized_baseline(report), Path(args.baseline))
        except (OSError, ValueError) as exc:
            print(f"Benchmark error: {exc}", file=sys.stderr)
            raise SystemExit(2) from exc
        raise SystemExit(0 if report["status"] == "passed" else 3)
    if args.command == "mcp":
        from specflow.mcp.server import run_stdio
        from specflow.tools.registry import ToolRegistry
        from specflow.tools.repository_tools import RepositoryToolSet

        registry = ToolRegistry()
        RepositoryToolSet(Path(args.root)).register_into(registry)
        run_stdio(registry)
        raise SystemExit(0)
    if args.mode == "multi-agent":
        from specflow.policy import DEFAULT_POLICY
        from specflow.runner_multi import run_multi_agent

        policy = (
            replace(DEFAULT_POLICY, max_llm_calls=args.max_llm_calls)
            if args.max_llm_calls is not None
            else DEFAULT_POLICY
        )
        exit_code = run_multi_agent(
            repo=Path(args.repo),
            requirement=args.requirement,
            output=Path(args.output),
            mock=args.mock,
            provider=args.provider,
            model=args.model or "",
            policy=policy,
        )
    else:
        from specflow.runner import run

        exit_code = run(
            repo=Path(args.repo),
            requirement=args.requirement,
            output=Path(args.output),
            provider=args.provider,
            model=args.model or "",
            mock=args.mock,
            max_files=args.max_files,
        )
    raise SystemExit(exit_code)


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a positive integer") from error
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="specflow",
        description="SpecFlow Agent — spec-driven development assistant",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show the installed package version and exit",
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run specification generation")
    run_parser.add_argument("--repo", required=True, help="Path to the target repository")
    run_parser.add_argument("--requirement", required=True, help="Requirement description")
    run_parser.add_argument(
        "--output", default="./artifacts", help="Output directory for artifacts"
    )

    benchmark_parser = subparsers.add_parser(
        "benchmark", help="Run the deterministic mock portfolio benchmark"
    )
    benchmark_parser.add_argument(
        "--suite", required=True, help="Directory of 12 benchmark JSON cases"
    )
    benchmark_parser.add_argument(
        "--repo", required=True, help="Committed read-only fixture repository"
    )
    benchmark_parser.add_argument(
        "--output", required=True, help="Empty directory for generated artifacts"
    )
    benchmark_parser.add_argument(
        "--baseline",
        default="",
        help="Optional path for normalized, commit-safe mock baseline JSON",
    )
    mcp_parser = subparsers.add_parser("mcp", help="Serve repository Tools over MCP (stdio)")
    mcp_parser.add_argument("--root", required=True, help="Path to the repository root to expose")
    run_parser.add_argument(
        "--provider",
        default="mock",
        choices=["mock", "openai-compatible"],
        help="LLM provider type (default: mock)",
    )
    run_parser.add_argument("--model", default="", help="Model name override (optional)")
    run_parser.add_argument(
        "--max-llm-calls",
        type=_positive_int,
        default=None,
        help="Total LLM request limit for multi-agent mode (default: 10)",
    )
    run_parser.add_argument(
        "--max-files", type=int, default=5, help="Maximum files to read (default: 5)"
    )
    run_parser.add_argument(
        "--mock",
        action="store_true",
        help="Force mock mode even if provider is configured",
    )
    run_parser.add_argument(
        "--mode",
        default="legacy",
        choices=["legacy", "multi-agent"],
        help="Execution mode: legacy or multi-agent (default: legacy)",
    )

    parsed = parser.parse_args(argv)
    if not parsed.command:
        parser.print_help()
        raise SystemExit(2)
    if (
        parsed.command == "run"
        and parsed.mode != "multi-agent"
        and parsed.max_llm_calls is not None
    ):
        run_parser.error("--max-llm-calls requires --mode multi-agent")
    return parsed
