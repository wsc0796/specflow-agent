"""Command-line entry point for SpecFlow Agent."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    """Parse arguments and delegate to the runner."""
    args = _parse_args(argv or sys.argv[1:])

    if args.mode == "multi-agent":
        from specflow.runner_multi import run_multi_agent

        exit_code = run_multi_agent(
            repo=Path(args.repo),
            requirement=args.requirement,
            output=Path(args.output),
            mock=args.mock,
            provider=args.provider,
            model=args.model or "",
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


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="specflow",
        description="SpecFlow Agent — spec-driven development assistant",
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run specification generation")
    run_parser.add_argument("--repo", required=True, help="Path to the target repository")
    run_parser.add_argument("--requirement", required=True, help="Requirement description")
    run_parser.add_argument(
        "--output", default="./artifacts", help="Output directory for artifacts"
    )
    run_parser.add_argument(
        "--provider",
        default="mock",
        choices=["mock", "openai-compatible"],
        help="LLM provider type (default: mock)",
    )
    run_parser.add_argument("--model", default="", help="Model name override (optional)")
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
    return parsed
