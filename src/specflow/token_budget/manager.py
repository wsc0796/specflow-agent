"""Deterministic token budget management."""

from __future__ import annotations

from dataclasses import replace

from specflow.context_builder import BuiltContext
from specflow.token_budget.estimator import TokenEstimator
from specflow.token_budget.exceptions import TokenBudgetError
from specflow.token_budget.models import BudgetPolicy, BudgetResult, RemovedSection

_SECTION_MARKERS = {
    "requirement": ["Requirement:", "User requirement:", "Requirement analysis:"],
    "project_overview": [
        "Project:",
        "# Project Context",
        "project_name:",
        "total_files:",
        "ignored_directories:",
        "oversized_files:",
    ],
    "technology_stack": [
        "language:",
        "frameworks:",
        "validation_library:",
        "orm:",
        "database:",
        "test_framework:",
        "lint_tools:",
        "dependency_files:",
        "entry_candidates:",
        "top_level_directories:",
    ],
    "evidence": ["technology_evidence:"],
    "warnings": ["parse_warnings:"],
    "unknowns": ["unknowns:", "Unknowns:"],
}


class TokenBudgetManager:
    """Apply deterministic token budgets to BuiltContext objects."""

    def __init__(self, policy: BudgetPolicy) -> None:
        self._validate_policy(policy)
        self._policy = policy
        self._estimator = TokenEstimator(policy.estimation_chars_per_token)

    def apply(self, context: BuiltContext) -> BudgetResult:
        original_tokens = self._estimate_context(context)
        if original_tokens <= self._policy.input_budget:
            return BudgetResult(
                context=context,
                policy=self._policy,
                original_estimated_tokens=original_tokens,
                final_estimated_tokens=original_tokens,
                was_trimmed=False,
                removed_sections=[],
            )

        sections = self._split_user_message(context.user_message)
        base_context = replace(context, user_message="")
        base_tokens = self._estimate_context(base_context)
        if base_tokens > self._policy.input_budget:
            raise TokenBudgetError("Budget cannot fit required system and metadata content")

        selected_sections, removed_sections = self._trim_sections(
            context=context,
            sections=sections,
        )
        trimmed_message = self._join_sections(selected_sections)
        trimmed_context = replace(context, user_message=trimmed_message, context_hash="")
        final_tokens = self._estimate_context(trimmed_context)
        if final_tokens > self._policy.input_budget:
            raise TokenBudgetError("Budget cannot fit required high-priority context")

        return BudgetResult(
            context=trimmed_context,
            policy=self._policy,
            original_estimated_tokens=original_tokens,
            final_estimated_tokens=final_tokens,
            was_trimmed=True,
            removed_sections=removed_sections,
        )

    @staticmethod
    def _validate_policy(policy: BudgetPolicy) -> None:
        if policy.max_tokens <= 0:
            raise TokenBudgetError("max_tokens must be positive")
        if policy.reserved_response_tokens < 0:
            raise TokenBudgetError("reserved_response_tokens must not be negative")
        if policy.input_budget <= 0:
            raise TokenBudgetError("reserved_response_tokens must be smaller than max_tokens")
        if policy.estimation_chars_per_token <= 0:
            raise TokenBudgetError("estimation_chars_per_token must be positive")

    def _estimate_context(self, context: BuiltContext) -> int:
        source_text = "\n".join(
            f"{source.kind}:{source.identifier}:{source.hash or ''}" for source in context.sources
        )
        metadata = "\n".join(
            [
                context.prompt_name,
                context.prompt_version,
                context.prompt_hash,
                context.project_context_hash,
                context.context_hash,
                source_text,
            ]
        )
        return self._estimator.estimate(context.system_message, context.user_message, metadata)

    def _trim_sections(
        self,
        context: BuiltContext,
        sections: list[tuple[str, str]],
    ) -> tuple[list[tuple[str, str]], list[RemovedSection]]:
        selected = list(sections)
        removed: list[RemovedSection] = []

        for index, (name, text) in self._removal_order(sections):
            if self._estimate_with_sections(context, selected) <= self._policy.input_budget:
                break
            selected[index] = ("", "")
            removed.append(
                RemovedSection(
                    name=name,
                    estimated_tokens=self._estimator.estimate(text),
                    priority=self._priority(name),
                )
            )

        selected = [(name, text) for name, text in selected if name and text]
        return selected, removed

    def _estimate_with_sections(
        self,
        context: BuiltContext,
        sections: list[tuple[str, str]],
    ) -> int:
        trimmed = replace(context, user_message=self._join_sections(sections), context_hash="")
        return self._estimate_context(trimmed)

    def _removal_order(self, sections: list[tuple[str, str]]) -> list[tuple[int, tuple[str, str]]]:
        indexed = list(enumerate(sections))
        return sorted(indexed, key=lambda item: (self._priority(item[1][0]), item[0]))

    def _priority(self, section_name: str) -> int:
        return self._policy.section_priorities.get(section_name, 0)

    @staticmethod
    def _split_user_message(message: str) -> list[tuple[str, str]]:
        sections: list[tuple[str, list[str]]] = []
        current_name = "project_overview"
        current_lines: list[str] = []

        for line in message.splitlines():
            detected = TokenBudgetManager._detect_section(line)
            if detected and current_lines:
                sections.append((current_name, current_lines))
                current_name = detected
                current_lines = [line]
            else:
                if detected:
                    current_name = detected
                current_lines.append(line)

        if current_lines:
            sections.append((current_name, current_lines))

        return [
            (name, "\n".join(lines).strip()) for name, lines in sections if "\n".join(lines).strip()
        ]

    @staticmethod
    def _detect_section(line: str) -> str | None:
        stripped = line.strip()
        for section_name, markers in _SECTION_MARKERS.items():
            if stripped in markers or any(stripped.startswith(marker) for marker in markers):
                return section_name
        return None

    @staticmethod
    def _join_sections(sections: list[tuple[str, str]]) -> str:
        return "\n".join(text for _, text in sections if text).strip()
